import os
import gc
import time
import random
import string
import shutil
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, session
from werkzeug.utils import secure_filename
import torch

# Enforce single-thread CPU execution to eliminate thread contention on 0.1 CPU
torch.set_num_threads(1)
try:
    torch.set_num_interop_threads(1)
except Exception:
    pass

from utils.database import (
    init_db, add_screening, update_screening_notes,
    get_screening_by_id, get_all_screenings, get_dashboard_statistics,
    create_or_update_user, get_user_by_email
)
from utils.preprocessing import allowed_file, MAX_FILE_SIZE
from utils.validation import validate_retinal_image
from services.prediction_service import (
    initialize_model, predict_fundus_image, is_demo_mode, get_model
)
from services.gradcam import generate_gradcam_heatmap
from services.segmentation_service import predict_retinal_segmentation

app = Flask(__name__)
app.config['SECRET_KEY'] = 'retina-xai-rural-screening-key-2026'
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

DEMO_OTP = "652070"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
GENERATED_FOLDER = os.path.join(BASE_DIR, 'static', 'generated')
SAMPLES_FOLDER = os.path.join(BASE_DIR, 'static', 'samples')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)
os.makedirs(SAMPLES_FOLDER, exist_ok=True)

# Initialize database on startup
init_db()
# Note: Heavy models are loaded lazily on first access to keep startup RAM minimal (~100MB)

@app.context_processor
def inject_global_vars():
    demo_active = is_demo_mode()
    return {
        'is_demo': demo_active,
        'current_year': datetime.now().year,
        'model_status': 'Trained IDRiD Deep Learning Model Active' if not demo_active else 'Demonstration Mode',
        'current_user': session.get('user')
    }

@app.before_request
def check_authentication():
    # Public endpoints that never require authentication
    public_endpoints = {'static', 'favicon', 'index', 'about', 'login', 'register', 'otp', 'guest', 'logout'}
    if request.endpoint in public_endpoints or request.endpoint is None:
        return None

    # Public API read endpoints
    if request.path.startswith('/api/'):
        return None

    # Protected clinical routes
    if 'user' not in session:
        if request.endpoint in {'screening', 'dashboard', 'history', 'result'}:
            next_param = request.full_path if request.query_string else request.path
            return redirect(url_for('login', next=next_param))
        if request.path in ['/predict', '/save-screening']:
            return jsonify({'success': False, 'error': 'Authentication required. Please log in or continue as Guest Screener.'}), 401
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or request.form.get('next', '')
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            return render_template('login.html', error='Please enter a valid email address.', next_url=next_url)
        session['pending_email'] = email
        user = get_user_by_email(email)
        if user:
            session['pending_name'] = user['full_name']
            session['pending_role'] = user.get('role', 'Clinician / Screener')
            return redirect(url_for('otp', next=next_url))
        else:
            return redirect(url_for('register', email=email, next=next_url))
    return render_template('login.html', next_url=next_url)

@app.route('/register', methods=['GET', 'POST'])
def register():
    next_url = request.args.get('next') or request.form.get('next', '')
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        age = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()

        if not full_name or not email:
            return render_template('register.html', error='Full name and email are required.', email=email, next_url=next_url)

        parsed_age = int(age) if age.isdigit() else None
        session['pending_name'] = full_name
        session['pending_email'] = email
        session['pending_age'] = parsed_age
        session['pending_gender'] = gender

        # Persist user details
        create_or_update_user(full_name, email, parsed_age, gender)
        return redirect(url_for('otp', next=next_url))

    initial_email = request.args.get('email') or session.get('pending_email', '')
    return render_template('register.html', email=initial_email, next_url=next_url)

