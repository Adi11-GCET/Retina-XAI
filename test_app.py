import unittest
import json
import os
from app import app
from utils.database import get_db_connection

class RetinaXAITestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

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
        self.assertIn(b'EfficientNetB0', response.data)

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

if __name__ == '__main__':
    unittest.main()
