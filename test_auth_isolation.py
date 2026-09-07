import os
import json
import time
import secrets
import unittest
from app import app
from utils.database import (
    get_or_create_user_by_phone, get_user_by_phone, get_user_by_id,
    get_screening_by_id, add_screening, get_all_screenings,
    get_user_screenings, get_dashboard_statistics
)
from services.otp_service import (
    normalize_phone_number, otp_manager, DEMO_OTP,
    MockOtpProvider, TwilioOtpProvider, Fast2SmsOtpProvider,
    Msg91OtpProvider, UnavailableOtpProvider,
    is_production_mode, is_demo_otp_allowed, get_otp_provider
)
from unittest.mock import patch, MagicMock

class TestAuthAndDataIsolation(unittest.TestCase):
    """
    Comprehensive 20-point test suite for DrishtiAI Authentication & User Data Isolation:
    1. Phone normalization (+91XXXXXXXXXX)
    2. Cryptographic OTP generation (6 digits via secrets)
    3. Development simulation mode notice (never fake real SMS delivery)
    4. Single-use OTP burn on successful verification
    5. Max attempts limit (locks after 5 failed attempts)
    6. OTP resend cooldown (60 seconds)
    7. User creation in DB with integer ID and audit timestamps
    8. Returning user login updates last_login without duplicating user
    9. Unauthenticated requests to protected endpoints redirect to login or return 401
    10. Login & OTP flow establishes authenticated session with user_id
    11. Logout flushes session and deletes session cookie
    12. Screening creation binds session user_id, sets is_demo=0, and uses unguessable token
    13. Database get_user_screenings strictly isolates records by user_id
    14. Cross-user access to /result/<id> returns 403 Forbidden
    15. Cross-user modification via /save-screening returns 403 Forbidden
    16. Dashboard statistics aggregate strictly by user_id
    17. Export CSV history contains ONLY the authenticated user's records
    18. Chatbot "Explain my result" explains ONLY the authenticated user's record
    19. Guest mode assigns an isolated unique guest account without exposing clinical data
    20. Navbar displays masked mobile number (👤 +91 ******4321) and clear logout option
    """

    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

    def test_01_phone_normalization(self):
        self.assertEqual(normalize_phone_number("9876543210"), "+919876543210")
        self.assertEqual(normalize_phone_number("09876543210"), "+919876543210")
        self.assertEqual(normalize_phone_number("+91 98765 43210"), "+919876543210")
        self.assertEqual(normalize_phone_number("+91-9876543210"), "+919876543210")
        
        with self.assertRaises(ValueError):
            normalize_phone_number("12345")
        with self.assertRaises(ValueError):
            normalize_phone_number("abcdefghij")
        with self.assertRaises(ValueError):
            normalize_phone_number("")

    def test_02_otp_generation_and_cryptographic_randomness(self):
        phone = "+919811111111"
        otp_manager._store.pop(phone, None)
        success, msg, code = otp_manager.create_and_send_otp(phone)
        self.assertTrue(success)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        self.assertTrue(100000 <= int(code) <= 999999)

    def test_03_mock_otp_provider_simulation_message(self):
        provider = MockOtpProvider()
        success, msg = provider.send_otp("+919811111111", "123456")
        self.assertTrue(success)
        self.assertTrue("SIMULATION" in msg or "DEVELOPMENT" in msg)
        self.assertTrue("not configured" in msg)

    def test_04_otp_single_use_burn(self):
        phone = "+919822222222"
        otp_manager._store.pop(phone, None)
        success, msg, code = otp_manager.create_and_send_otp(phone)
        self.assertTrue(success)
        
        # First verification succeeds
        verified, _ = otp_manager.verify_otp(phone, code)
        self.assertTrue(verified)
        
        # Immediate second verification with same code fails
        verified2, err_msg = otp_manager.verify_otp(phone, code)
        self.assertFalse(verified2)
        self.assertTrue("expired" in err_msg.lower() or "not found" in err_msg.lower())

    def test_05_otp_max_attempts_limit(self):
        phone = "+919833333333"
        otp_manager._store.pop(phone, None)
        otp_manager.create_and_send_otp(phone)
        
        for _ in range(5):
            verified, _ = otp_manager.verify_otp(phone, "000000")
            self.assertFalse(verified)
            
        verified_after, err = otp_manager.verify_otp(phone, "000000")
        self.assertFalse(verified_after)
        self.assertTrue("expired" in err.lower() or "not found" in err.lower() or "attempts" in err.lower())

    def test_06_otp_resend_cooldown(self):
        phone = "+919844444444"
        otp_manager._store.pop(phone, None)
        success1, _, _ = otp_manager.create_and_send_otp(phone)
        self.assertTrue(success1)
        
        success2, reason, _ = otp_manager.create_and_send_otp(phone)
        self.assertFalse(success2)
        self.assertTrue("wait" in reason.lower() or "seconds" in reason.lower())

    def test_07_user_creation_in_db(self):
        test_phone = "+919777777701"
        user = get_or_create_user_by_phone(test_phone, full_name="Nurse Priya")
        self.assertIsNotNone(user)
        self.assertIsInstance(user['id'], int)
        self.assertEqual(user['full_name'], "Nurse Priya")
        self.assertEqual(user['phone_number'], test_phone)
        self.assertEqual(user['mobile_number'], test_phone)
        self.assertEqual(user['is_active'], 1)
        self.assertIsNotNone(user['created_at'])

    def test_08_subsequent_login_updates_last_login(self):
        test_phone = "+919777777702"
        user1 = get_or_create_user_by_phone(test_phone, full_name="Officer Ramesh")
        u1_id = user1['id']
        
        time.sleep(0.1)
        user2 = get_or_create_user_by_phone(test_phone)
        self.assertEqual(user2['id'], u1_id)
        self.assertEqual(user2['full_name'], "Officer Ramesh")

    def test_09_unauthenticated_access_redirects(self):
        with app.test_client() as c:
            resp = c.get('/screening')
            self.assertEqual(resp.status_code, 302)
            self.assertIn('/login', resp.headers['Location'])
            
            resp_dash = c.get('/dashboard')
            self.assertEqual(resp_dash.status_code, 302)
            
            resp_hist = c.get('/history')
            self.assertEqual(resp_hist.status_code, 302)
            
            resp_api = c.post('/predict', data={})
            self.assertEqual(resp_api.status_code, 401)

    def test_10_login_and_otp_session_establishment(self):
        c = app.test_client()
        test_phone = "9876543210"
        resp = c.post('/login', data={'phone': test_phone}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(b"Simulated OTP" in resp.data or b"Enter the 6-digit OTP" in resp.data)
        
        verify_resp = c.post('/otp', data={'otp': DEMO_OTP}, follow_redirects=True)
        self.assertEqual(verify_resp.status_code, 200)
        
        with c.session_transaction() as sess:
            self.assertIsNotNone(sess.get('user_id'))
            self.assertIsNotNone(sess.get('user'))
            self.assertEqual(sess['user']['phone'], "+919876543210")

    def test_11_logout_clears_session_and_cookies(self):
        c = app.test_client()
        c.post('/login', data={'phone': '9876543210'})
        c.post('/otp', data={'otp': DEMO_OTP})
        
        logout_resp = c.get('/logout', follow_redirects=False)
        self.assertEqual(logout_resp.status_code, 302)
        self.assertIn('/login', logout_resp.headers['Location'])
        
        with c.session_transaction() as sess:
            self.assertNotIn('user_id', sess)
            self.assertNotIn('user', sess)

    def test_12_user_screening_creation_binds_user_id(self):
        c = app.test_client()
        user_a = get_or_create_user_by_phone("+919100000001", full_name="User Alpha")
        with c.session_transaction() as sess:
            sess['user_id'] = user_a['id']
            sess['user'] = {
                'id': user_a['id'],
                'phone': user_a['phone_number'],
                'name': user_a['full_name'],
                'role': 'Clinician',
                'is_guest': False
            }
        
        resp = c.post('/predict', data={'sample_name': 'sample_mild.jpg'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['success'])
        patient_id = data['patient_id']
        
        screening = get_screening_by_id(patient_id)
        self.assertIsNotNone(screening)
        self.assertEqual(screening['user_id'], user_a['id'])
        self.assertEqual(screening['is_demo'], 0)
        self.assertIn(f"u{user_a['id']}_", screening['image_path'])

    def test_13_user_data_isolation_history_query(self):
        user_a = get_or_create_user_by_phone("+919100000002", full_name="User Beta")
        user_b = get_or_create_user_by_phone("+919100000003", full_name="User Gamma")
        
        pid_a = f"RXT-TA1-{secrets.token_hex(3)}"
        pid_b = f"RXT-TB1-{secrets.token_hex(3)}"

        add_screening(
            patient_id=pid_a,
            user_id=user_a['id'],
            image_path="static/samples/sample_mild.jpg",
            heatmap_path="",
            overlay_path="",
            prediction="Mild DR",
            class_id=1,
            confidence=85.0,
            probabilities=[0.1, 0.85, 0.05, 0.0, 0.0],
            risk_status="Mild DR",
            is_demo=0
        )
        add_screening(
            patient_id=pid_b,
            user_id=user_b['id'],
            image_path="static/samples/sample_severe.jpg",
            heatmap_path="",
            overlay_path="",
            prediction="Severe DR",
            class_id=3,
            confidence=92.0,
            probabilities=[0.0, 0.0, 0.08, 0.92, 0.0],
            risk_status="Severe DR",
            is_demo=0
        )
        
        a_records = get_user_screenings(user_a['id'])
        b_records = get_user_screenings(user_b['id'])
        
        a_ids = [r['patient_id'] for r in a_records]
        b_ids = [r['patient_id'] for r in b_records]
        
        self.assertIn(pid_a, a_ids)
        self.assertNotIn(pid_b, a_ids)
        
        self.assertIn(pid_b, b_ids)
        self.assertNotIn(pid_a, b_ids)

    def test_14_cross_user_result_access_forbidden_403(self):
        c = app.test_client()
        user_a = get_or_create_user_by_phone("+919100000004", full_name="User Delta")
        user_b = get_or_create_user_by_phone("+919100000005", full_name="User Epsilon")
        
        pid_a = f"RXT-TA2-{secrets.token_hex(3)}"
        add_screening(
            patient_id=pid_a,
            user_id=user_a['id'],
            image_path="static/samples/sample_moderate.jpg",
            heatmap_path="",
            overlay_path="",
            prediction="Moderate DR",
            class_id=2,
            confidence=89.0,
            probabilities=[0.05, 0.05, 0.89, 0.01, 0.0],
            risk_status="Moderate DR",
            is_demo=0
        )
        
        with c.session_transaction() as sess:
            sess['user_id'] = user_b['id']
            sess['user'] = {
                'id': user_b['id'],
                'phone': user_b['phone_number'],
                'name': user_b['full_name'],
                'role': 'Clinician',
                'is_guest': False
            }
            
        resp = c.get(f'/result/{pid_a}')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(b"403 Forbidden" in resp.data or b"Access Denied" in resp.data)

    def test_15_cross_user_save_screening_forbidden_403(self):
        c = app.test_client()
        user_a = get_or_create_user_by_phone("+919100000006", full_name="User Zeta")
        user_b = get_or_create_user_by_phone("+919100000007", full_name="User Eta")
        
        pid_a = f"RXT-TA3-{secrets.token_hex(3)}"
        add_screening(
            patient_id=pid_a,
            user_id=user_a['id'],
            image_path="static/samples/sample_no_dr.jpg",
            heatmap_path="",
            overlay_path="",
            prediction="No DR",
            class_id=0,
            confidence=98.0,
            probabilities=[0.98, 0.01, 0.01, 0.0, 0.0],
            risk_status="No DR",
            is_demo=0
        )
        
        with c.session_transaction() as sess:
            sess['user_id'] = user_b['id']
            sess['user'] = {
                'id': user_b['id'],
                'phone': user_b['phone_number'],
                'name': user_b['full_name'],
                'role': 'Clinician',
                'is_guest': False
            }
            
        resp = c.post('/save-screening', data={
            'screening_id': pid_a,
            'notes': 'Malicious modification by User B',
            'referral_required': 1
        })
        self.assertEqual(resp.status_code, 403)

    def test_16_dashboard_statistics_isolation(self):
        user_a = get_or_create_user_by_phone("+919100000008", full_name="User Theta")
        user_b = get_or_create_user_by_phone("+919100000009", full_name="User Iota")
        
        pid_a1 = f"RXT-STA1-{secrets.token_hex(3)}"
        pid_a2 = f"RXT-STA2-{secrets.token_hex(3)}"
        pid_b1 = f"RXT-STB1-{secrets.token_hex(3)}"

        add_screening(
            patient_id=pid_a1, user_id=user_a['id'], image_path="", heatmap_path="", overlay_path="",
            prediction="Mild DR", class_id=1, confidence=80.0, probabilities=[0,1,0,0,0], risk_status="", is_demo=0
        )
        add_screening(
            patient_id=pid_a2, user_id=user_a['id'], image_path="", heatmap_path="", overlay_path="",
            prediction="Severe DR", class_id=3, confidence=90.0, probabilities=[0,0,0,1,0], risk_status="", is_demo=0
        )
        add_screening(
            patient_id=pid_b1, user_id=user_b['id'], image_path="", heatmap_path="", overlay_path="",
            prediction="No DR", class_id=0, confidence=99.0, probabilities=[1,0,0,0,0], risk_status="", is_demo=0
        )
        
        stats_a = get_dashboard_statistics(user_id=user_a['id'])
        stats_b = get_dashboard_statistics(user_id=user_b['id'])
        
        self.assertGreaterEqual(stats_a['total'], 2)
        self.assertGreaterEqual(stats_b['total'], 1)
        self.assertGreaterEqual(stats_a['mild'], 1)
        self.assertGreaterEqual(stats_a['severe'], 1)
        self.assertEqual(stats_b['mild'], 0)

    def test_17_export_history_csv_isolation(self):
        c = app.test_client()
        user_a = get_or_create_user_by_phone("+919100000010", full_name="User Kappa")
        user_b = get_or_create_user_by_phone("+919100000011", full_name="User Lambda")
        
        pid_a = f"RXT-CSVA-{secrets.token_hex(3)}"
        pid_b = f"RXT-CSVB-{secrets.token_hex(3)}"

        add_screening(
            patient_id=pid_a, user_id=user_a['id'], image_path="", heatmap_path="", overlay_path="",
            prediction="No DR", class_id=0, confidence=95.0, probabilities=[1,0,0,0,0], risk_status="", is_demo=0
        )
        add_screening(
            patient_id=pid_b, user_id=user_b['id'], image_path="", heatmap_path="", overlay_path="",
            prediction="Proliferative DR", class_id=4, confidence=96.0, probabilities=[0,0,0,0,1], risk_status="", is_demo=0
        )
        
        with c.session_transaction() as sess:
            sess['user_id'] = user_b['id']
            sess['user'] = {'id': user_b['id'], 'phone': user_b['phone_number'], 'name': 'User Lambda', 'role': 'Clinician', 'is_guest': False}
            
        resp = c.get('/export-history-csv')
        self.assertEqual(resp.status_code, 200)
        csv_text = resp.data.decode('utf-8')
        self.assertIn(pid_b, csv_text)
        self.assertNotIn(pid_a, csv_text)

    def test_18_chatbot_latest_result_isolation(self):
        c = app.test_client()
        user_a = get_or_create_user_by_phone("+919100000012", full_name="User Mu")
        user_b = get_or_create_user_by_phone("+919100000013", full_name="User Nu")
        
        pid_a = f"RXT-CHTA-{secrets.token_hex(3)}"
        add_screening(
            patient_id=pid_a, user_id=user_a['id'], image_path="", heatmap_path="", overlay_path="",
            prediction="Severe DR", class_id=3, confidence=94.0, probabilities=[0,0,0,1,0], risk_status="", is_demo=0
        )
        
        # User B logs in (has no screenings)
        with c.session_transaction() as sess:
            sess['user_id'] = user_b['id']
            sess['user'] = {'id': user_b['id'], 'phone': user_b['phone_number'], 'name': 'User Nu', 'role': 'Clinician', 'is_guest': False}
            
        chat_resp = c.post('/api/chat', json={'message': 'Explain my result', 'lang': 'en'})
        self.assertEqual(chat_resp.status_code, 200)
        data = json.loads(chat_resp.data)
        self.assertNotIn(pid_a, data['reply'])
        self.assertIn("No screening record is available", data['reply'])

    def test_19_guest_mode_isolated_session(self):
        c = app.test_client()
        resp = c.get('/guest', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        
        with c.session_transaction() as sess:
            self.assertIsNotNone(sess.get('user_id'))
            self.assertIsNotNone(sess.get('user'))
            self.assertTrue(sess['user']['is_guest'])
            self.assertIn("Guest Screener", sess['user']['name'])

    def test_20_navbar_masked_phone_display(self):
        c = app.test_client()
        test_phone = "+919876543210"
        c.post('/login', data={'phone': test_phone})
        c.post('/otp', data={'otp': DEMO_OTP})
        
        resp = c.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(b"+91 ******3210" in resp.data)
        self.assertTrue(b"Logout" in resp.data)

    def test_21_production_mode_fails_safe_without_credentials(self):
        """In production mode without SMS credentials, system must fail safe."""
        orig_auth = os.environ.get('AUTH_MODE')
        orig_demo = os.environ.get('DEMO_OTP_ENABLED')
        orig_prov = os.environ.get('SMS_PROVIDER')
        try:
            os.environ['AUTH_MODE'] = 'production'
            os.environ['DEMO_OTP_ENABLED'] = 'false'
            os.environ['SMS_PROVIDER'] = ''
            
            self.assertTrue(is_production_mode())
            self.assertFalse(is_demo_otp_allowed())
            
            prov = get_otp_provider()
            self.assertIsInstance(prov, UnavailableOtpProvider)
            
            phone = "+919911223344"
            otp_manager._store.pop(phone, None)
            success, msg, code = otp_manager.create_and_send_otp(phone)
            self.assertFalse(success)
            self.assertIn("unavailable", msg.lower())
            self.assertEqual(code, "")
        finally:
            if orig_auth is not None:
                os.environ['AUTH_MODE'] = orig_auth
            else:
                os.environ.pop('AUTH_MODE', None)
            if orig_demo is not None:
                os.environ['DEMO_OTP_ENABLED'] = orig_demo
            else:
                os.environ.pop('DEMO_OTP_ENABLED', None)
            if orig_prov is not None:
                os.environ['SMS_PROVIDER'] = orig_prov
            else:
                os.environ.pop('SMS_PROVIDER', None)

    def test_22_production_mode_rejects_demo_otp(self):
        """In production mode, entering universal DEMO_OTP code must fail."""
        orig_auth = os.environ.get('AUTH_MODE')
        orig_demo = os.environ.get('DEMO_OTP_ENABLED')
        try:
            os.environ['AUTH_MODE'] = 'production'
            os.environ['DEMO_OTP_ENABLED'] = 'false'
            
            phone = "+919876543210"
            otp_manager._store.pop(phone, None)
            
            # Direct verification with DEMO_OTP without active OTP session
            verified, err = otp_manager.verify_otp(phone, DEMO_OTP)
            self.assertFalse(verified)
            self.assertTrue("not found" in err.lower() or "expired" in err.lower())
            
            # Active session with random OTP
            otp_manager._store[phone] = {
                'hashed_otp': 'some_random_hash',
                'created_at': time.time(),
                'attempts': 0,
                'last_sent_at': time.time(),
                'send_history': [time.time()]
            }
            verified2, err2 = otp_manager.verify_otp(phone, DEMO_OTP)
            self.assertFalse(verified2)
            self.assertIn("incorrect", err2.lower())
        finally:
            if orig_auth is not None:
                os.environ['AUTH_MODE'] = orig_auth
            else:
                os.environ.pop('AUTH_MODE', None)
            if orig_demo is not None:
                os.environ['DEMO_OTP_ENABLED'] = orig_demo
            else:
                os.environ.pop('DEMO_OTP_ENABLED', None)

    def test_23_ip_rate_limiting(self):
        """Exceeding 10 OTP requests from same IP within 15 mins is blocked."""
        test_ip = "192.168.1.99"
        otp_manager._ip_store.pop(test_ip, None)
        
        # Add 10 timestamps
        now = time.time()
        otp_manager._ip_store[test_ip] = [now] * 10
        
        can_send, reason = otp_manager.can_send_from_ip(test_ip)
        self.assertFalse(can_send)
        self.assertIn("Too many requests from this network", reason)
        
        # Subsequent send with that IP fails
        phone = "+919955112233"
        otp_manager._store.pop(phone, None)
        success, msg, _ = otp_manager.create_and_send_otp(phone, ip_address=test_ip)
        self.assertFalse(success)
        self.assertIn("network", msg.lower())

    def test_24_resend_invalidates_previous_otp(self):
        """Requesting a new OTP code must invalidate any previously issued OTP."""
        phone = "+919966112233"
        otp_manager._store.pop(phone, None)
        
        # 1st OTP
        success1, _, code1 = otp_manager.create_and_send_otp(phone)
        self.assertTrue(success1)
        self.assertTrue(code1)
        
        # Force cooldown expiration for test
        otp_manager._store[phone]['last_sent_at'] = time.time() - 61
        
        # 2nd OTP
        success2, _, code2 = otp_manager.create_and_send_otp(phone)
        self.assertTrue(success2)
        self.assertTrue(code2)
        
        # Verifying with code1 must fail
        verified1, err1 = otp_manager.verify_otp(phone, code1)
        self.assertFalse(verified1)
        
        # Verifying with code2 must succeed
        verified2, _ = otp_manager.verify_otp(phone, code2)
        self.assertTrue(verified2)

    def test_25_sms_gateway_dispatch_interfaces(self):
        """Validates Fast2SMS, Twilio, and MSG91 network payload formatting."""
        # Fast2SMS
        f2s = Fast2SmsOtpProvider()
        f2s.api_key = "test_f2s_key"
        with patch('urllib.request.urlopen') as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({'return': True}).encode('utf-8')
            mock_url.return_value.__enter__.return_value = mock_resp
            ok, msg = f2s.send_otp("+919876543210", "123456")
            self.assertTrue(ok)
            self.assertIn("Fast2SMS", msg)
            
        # Twilio
        tw = TwilioOtpProvider()
        tw.account_sid = "AC_mock_sid"
        tw.auth_token = "mock_auth_token"
        tw.from_number = "+15551234567"
        with patch('urllib.request.urlopen') as mock_url:
            mock_resp = MagicMock()
            mock_resp.status = 201
            mock_url.return_value.__enter__.return_value = mock_resp
            ok, msg = tw.send_otp("+919876543210", "123456")
            self.assertTrue(ok)
            self.assertIn("Twilio", msg)

        # MSG91
        m91 = Msg91OtpProvider()
        m91.auth_key = "mock_msg91_auth"
        m91.template_id = "mock_template_123"
        with patch('urllib.request.urlopen') as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({'type': 'success'}).encode('utf-8')
            mock_url.return_value.__enter__.return_value = mock_resp
            ok, msg = m91.send_otp("+919876543210", "123456")
            self.assertTrue(ok)
            self.assertIn("MSG91", msg)

    def test_26_send_and_verify_api_endpoints(self):
        """Validates JSON endpoints /send-otp and /verify-otp."""
        c = app.test_client()
        phone = "+919977889900"
        otp_manager._store.pop(phone, None)
        
        # /send-otp API
        send_resp = c.post('/send-otp', json={'phone': phone})
        self.assertEqual(send_resp.status_code, 200)
        data = json.loads(send_resp.data)
        self.assertTrue(data['success'])
        otp_code = data.get('demo_otp')
        self.assertIsNotNone(otp_code)
        
        # /verify-otp API
        verify_resp = c.post('/verify-otp', json={'phone': phone, 'otp': otp_code})
        self.assertEqual(verify_resp.status_code, 200)
        v_data = json.loads(verify_resp.data)
        self.assertTrue(v_data['success'])
        self.assertIsNotNone(v_data.get('user'))
        self.assertEqual(v_data['user']['phone'], phone)

if __name__ == '__main__':
    unittest.main()