@app.route('/otp', methods=['GET', 'POST'])
def otp():
    next_url = request.args.get('next') or request.form.get('next', '')
    email = session.get('pending_email', 'demo@drishtiai.org')

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()
        if entered_otp == DEMO_OTP:
            email = session.get('pending_email', 'demo@drishtiai.org')
            user_db = get_user_by_email(email)
            name = session.get('pending_name')
            role = session.get('pending_role', 'Clinician / Screener')

            if user_db:
                name = user_db['full_name']
                role = user_db.get('role', 'Clinician / Screener')
            elif not name:
                name = 'Dr. Ananya Sharma' if email == 'demo@drishtiai.org' else email.split('@')[0].capitalize()
                create_or_update_user(name, email, session.get('pending_age'), session.get('pending_gender'), role)

            session['user'] = {
                'name': name,
                'email': email,
                'role': role,
                'is_guest': False
            }
            # Clear temporary session data
            session.pop('pending_name', None)
            session.pop('pending_email', None)
            session.pop('pending_age', None)
            session.pop('pending_gender', None)
            session.pop('pending_role', None)

            target = next_url if next_url and not next_url.startswith('/login') else url_for('dashboard')
            return redirect(target)
        else:
            return render_template('otp.html', email=email, demo_otp=DEMO_OTP, error='Invalid security OTP code. Please use the demonstration code 652070.', next_url=next_url)

    return render_template('otp.html', email=email, demo_otp=DEMO_OTP, next_url=next_url)

@app.route('/guest')
def guest():
    next_url = request.args.get('next', '')
    session['user'] = {
        'name': 'Guest Screener',
        'email': 'guest@drishtiai.org',
        'role': 'Guest Clinician',
        'is_guest': True
    }
    target = next_url if next_url and not next_url.startswith('/login') else url_for('dashboard')
    return redirect(target)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.svg', mimetype='image/svg+xml')

@app.route('/')
def index():
    return render_template('index.html', active_page='home')

@app.route('/screening')
def screening():
    return render_template('screening.html', active_page='screening')

@app.route('/predict', methods=['POST'])
def predict():
    t_total_start = time.perf_counter()
    try:
        sample_name = request.form.get('sample_name', '').strip()
        uploaded_file = request.files.get('image')

        # Generate unique Patient ID (e.g. RXT-2048)
        rand_num = random.randint(1020, 9999)
        patient_id = f"RXT-{rand_num}"

        target_img_filename = f"{patient_id}_fundus.jpg"
        target_img_path = os.path.join(UPLOAD_FOLDER, target_img_filename)
        rel_img_path = f"static/uploads/{target_img_filename}"

        if sample_name:
            # Using preloaded sample case
            sample_source = os.path.join(SAMPLES_FOLDER, sample_name)
            if not os.path.exists(sample_source):
                return jsonify({'success': False, 'error': f'Sample image {sample_name} not found.'}), 400
            shutil.copyfile(sample_source, target_img_path)
        elif uploaded_file and uploaded_file.filename != '':
            if not allowed_file(uploaded_file.filename):
                return jsonify({'success': False, 'error': 'Please upload a valid JPG, JPEG, or PNG retinal fundus photograph.'}), 400
            uploaded_file.save(target_img_path)
        else:
            return jsonify({'success': False, 'error': 'Please select or upload a retinal image before analysis.'}), 400

        # Validate retinal image domain & quality (Reject random non-retinal photos)
        t_val_start = time.perf_counter()
        validation = validate_retinal_image(target_img_path)
        t_val_elapsed = (time.perf_counter() - t_val_start) * 1000
        print(f"[RETINA-XAI TIMING] Validation: {t_val_elapsed:.1f}ms", flush=True)

        if not validation['is_valid_retina']:
            if os.path.exists(target_img_path):
                try:
                    os.remove(target_img_path)
                except Exception:
                    pass
            return jsonify({
                'success': False,
                'is_invalid_image': True,
                'error': f"Invalid Image: {validation['reason']}. Please upload a standard retinal fundus photograph.",
                'validation_metrics': validation.get('metrics', {})
            }), 400

        # Execute AI Screening Inference (PyTorch trained model)
        t_dr_start = time.perf_counter()
        prediction_result = predict_fundus_image(target_img_path)
        t_dr_elapsed = (time.perf_counter() - t_dr_start) * 1000
        print(f"[RETINA-XAI TIMING] DR Inference: {t_dr_elapsed:.1f}ms", flush=True)
        
        # Generate Grad-CAM heatmaps & overlay (PyTorch gradients)
        t_cam_start = time.perf_counter()
        rel_heatmap, rel_overlay = generate_gradcam_heatmap(
            target_img_path,
            GENERATED_FOLDER,
            prediction_result['class_id'],
            model=get_model(),
            is_demo=prediction_result['is_demo']
        )
        t_cam_elapsed = (time.perf_counter() - t_cam_start) * 1000
        print(f"[RETINA-XAI TIMING] Grad-CAM: {t_cam_elapsed:.1f}ms", flush=True)

        # Generate IDRiD U-Net retinal segmentation (lesions & optic disc)
        t_seg_start = time.perf_counter()
        seg_result = predict_retinal_segmentation(target_img_path, GENERATED_FOLDER, patient_id)
        t_seg_elapsed = (time.perf_counter() - t_seg_start) * 1000
        print(f"[RETINA-XAI TIMING] Segmentation: {t_seg_elapsed:.1f}ms", flush=True)

        # Persist to SQLite
        add_screening(
            patient_id=patient_id,
            image_path=rel_img_path,
            heatmap_path=rel_heatmap,
            overlay_path=rel_overlay,
            prediction=prediction_result['class_name'],
            class_id=prediction_result['class_id'],
            confidence=prediction_result['confidence'],
            probabilities=prediction_result['probabilities'],
            risk_status=prediction_result['clinical_profile']['summary'],
            notes='',
            referral_required=1 if prediction_result['clinical_profile']['referral_recommended'] else 0,
            is_demo=1 if prediction_result['is_demo'] else 0,
            seg_overlay_path=seg_result.get('seg_overlay_path', ''),
            seg_mask_path=seg_result.get('seg_mask_path', ''),
            detected_lesions=seg_result.get('detected_lesions', {})
        )

        t_total_elapsed = (time.perf_counter() - t_total_start) * 1000
        print(f"[RETINA-XAI TIMING] Total Screening Request: {t_total_elapsed:.1f}ms", flush=True)
        gc.collect()

        return jsonify({
            'success': True,
            'patient_id': patient_id,
            'redirect_url': url_for('result', screening_id=patient_id)
        })

    except Exception as e:
        print(f"[ERROR in /predict]: {e}", flush=True)
        return jsonify({'success': False, 'error': 'AI analysis is temporarily unavailable. Please try again.'}), 500

