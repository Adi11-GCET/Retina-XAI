import unittest
import json
import os
from app import app
from utils.database import get_db_connection

class RetinaXAITestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        with self.app.session_transaction() as sess:
            sess['user'] = {
                'name': 'Dr. Ananya Sharma',
                'email': 'demo@drishtiai.org',
                'role': 'Consultant Ophthalmologist',
                'is_guest': False
            }

    def test_home_page(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'RETINA', response.data)
        self.assertIn(b'AI-ASSISTED RETINAL SCREENING', response.data)

    def test_screening_page(self):
        response = self.app.get('/screening')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'New Retinal Screening', response.data)
        self.assertIn(b'sample_no_dr.jpg', response.data)

    def test_dashboard_page(self):
        response = self.app.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Screening Dashboard', response.data)
        self.assertIn(b'distributionChart', response.data)

    def test_history_page(self):
        response = self.app.get('/history')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Screening History', response.data)
        self.assertIn(b'RXT-1001', response.data)

    def test_about_page(self):
        response = self.app.get('/about')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Prototype Limitations', response.data)
        self.assertIn(b'Custom PyTorch CNN', response.data)

    def test_api_dashboard(self):
        response = self.app.get('/api/dashboard')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('total', data)
        self.assertGreaterEqual(data['total'], 5)

    def test_api_history(self):
        response = self.app.get('/api/history')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 5)

    def test_predict_with_sample(self):
        response = self.app.post('/predict', data={'sample_name': 'sample_moderate.jpg'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('RXT-', data['patient_id'])
        self.assertIn('/result/RXT-', data['redirect_url'])

        # Now test retrieving the generated result page
        result_res = self.app.get(data['redirect_url'])
        self.assertEqual(result_res.status_code, 200)
        self.assertIn(b'AI Screening Result', result_res.data)
        self.assertIn(b'Grad-CAM', result_res.data)

    def test_save_screening_notes(self):
        # Update RXT-1001
        response = self.app.post('/save-screening', data={
            'screening_id': 'RXT-1001',
            'notes': 'Verified normal fundus by Dr. Sharma. No microaneurysms detected.',
            'referral_required': '0'
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])

    def test_accessibility_and_voice_elements(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('voiceAssistantModal', html)
        self.assertIn('navVoiceBtn', html)
        self.assertIn('themeToggle', html)
        self.assertIn('zoom-btn', html)
        self.assertIn('voice.js', html)

    def test_tts_and_dictate_on_result(self):
        response = self.app.get('/result/RXT-1001')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('ttsPlayBtn', html)
        self.assertIn('ttsStopBtn', html)
        self.assertIn('dictateNotesBtn', html)

    def test_voice_search_on_history(self):
        response = self.app.get('/history')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn('voiceSearchBtn', html)

    def test_invalid_image_rejection(self):
        """Ensure random non-retinal images are rejected with HTTP 400 and is_invalid_image: True."""
        from PIL import Image
        import io

        # Create a non-retinal image (e.g. cool blue landscape/document)
        fake_img = Image.new('RGB', (300, 300), color=(100, 150, 240))
        img_byte_arr = io.BytesIO()
        fake_img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)

        response = self.app.post(
            '/predict',
            data={'image': (img_byte_arr, 'random_landscape.jpg')},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertTrue(data.get('is_invalid_image', False))
        self.assertIn('Invalid Image', data.get('error', ''))

    def test_segmentation_integration_in_prediction(self):
        """Ensure valid retinal screening runs both DR prediction and IDRiD segmentation."""
        response = self.app.post('/predict', data={'sample_name': 'sample_mild.jpg'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])

        result_res = self.app.get(data['redirect_url'])
        self.assertEqual(result_res.status_code, 200)
        html = result_res.data.decode('utf-8')
        # Check Grad-CAM is preserved
        self.assertIn('EXPLAINABLE AI', html)
        self.assertIn('mainRetinaDisplay', html)
        # Check Segmentation is rendered
        self.assertIn('IDRiD PIXEL SEGMENTATION', html)
        self.assertIn('segRetinaDisplay', html)
        self.assertIn('switchSegView', html)

    def test_retinal_validator_direct(self):
        """Direct verification of multi-feature retinal validator."""
        from utils.validation import validate_retinal_image
        import tempfile
        from PIL import Image

        # Test valid fundus sample
        valid_res = validate_retinal_image('static/samples/sample_no_dr.jpg')
        self.assertTrue(valid_res['is_valid_retina'])

        # Test invalid non-retinal image
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tf:
            tf_path = tf.name
        try:
            non_retina = Image.new('RGB', (256, 256), color=(255, 255, 255))
            non_retina.save(tf_path)
            invalid_res = validate_retinal_image(tf_path)
            self.assertFalse(invalid_res['is_valid_retina'])
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_unauthenticated_protected_route_redirect(self):
        """Ensure unauthenticated users accessing protected routes are redirected to login."""
        fresh_client = app.test_client()
        response = fresh_client.get('/screening')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers.get('Location', ''))

    def test_login_page_renders_drishtiai(self):
        """Ensure login page renders DrishtiAI branding and guest option."""
        fresh_client = app.test_client()
        response = fresh_client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Drishti', response.data)
        self.assertIn(b'Secure Retinal Screening', response.data)
        self.assertIn(b'Explore Portal as Guest', response.data)

    def test_login_existing_user_redirects_to_otp(self):
        """Ensure logging in with existing user redirects to OTP verification."""
        fresh_client = app.test_client()
        response = fresh_client.post('/login', data={'email': 'demo@drishtiai.org'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/otp', response.headers.get('Location', ''))

    def test_login_new_user_redirects_to_register(self):
        """Ensure logging in with an unknown email redirects to clinician registration."""
        fresh_client = app.test_client()
        response = fresh_client.post('/login', data={'email': 'dr.new@hospital.org'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/register', response.headers.get('Location', ''))

    def test_register_clinician(self):
        """Ensure registering a clinician persists the user and moves to OTP."""
        fresh_client = app.test_client()
        response = fresh_client.post('/register', data={
            'full_name': 'Dr. Test Clinician',
            'email': 'test.clinician@ruralhealth.org',
            'age': '40',
            'gender': 'Male'
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/otp', response.headers.get('Location', ''))

    def test_otp_verification_success(self):
        """Ensure submitting correct Demo OTP 652070 logs in user and grants dashboard access."""
        fresh_client = app.test_client()
        with fresh_client.session_transaction() as sess:
            sess['pending_email'] = 'demo@drishtiai.org'
            sess['pending_name'] = 'Dr. Ananya Sharma'

        response = fresh_client.post('/otp', data={'otp': '652070'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard', response.headers.get('Location', ''))

        # Verify session is populated
        with fresh_client.session_transaction() as sess:
            self.assertIn('user', sess)
            self.assertEqual(sess['user']['email'], 'demo@drishtiai.org')
            self.assertFalse(sess['user']['is_guest'])

    def test_otp_verification_invalid_code(self):
        """Ensure invalid OTP code returns an error message."""
        fresh_client = app.test_client()
        response = fresh_client.post('/otp', data={'otp': '000000'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid security OTP code', response.data)

    def test_guest_access_bypass(self):
        """Ensure 1-click guest access bypasses authentication and sets Guest Screener session."""
        fresh_client = app.test_client()
        response = fresh_client.get('/guest')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard', response.headers.get('Location', ''))

        with fresh_client.session_transaction() as sess:
            self.assertIn('user', sess)
            self.assertEqual(sess['user']['name'], 'Guest Screener')
            self.assertTrue(sess['user']['is_guest'])

    def test_logout(self):
        """Ensure logging out clears the session and returns to login."""
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user'] = {'name': 'Test User', 'email': 'test@test.com', 'is_guest': False}
        response = client.get('/logout')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers.get('Location', ''))

        with client.session_transaction() as sess:
            self.assertNotIn('user', sess)

if __name__ == '__main__':
    unittest.main()

