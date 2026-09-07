import os
import gc
import time
import random
import string
import secrets
import shutil
import csv
import io
from datetime import datetime
from flask import (
    Flask, render_template, render_template_string, request, jsonify, redirect,
    url_for, send_from_directory, session, Response
)
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
    get_screening_by_id, get_all_screenings, get_user_screenings,
    get_dashboard_statistics, get_or_create_user_by_phone,
    get_user_by_id, get_user_by_email, create_or_update_user
)
from utils.preprocessing import allowed_file, MAX_FILE_SIZE
from utils.validation import validate_retinal_image
from services.prediction_service import (
    initialize_model, predict_fundus_image, is_demo_mode, get_model
)
from services.gradcam import generate_gradcam_heatmap
from services.segmentation_service import predict_retinal_segmentation
from services.otp_service import (
    normalize_phone_number, otp_manager, DEMO_OTP,
    get_otp_provider, MockOtpProvider, UnavailableOtpProvider,
    is_production_mode, is_demo_otp_allowed
)
from services.chatbot_service import chatbot_service
from services.storage_service import storage_service

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'retina-xai-rural-screening-key-2026')
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Production-safe session cookie settings
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if is_production_mode():
    app.config['SESSION_COOKIE_SECURE'] = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
GENERATED_FOLDER = os.path.join(BASE_DIR, 'static', 'generated')
SAMPLES_FOLDER = os.path.join(BASE_DIR, 'static', 'samples')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)
os.makedirs(SAMPLES_FOLDER, exist_ok=True)

# Initialize database on startup (executes safe non-destructive migration)
init_db()