@app.route('/result/<screening_id>')
def result(screening_id):
    screening_record = get_screening_by_id(screening_id)
    if not screening_record:
        return redirect(url_for('screening'))
    return render_template('result.html', screening=screening_record, active_page='screening')

@app.route('/save-screening', methods=['POST'])
def save_screening():
    try:
        screening_id = request.form.get('screening_id')
        notes = request.form.get('notes', '').strip()
        referral_required = int(request.form.get('referral_required', 0))

        if not screening_id:
            return jsonify({'success': False, 'error': 'Missing screening ID'}), 400

        update_screening_notes(screening_id, notes, referral_required)
        return jsonify({'success': True, 'message': 'Screening record updated successfully.'})
    except Exception as e:
        print(f"[ERROR in /save-screening]: {e}", flush=True)
        return jsonify({'success': False, 'error': 'Unable to save screening. Please try again.'}), 500

@app.route('/dashboard')
def dashboard():
    stats = get_dashboard_statistics()
    return render_template('dashboard.html', stats=stats, active_page='dashboard')

@app.route('/history')
def history():
    class_filter = request.args.get('class_filter', 'all')
    search_query = request.args.get('q', '').strip()
    screenings = get_all_screenings(filter_class=class_filter, search_query=search_query)
    return render_template('history.html', screenings=screenings, current_filter=class_filter, search_query=search_query, active_page='history')

@app.route('/about')
def about():
    return render_template('about.html', active_page='about')

# API Endpoints
@app.route('/api/dashboard')
def api_dashboard():
    return jsonify(get_dashboard_statistics())

@app.route('/api/history')
def api_history():
    screenings = get_all_screenings()
    return jsonify(screenings)

# Error Handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('base.html', content='<div class="container py-5 text-center"><h2>Page Not Found</h2><p class="text-muted">The requested clinical page could not be located.</p><a href="/" class="btn btn-primary-custom">Return to Home</a></div>'), 404

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({'success': False, 'error': 'Maximum file size is 10 MB. Please upload a smaller image.'}), 413

@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': 'Internal system error. Please contact administrator.'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("\n" + "="*60)
    print("  RETINA-XAI — Explainable AI for Retinal Screening")
    print(f"  Server launching at: http://0.0.0.0:{port}")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=port, debug=False)
