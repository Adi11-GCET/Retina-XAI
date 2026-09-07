import unittest
import json
import time
from app import app
from utils.database import (
    init_db, get_db_connection, get_or_create_user_by_phone,
    add_screening, get_screening_by_id, get_user_screenings,
    get_dashboard_statistics
)
from services.otp_service import (
    normalize_phone_number, otp_manager, DEMO_OTP, hash_otp
)
from services.chatbot_service import chatbot_service

class UpgradeTestSuite(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Ensure database is initialized
        init_db()

        # Seed User A & User B
        self.user_a = get_or_create_user_by_phone('+919111111111', full_name='User Alpha', role='Ophthalmologist')
        self.user_b = get_or_create_user_by_phone('+919222222222', full_name='User Beta', role='Community Health Worker')
        from utils.database import execute_query
        execute_query("DELETE FROM screenings WHERE user_id IN (?, ?)", (self.user_a['id'], self.user_b['id']), commit=True)

    # =================================================================
    # 1. AUTHENTICATION & MOBILE OTP TESTS
    # =================================================================

    def test_phone_number_normalization(self):
        """Test Indian and international phone number normalization."""
        self.assertEqual(normalize_phone_number('9876543210'), '+919876543210')
        self.assertEqual(normalize_phone_number('+91 98765 43210'), '+919876543210')
        self.assertEqual(normalize_phone_number('09876543210'), '+919876543210')
        self.assertEqual(normalize_phone_number('919876543210'), '+919876543210')

        with self.assertRaises(ValueError):
            normalize_phone_number('12345')
        with self.assertRaises(ValueError):
            normalize_phone_number('')

    def test_otp_generation_and_verification_flow(self):
        """Test OTP generation, verification, and wrong OTP rejection."""
        test_phone = '+919333333333'
        ok, msg, code = otp_manager.create_and_send_otp(test_phone)
        self.assertTrue(ok)

        # Reject invalid format
        v_bad_format, _ = otp_manager.verify_otp(test_phone, '123')
        self.assertFalse(v_bad_format)

        # Reject wrong OTP
        v_wrong, wrong_msg = otp_manager.verify_otp(test_phone, '000000')
        self.assertFalse(v_wrong)
        self.assertIn('attempt', wrong_msg)

        # Accept correct generated OTP
        v_correct, _ = otp_manager.verify_otp(test_phone, code)
        self.assertTrue(v_correct)

    def test_demo_otp_code(self):
        """Verify standard DEMO_OTP works for demonstration mode."""
        test_phone = '+919876543210'
        v_demo, _ = otp_manager.verify_otp(test_phone, DEMO_OTP)
        self.assertTrue(v_demo)

    def test_otp_resend_cooldown(self):
        """Ensure 60-second cooldown is enforced on OTP resend."""
        test_phone = '+919444444444'
        ok1, _, _ = otp_manager.create_and_send_otp(test_phone)
        self.assertTrue(ok1)

        # Immediate resend should be blocked by cooldown
        ok2, msg2, _ = otp_manager.create_and_send_otp(test_phone)
        self.assertFalse(ok2)
        self.assertIn('wait', msg2.lower())

    def test_login_flow_via_http(self):
        """Test HTTP POST /login followed by /otp verification creates session."""
        client = app.test_client()
        # Request OTP
        login_res = client.post('/login', data={'phone': '9555555555'})
        self.assertEqual(login_res.status_code, 302)
        self.assertIn('/otp', login_res.headers.get('Location', ''))

        # Verify OTP
        otp_res = client.post('/otp', data={'otp': DEMO_OTP})
        self.assertEqual(otp_res.status_code, 302)
        self.assertIn('/dashboard', otp_res.headers.get('Location', ''))

        with client.session_transaction() as sess:
            self.assertIn('user', sess)
            self.assertEqual(sess['user']['phone'], '+919555555555')
            self.assertFalse(sess['user']['is_guest'])

    def test_logout_clears_session(self):
        """Test /logout completely removes user session."""
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user'] = {'id': self.user_a['id'], 'name': 'User Alpha'}
        logout_res = client.get('/logout')
        self.assertEqual(logout_res.status_code, 302)
        with client.session_transaction() as sess:
            self.assertNotIn('user', sess)

    def test_protected_routes_require_auth(self):
        """Ensure protected routes redirect to login when unauthenticated."""
        fresh = app.test_client()
        for path in ['/screening', '/dashboard', '/history']:
            res = fresh.get(path)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/login', res.headers.get('Location', ''))

        # API endpoints should return 401 JSON
        api_res = fresh.post('/predict')
        self.assertEqual(api_res.status_code, 401)
        api_chat_res = fresh.post('/api/chat', json={'message': 'hello'})
        self.assertEqual(api_chat_res.status_code, 401)

    # =================================================================
    # 2. STRICT USER ISOLATION TESTS
    # =================================================================

    def test_user_history_and_dashboard_isolation(self):
        """
        User A creates a screening, User B creates a screening.
        User A must only see A's screening; User B must only see B's screening.
        """
        # Create screening for User A
        scr_a_id = f"RXT-A{int(time.time()*10)%10000}"
        add_screening(
            patient_id=scr_a_id, user_id=self.user_a['id'],
            image_path='static/samples/sample_mild.jpg',
            heatmap_path='static/samples/sample_mild_heatmap.jpg',
            overlay_path='static/samples/sample_mild_overlay.jpg',
            prediction='Mild Diabetic Retinopathy', class_id=1, confidence=88.5,
            probabilities=[5.0, 88.5, 4.0, 2.0, 0.5], risk_status='Mild observation',
            notes='Patient A clinical notes'
        )

        # Create screening for User B
        scr_b_id = f"RXT-B{int(time.time()*10)%10000}"
        add_screening(
            patient_id=scr_b_id, user_id=self.user_b['id'],
            image_path='static/samples/sample_severe.jpg',
            heatmap_path='static/samples/sample_severe_heatmap.jpg',
            overlay_path='static/samples/sample_severe_overlay.jpg',
            prediction='Severe Diabetic Retinopathy', class_id=3, confidence=94.2,
            probabilities=[1.0, 2.0, 2.0, 94.2, 0.8], risk_status='Urgent referral',
            referral_required=1, notes='Patient B clinical notes'
        )

        # 1. Database layer verification
        a_records = get_user_screenings(user_id=self.user_a['id'])
        a_patient_ids = [r['patient_id'] for r in a_records]
        self.assertIn(scr_a_id, a_patient_ids)
        self.assertNotIn(scr_b_id, a_patient_ids)

        b_records = get_user_screenings(user_id=self.user_b['id'])
        b_patient_ids = [r['patient_id'] for r in b_records]
        self.assertIn(scr_b_id, b_patient_ids)
        self.assertNotIn(scr_a_id, b_patient_ids)

        # 2. HTTP History route verification for User A
        client_a = app.test_client()
        with client_a.session_transaction() as sess:
            sess['user'] = {'id': self.user_a['id'], 'name': 'User Alpha'}
        res_a = client_a.get('/history')
        self.assertEqual(res_a.status_code, 200)
        self.assertIn(scr_a_id.encode('utf-8'), res_a.data)
        self.assertNotIn(scr_b_id.encode('utf-8'), res_a.data)

        # 3. HTTP History route verification for User B
        client_b = app.test_client()
        with client_b.session_transaction() as sess:
            sess['user'] = {'id': self.user_b['id'], 'name': 'User Beta'}
        res_b = client_b.get('/history')
        self.assertEqual(res_b.status_code, 200)
        self.assertIn(scr_b_id.encode('utf-8'), res_b.data)
        self.assertNotIn(scr_a_id.encode('utf-8'), res_b.data)

        # 4. User B attempts to access User A's screening result by tampering with URL ID
        tamper_res = client_b.get(f'/result/{scr_a_id}')
        self.assertEqual(tamper_res.status_code, 403)
        self.assertIn(b'Access Denied', tamper_res.data)

        # 5. User A accesses own record -> 200 OK
        valid_res = client_a.get(f'/result/{scr_a_id}')
        self.assertEqual(valid_res.status_code, 200)

        # 6. User B attempts to edit User A's record via /save-screening -> 403 Forbidden
        save_tamper = client_b.post('/save-screening', data={'screening_id': scr_a_id, 'notes': 'Hacked'})
        self.assertEqual(save_tamper.status_code, 403)

        # 7. Dashboard statistics isolation
        stats_a = get_dashboard_statistics(user_id=self.user_a['id'])
        stats_b = get_dashboard_statistics(user_id=self.user_b['id'])
        self.assertGreaterEqual(stats_a['mild'], 1)
        self.assertEqual(stats_a['severe'], 0)
        self.assertGreaterEqual(stats_b['severe'], 1)
        self.assertEqual(stats_b['mild'], 0)

    def test_csv_export_is_user_specific(self):
        """Ensure /export-history-csv returns only the authenticated user's records."""
        scr_id = f"RXT-CSV{int(time.time()*10)%10000}"
        add_screening(
            patient_id=scr_id, user_id=self.user_a['id'],
            image_path='static/samples/sample_no_dr.jpg',
            heatmap_path='static/samples/sample_no_dr_heatmap.jpg',
            overlay_path='static/samples/sample_no_dr_overlay.jpg',
            prediction='No Diabetic Retinopathy', class_id=0, confidence=97.0,
            probabilities=[97.0, 1.0, 1.0, 0.5, 0.5], risk_status='Normal'
        )

        client_a = app.test_client()
        with client_a.session_transaction() as sess:
            sess['user'] = {'id': self.user_a['id'], 'name': 'User Alpha'}
        res = client_a.get('/export-history-csv')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/csv')
        csv_text = res.data.decode('utf-8')
        self.assertIn(scr_id, csv_text)

        # User B should NOT have User A's ID in CSV
        client_b = app.test_client()
        with client_b.session_transaction() as sess:
            sess['user'] = {'id': self.user_b['id'], 'name': 'User Beta'}
        res_b = client_b.get('/export-history-csv')
        self.assertNotIn(scr_id, res_b.data.decode('utf-8'))

    # =================================================================
    # 3. DRISHTIAI ASSISTANT CHATBOT TESTS
    # =================================================================

    def test_chatbot_faq_fallback(self):
        """Verify chatbot returns safe educational FAQ responses without external API key."""
        res_en = chatbot_service.handle_message("What is diabetic retinopathy?")
        self.assertEqual(res_en['mode'], 'faq')
        self.assertIn("Diabetic Retinopathy", res_en['reply'])
        self.assertFalse(res_en['is_medical_warning'])

        res_hi = chatbot_service.handle_message("डायबिटिक रेटिनोपैथी क्या है?", lang='hi')
        self.assertEqual(res_hi['mode'], 'faq')
        self.assertIn("रेटिना", res_hi['reply'])

    def test_chatbot_medical_safety_guardrails(self):
        """Ensure red-flag urgent symptoms trigger emergency referral warning."""
        res = chatbot_service.handle_message("I am experiencing sudden vision loss and severe eye pain")
        self.assertTrue(res['is_medical_warning'])
        self.assertIn("URGENT MEDICAL NOTICE", res['reply'])
        self.assertIn("emergency", res['reply'].lower())

    def test_chatbot_refuses_direct_diagnosis(self):
        """Ensure chatbot does not diagnose or prescribe."""
        res = chatbot_service.handle_message("Diagnose me and give me eye drops for my infection")
        self.assertIn("does not diagnose", res['reply'].lower())

    def test_chatbot_explain_my_result(self):
        """Test 'Explain my result' retrieves only authenticated user's latest screening."""
        scr_id = f"RXT-EX{int(time.time()*10)%10000}"
        add_screening(
            patient_id=scr_id, user_id=self.user_a['id'],
            image_path='static/samples/sample_moderate.jpg',
            heatmap_path='static/samples/sample_moderate_heatmap.jpg',
            overlay_path='static/samples/sample_moderate_overlay.jpg',
            prediction='Moderate Diabetic Retinopathy', class_id=2, confidence=91.5,
            probabilities=[1.0, 3.0, 91.5, 3.0, 1.5], risk_status='Referral advisory',
            referral_required=1
        )

        res = chatbot_service.handle_message("Explain my latest result", user_id=self.user_a['id'])
        self.assertIn(scr_id, res['reply'])
        self.assertIn("Moderate Diabetic Retinopathy", res['reply'])
        self.assertIn("Grade 2", res['reply'])

    def test_chatbot_http_endpoint(self):
        """Test POST /api/chat endpoint with session."""
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user'] = {'id': self.user_a['id'], 'name': 'User Alpha'}
        res = client.post('/api/chat', json={'message': 'How does Grad-CAM work?', 'lang': 'en'})
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn("Grad-CAM", data['reply'])

    # =================================================================
    # 4. HEALTH CHECK & RESOURCE OPTIMIZATION
    # =================================================================

    def test_health_endpoint(self):
        """Verify /health returns 200 OK without triggering heavy inference."""
        res = self.app.get('/health')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['project'], 'RETINA-XAI')
        self.assertEqual(data['brand'], 'DrishtiAI')
        self.assertEqual(data['database'], 'connected')

if __name__ == '__main__':
    unittest.main()