def get_client_ip() -> str:
    """Extracts client IP from X-Forwarded-For or remote_addr."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'

def mask_phone_number(phone: str) -> str:
    """Masks phone number for privacy, e.g. +919876543210 -> +91 ******3210."""
    if not phone:
        return ""
    p = str(phone).strip()
    if p.startswith('+91') and len(p) >= 13:
        return f"+91 ******{p[-4:]}"
    elif len(p) >= 10:
        return f"{p[:2]}******{p[-4:]}"
    return f"******{p[-4:]}"

@app.context_processor
def inject_global_vars():
    demo_active = is_demo_mode()
    u = session.get('user')
    raw_phone = (u.get('phone') or u.get('mobile_number') or '') if u else ''
    masked_phone = mask_phone_number(raw_phone) if raw_phone else ''
    return {
        'is_demo': demo_active,
        'demo_otp_enabled': is_demo_otp_allowed(),
        'current_year': datetime.now().year,
        'model_status': 'Trained IDRiD Deep Learning Model Active' if not demo_active else 'Demonstration Mode',
        'current_user': u,
        'masked_phone': masked_phone
    }

@app.before_request
def check_authentication():
    # Public endpoints that never require authentication
    public_endpoints = {
        'static', 'favicon', 'index', 'about', 'login',
        'otp', 'resend_otp', 'guest', 'logout', 'health',
        'send_otp_api', 'verify_otp_api'
    }
    if request.endpoint in public_endpoints or request.endpoint is None:
        return None

    # Protected clinical routes require authenticated user session
    if 'user' not in session:
        if request.endpoint in {'screening', 'dashboard', 'history', 'result', 'export_history_csv'}:
            next_param = request.full_path if request.query_string else request.path
            return redirect(url_for('login', next=next_param))
        if request.path in ['/predict', '/save-screening', '/api/chat', '/api/history', '/api/dashboard']:
            return jsonify({
                'success': False,
                'error': 'Authentication required. Please log in or continue as Guest Screener.'
            }), 401

    return None

# -------------------------------------------------------------------
# Authentication Routes (Mobile OTP & Guest Bypass)
# -------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next') or request.form.get('next', '')
    if request.method == 'POST':
        raw_phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip().lower()

        # Legacy email-based login compatibility
        if email and not raw_phone:
            existing_user = get_user_by_email(email)
            if existing_user:
                phone = existing_user.get('phone_number') or '+919876543210'
                session['pending_phone'] = phone
                session['pending_email'] = email
                session['pending_name'] = existing_user.get('full_name')
                if is_demo_otp_allowed():
                    session['demo_otp_display'] = DEMO_OTP
                else:
                    session.pop('demo_otp_display', None)
                return redirect(url_for('otp', next=next_url))
            else:
                session['pending_email'] = email
                return redirect(url_for('register', email=email, next=next_url))

        # Mobile number flow
        try:
            normalized = normalize_phone_number(raw_phone)
        except ValueError as e:
            return render_template('login.html', error=str(e), next_url=next_url)

        client_ip = get_client_ip()
        success, message, demo_code = otp_manager.create_and_send_otp(normalized, ip_address=client_ip)
        if not success:
            return render_template('login.html', error=message, next_url=next_url)

        session['pending_phone'] = normalized
        demo_allowed = is_demo_otp_allowed()
        if demo_allowed and demo_code:
            session['demo_otp_display'] = demo_code
        else:
            session.pop('demo_otp_display', None)
        return redirect(url_for('otp', next=next_url))

    return render_template('login.html', next_url=next_url)

@app.route('/send-otp', methods=['POST'])
def send_otp_api():
    """API endpoint to request an OTP code (supports JSON and form-encoded data)."""
    data = request.get_json(silent=True) or request.form or {}
    raw_phone = data.get('phone') or data.get('mobile_number') or ''
    try:
        normalized = normalize_phone_number(raw_phone)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    client_ip = get_client_ip()
    success, message, demo_code = otp_manager.create_and_send_otp(normalized, ip_address=client_ip)
    if not success:
        return jsonify({'success': False, 'error': message}), 429

    session['pending_phone'] = normalized
    demo_allowed = is_demo_otp_allowed()
    if demo_allowed and demo_code:
        session['demo_otp_display'] = demo_code
    else:
        session.pop('demo_otp_display', None)

    resp_payload = {'success': True, 'message': message}
    if demo_allowed:
        resp_payload['demo_otp'] = demo_code or DEMO_OTP
    return jsonify(resp_payload)

@app.route('/register', methods=['GET', 'POST'])
def register():
    next_url = request.args.get('next') or request.form.get('next', '')
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        age = request.form.get('age', '').strip()
        gender = request.form.get('gender', '').strip()
        phone = request.form.get('phone', '').strip() or '+919876543210'

        if not full_name:
            return render_template('register.html', error='Full name is required.', email=email, next_url=next_url)

        parsed_age = int(age) if age.isdigit() else None
        session['pending_name'] = full_name
        session['pending_email'] = email
        phone_raw = request.form.get('phone', '').strip()
        phone = None
        if phone_raw:
            try:
                phone = normalize_phone_number(phone_raw)
            except Exception:
                phone = None

        if phone:
            session['pending_phone'] = phone

        create_or_update_user(full_name, email=email, age=parsed_age, gender=gender, phone_number=phone)
        return redirect(url_for('otp', next=next_url))

    initial_email = request.args.get('email') or session.get('pending_email', '')
    return render_template('register.html', email=initial_email, next_url=next_url)

@app.route('/otp', methods=['GET', 'POST'])
def otp():
    next_url = request.args.get('next') or request.form.get('next', '')
    phone = session.get('pending_phone', '+919876543210')
    email = session.get('pending_email', 'demo@drishtiai.org')
    demo_allowed = is_demo_otp_allowed()
    demo_code = session.get('demo_otp_display', DEMO_OTP if demo_allowed else "")

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()
        verified, err_msg = otp_manager.verify_otp(phone, entered_otp)

        if verified:
            # Look up or create user
            if email and not session.get('pending_phone'):
                user = get_user_by_email(email)
                if not user:
                    user_id = create_or_update_user(session.get('pending_name', 'Clinician'), email=email, phone_number=phone)
                    user = get_user_by_id(user_id)
            else:
                user = get_or_create_user_by_phone(phone, full_name=session.get('pending_name'))

            # Clear session to prevent fixation before setting authenticated session
            session.clear()
            user_phone = user.get('mobile_number') or user.get('phone_number') or phone
            session['user_id'] = user['id']
            session['user'] = {
                'id': user['id'],
                'phone': user_phone,
                'mobile_number': user_phone,
                'masked_phone': mask_phone_number(user_phone),
                'email': user.get('email') or email,
                'name': user.get('full_name') or f"Screener {user_phone[-4:]}",
                'role': user.get('role', 'Clinician / Screener'),
                'is_guest': False,
                'auth_method': 'otp'
            }

            target = next_url if next_url and not next_url.startswith('/login') and not next_url.startswith('/otp') else url_for('dashboard')
            return redirect(target)
        else:
            otp_err = f"Invalid security OTP code. {err_msg}" if err_msg else "Invalid security OTP code. Please check the code and try again."
            return render_template(
                'otp.html',
                phone=phone,
                email=email,
                demo_otp=demo_code,
                error=otp_err,
                next_url=next_url
            )

    return render_template('otp.html', phone=phone, email=email, demo_otp=demo_code, next_url=next_url)

@app.route('/verify-otp', methods=['POST'])
def verify_otp_api():
    """API endpoint to verify an OTP code (supports JSON and form-encoded data)."""
    data = request.get_json(silent=True) or request.form or {}
    raw_phone = data.get('phone') or data.get('mobile_number') or session.get('pending_phone')
    entered_otp = data.get('otp') or data.get('code') or ''
    next_url = data.get('next', '')

    if not raw_phone:
        return jsonify({'success': False, 'error': 'Mobile number is required.'}), 400

    try:
        normalized = normalize_phone_number(raw_phone)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    verified, message = otp_manager.verify_otp(normalized, entered_otp)
    if not verified:
        return jsonify({'success': False, 'error': message}), 400

    user = get_or_create_user_by_phone(normalized, full_name=session.get('pending_name'))
    session.clear()
    user_phone = user.get('mobile_number') or user.get('phone_number') or normalized
    session['user_id'] = user['id']
    session['user'] = {
        'id': user['id'],
        'phone': user_phone,
        'mobile_number': user_phone,
        'masked_phone': mask_phone_number(user_phone),
        'email': user.get('email') or '',
        'name': user.get('full_name') or f"Screener {user_phone[-4:]}",
        'role': user.get('role', 'Clinician / Screener'),
        'is_guest': False,
        'auth_method': 'otp'
    }

    redirect_target = next_url if next_url and not next_url.startswith('/login') and not next_url.startswith('/otp') else url_for('dashboard')
    return jsonify({
        'success': True,
        'message': message,
        'redirect_url': redirect_target,
        'user': session['user']
    })

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    phone = session.get('pending_phone')
    if not phone:
        return jsonify({'success': False, 'error': 'Session expired. Please re-enter your mobile number.'}), 400

    client_ip = get_client_ip()
    success, message, demo_code = otp_manager.create_and_send_otp(phone, ip_address=client_ip)
    if not success:
        return jsonify({'success': False, 'error': message}), 429

    demo_allowed = is_demo_otp_allowed()
    if demo_allowed and demo_code:
        session['demo_otp_display'] = demo_code
    else:
        session.pop('demo_otp_display', None)

    resp_payload = {
        'success': True,
        'message': message
    }
    if demo_allowed:
        resp_payload['demo_otp'] = demo_code or DEMO_OTP
    return jsonify(resp_payload)

@app.route('/guest')
def guest():
    next_url = request.args.get('next', '')
    # Dedicated guest account isolating guest screenings from registered clinical users
    guest_token = secrets.token_hex(4)
    guest_phone = f"+9199999{int(guest_token, 16) % 90000 + 10000}"
    guest_user = get_or_create_user_by_phone(guest_phone, full_name='Guest Screener', role='Guest Clinician')

    session.clear()
    session['user_id'] = guest_user['id']
    session['user'] = {
        'id': guest_user['id'],
        'phone': guest_phone,
        'mobile_number': guest_phone,
        'masked_phone': mask_phone_number(guest_phone),
        'email': f"guest_{guest_token}@drishtiai.local",
        'name': 'Guest Screener',
        'role': 'Guest Clinician',
        'is_guest': True
    }
    target = next_url if next_url and not next_url.startswith('/login') and not next_url.startswith('/otp') else url_for('dashboard')
    return redirect(target)

@app.route('/logout')
def logout():
    session.clear()
    resp = redirect(url_for('login'))
    resp.delete_cookie(app.config.get('SESSION_COOKIE_NAME', 'session'))
    return resp

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.svg', mimetype='image/svg+xml')

@app.route('/health')
def health():
    """
    Lightweight health-check endpoint for Render and uptime monitoring.
    Returns 200 OK immediately without triggering heavy PyTorch model inference.
    """
    return jsonify({
        'status': 'healthy',
        'project': 'RETINA-XAI',
        'brand': 'DrishtiAI',
        'database': 'connected',
        'timestamp': datetime.now().isoformat()
    }), 200

# -------------------------------------------------------------------
# Clinical Views & Screening Pipeline
# -------------------------------------------------------------------

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

        current_user_id = session.get('user_id') or session.get('user', {}).get('id')

        # Generate unique Patient ID (e.g. RXT-2048)
        rand_num = random.randint(1020, 9999)
        patient_id = f"RXT-{rand_num}"

        # Unguessable file name using user prefix and cryptographic token
        file_token = secrets.token_hex(4)
        target_img_filename = f"u{current_user_id}_{file_token}_{patient_id}_fundus.jpg"
        target_img_path = os.path.join(UPLOAD_FOLDER, target_img_filename)
        rel_img_path = f"static/uploads/{target_img_filename}"

        if sample_name:
            # Using preloaded sample case via storage service
            storage_service.copy_sample(sample_name, target_img_filename)
        elif uploaded_file and uploaded_file.filename != '':
            if not allowed_file(uploaded_file.filename):
                return jsonify({'success': False, 'error': 'Please upload a valid JPG, JPEG, or PNG retinal fundus photograph.'}), 400
            storage_service.save_upload(uploaded_file, target_img_filename)
        else:
            return jsonify({'success': False, 'error': 'Please select or upload a retinal image before analysis.'}), 400

        # Validate retinal image domain & quality (Reject random non-retinal photos)
        t_val_start = time.perf_counter()
        validation = validate_retinal_image(target_img_path)
        t_val_elapsed = (time.perf_counter() - t_val_start) * 1000
        print(f"[RETINA-XAI TIMING] Validation: {t_val_elapsed:.1f}ms", flush=True)

        if not validation['is_valid_retina']:
            storage_service.delete_file(target_img_path)
            guidance = validation.get('guidance', 'Please upload a standard retinal fundus photograph.')
            return jsonify({
                'success': False,
                'is_invalid_image': True,
                'error': f"Invalid Image: {validation['reason']}. {guidance}",
                'reason': validation['reason'],
                'guidance': guidance,
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
        seg_prefix = f"u{current_user_id}_{file_token}_{patient_id}"
        seg_result = predict_retinal_segmentation(target_img_path, GENERATED_FOLDER, seg_prefix)
        t_seg_elapsed = (time.perf_counter() - t_seg_start) * 1000
        print(f"[RETINA-XAI TIMING] Segmentation: {t_seg_elapsed:.1f}ms", flush=True)

        # Persist to Database strictly associated with authenticated user_id
        add_screening(
            patient_id=patient_id,
            user_id=current_user_id,
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
            is_demo=0,  # User-created screenings are never shared demo samples
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
    current_user_id = session.get('user_id') or session.get('user', {}).get('id')

    screening_record = get_screening_by_id(screening_id)
    if not screening_record:
        return redirect(url_for('screening'))

    # Strict Ownership Check:
    # A user cannot access another user's record by tampering with the URL ID.
    # User B accessing User A's record MUST receive 403 Forbidden.
    # Only pre-seeded system demo cases (user_id == 1, patient_id starting with 'RXT-100', and is_demo == 1) are globally accessible.
    record_user_id = screening_record.get('user_id')
    is_preseeded_demo = (
        record_user_id == 1 and 
        str(screening_record.get('patient_id', '')).startswith('RXT-100') and 
        screening_record.get('is_demo') == 1
    )

    if record_user_id is not None and record_user_id != current_user_id and not is_preseeded_demo:
        return render_template_string("""
            {% extends "base.html" %}
            {% block content %}
            <div class="container py-5 text-center">
              <div class="alert alert-danger p-4 rounded-4 shadow-sm max-w-600 mx-auto">
                <i class="bi bi-shield-x text-danger fs-1 mb-2 d-block"></i>
                <h3 class="fw-bold">403 Forbidden — Access Denied</h3>
                <p class="text-muted">You do not have authorization to view this clinical screening record.</p>
                <a href="/history" class="btn btn-primary-custom mt-2">Return to My History</a>
              </div>
            </div>
            {% endblock %}
        """), 403

    return render_template('result.html', screening=screening_record, active_page='screening')

@app.route('/save-screening', methods=['POST'])
def save_screening():
    try:
        current_user_id = session.get('user_id') or session.get('user', {}).get('id')

        screening_id = request.form.get('screening_id')
        notes = request.form.get('notes', '').strip()
        referral_required = int(request.form.get('referral_required', 0))

        if not screening_id:
            return jsonify({'success': False, 'error': 'Missing screening ID'}), 400

        # Verify ownership before updating
        existing = get_screening_by_id(screening_id)
        if not existing:
            return jsonify({'success': False, 'error': 'Screening record not found.'}), 404

        record_user_id = existing.get('user_id')
        if record_user_id is not None and record_user_id != current_user_id:
            return jsonify({'success': False, 'error': 'Unauthorized to modify this screening record.'}), 403

        update_screening_notes(screening_id, notes, referral_required, user_id=record_user_id)
        return jsonify({'success': True, 'message': 'Screening record updated successfully.'})
    except Exception as e:
        print(f"[ERROR in /save-screening]: {e}", flush=True)
        return jsonify({'success': False, 'error': 'Unable to save screening. Please try again.'}), 500

@app.route('/dashboard')
def dashboard():
    current_user_id = session.get('user_id') or session.get('user', {}).get('id')
    stats = get_dashboard_statistics(user_id=current_user_id)
    return render_template('dashboard.html', stats=stats, active_page='dashboard')

@app.route('/history')
def history():
    current_user_id = session.get('user_id') or session.get('user', {}).get('id')
    class_filter = request.args.get('class_filter', 'all')
    search_query = request.args.get('q', '').strip()
    screenings = get_user_screenings(user_id=current_user_id, filter_class=class_filter, search_query=search_query)
    return render_template(
        'history.html',
        screenings=screenings,
        current_filter=class_filter,
        search_query=search_query,
        active_page='history'
    )

@app.route('/export-history-csv')
def export_history_csv():
    """
    Downloads a CSV file containing ONLY the authenticated user's screening history.
    """
    current_user_id = session.get('user_id') or session.get('user', {}).get('id')
    screenings = get_user_screenings(user_id=current_user_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Patient ID', 'Date & Time', 'Severity Grade',
        'Diagnosis', 'Confidence (%)', 'Referral Required', 'Notes'
    ])

    for s in screenings:
        writer.writerow([
            s.get('patient_id', ''),
            s.get('created_at', ''),
            s.get('class_id', 0),
            s.get('prediction', ''),
            s.get('confidence', 0),
            'Yes' if s.get('referral_required') == 1 else 'No',
            s.get('notes', '').replace('\n', ' ')
        ])

    csv_data = output.getvalue()
    filename = f"drishtiai_screenings_user_{current_user_id}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route('/about')
def about():
    return render_template('about.html', active_page='about')

# -------------------------------------------------------------------
# Chatbot & Public API Endpoints
# -------------------------------------------------------------------

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """
    DrishtiAI Assistant Chatbot API.
    Protected by session authentication and bounded by medical guardrails.
    """
    try:
        data = request.get_json() or {}
        message = data.get('message', '').strip()
        lang = data.get('lang', 'en').strip()

        current_user_id = session.get('user_id') or session.get('user', {}).get('id')

        res = chatbot_service.handle_message(
            user_message=message,
            user_id=current_user_id,
            lang=lang
        )

        return jsonify({
            'success': True,
            'reply': res['reply'],
            'mode': res['mode'],
            'is_medical_warning': res.get('is_medical_warning', False),
            'detected_lang': res.get('detected_lang', lang)
        })
    except Exception as e:
        logger_err = str(e)
        print(f"[ERROR in /api/chat]: {logger_err}", flush=True)
        return jsonify({'success': False, 'error': 'Assistant is temporarily busy. Please retry.'}), 500

@app.route('/api/dashboard')
def api_dashboard():
    current_user_id = session.get('user_id') or session.get('user', {}).get('id')
    return jsonify(get_dashboard_statistics(user_id=current_user_id))

@app.route('/api/history')
def api_history():
    current_user_id = session.get('user_id') or session.get('user', {}).get('id')
    screenings = get_user_screenings(user_id=current_user_id)
    return jsonify(screenings)

# -------------------------------------------------------------------
# Error Handlers
# -------------------------------------------------------------------

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
