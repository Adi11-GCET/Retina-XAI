import os
import random
import string
import shutil
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename

from utils.database import (
    init_db, add_screening, update_screening_notes,
    get_screening_by_id, get_all_screenings, get_dashboard_statistics
)
from utils.preprocessing import allowed_file, MAX_FILE_SIZE
from services.prediction_service import (
    initialize_model, predict_fundus_image, is_demo_mode, get_model
)
from services.gradcam import generate_gradcam_heatmap

app = Flask(__name__)
app.config['SECRET_KEY'] = 'retina-xai-rural-screening-key-2026'
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
GENERATED_FOLDER = os.path.join(BASE_DIR, 'static', 'generated')
SAMPLES_FOLDER = os.path.join(BASE_DIR, 'static', 'samples')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)
os.makedirs(SAMPLES_FOLDER, exist_ok=True)

# Initialize database and model on startup
init_db()
initialize_model()

@app.context_processor
def inject_global_vars():
    return {
        'is_demo': is_demo_mode(),
        'current_year': datetime.now().year,
        'model_status': 'Trained IDRiD Deep Learning Model Active' if not is_demo_mode() else 'Demonstration Mode'
    }

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

        # Execute AI Screening Inference (PyTorch trained model)
        prediction_result = predict_fundus_image(target_img_path)
        
        # Generate Grad-CAM heatmaps & overlay (PyTorch gradients)
        rel_heatmap, rel_overlay = generate_gradcam_heatmap(
            target_img_path,
            GENERATED_FOLDER,
            prediction_result['class_id'],
            model=get_model(),
            is_demo=prediction_result['is_demo']
        )

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
            is_demo=1 if prediction_result['is_demo'] else 0
        )

        return jsonify({
            'success': True,
            'patient_id': patient_id,
            'redirect_url': url_for('result', screening_id=patient_id)
        })

    except Exception as e:
        print(f"[ERROR in /predict]: {e}")
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
        print(f"[ERROR in /save-screening]: {e}")
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
    print("\n" + "="*60)
    print("  RETINA-XAI — Explainable AI for Retinal Screening")
    print("  Server launching at: http://127.0.0.1:5000")
    print("="*60 + "\n")
    app.run(host='127.0.0.1', port=5000, debug=False)
