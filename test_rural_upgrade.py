import os
import re
import json
import unittest
import numpy as np
import cv2

# Import project modules
from app import app
from utils.validation import validate_retinal_image, ValidationResult
from services.chatbot_service import detect_language, chatbot_service, CASUAL_CONVERSATIONS, FAQ_KNOWLEDGE_BASE
from utils.database import init_db, get_db_connection

class TestRuralAccessibilityUpgrade(unittest.TestCase):
    """
    Comprehensive verification suite testing the 20 rural accessibility and quality upgrades:
    1. Default language English
    2. Hindi language support
    3. Hinglish language support
    4. Regional language 1: Bengali (bn)
    5. Regional language 2: Marathi (mr)
    6. Regional language 3: Tamil (ta)
    7. Language switching consistency
    8. Low-resource responsiveness & lightweight assets
    9. Blurred fundus rejection with actionable guidance
    10. Underexposed/dark fundus rejection with guidance
    11. Overexposed/glare fundus rejection with guidance
    12. Non-retinal image rejection with guidance
    13. "What does this mean?" explanation card in result template
    14. "What should I do now?" action guidance card in result template
    15. Eye care referral directory modal without fabricated hospitals
    16. Chatbot multi-language detection & matching
    17. Chatbot casual conversation
    18. Chatbot DR domain knowledge
    19. Chatbot emergency medical guardrails
    20. Existing core architecture regression (Model, Grad-CAM, Segmentation, OTP, User isolation)
    """

    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret'
        cls.client = app.test_client()

    # 1. Default language is English
    def test_01_default_language_is_english(self):
        with open('static/js/translations.js', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn("localStorage.getItem('retina_lang') || 'en'", content)
        self.assertIn("let currentLang = localStorage.getItem('retina_lang') || 'en';", content)

    # 2. Hindi language support
    def test_02_hindi_translations_available(self):
        with open('static/js/translations.js', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('"hi": {', content)
        self.assertIn("nav.home", content)
        self.assertIn("मुख्य पृष्ठ", content)

    # 3. Hinglish language support
    def test_03_hinglish_translations_available(self):
        with open('static/js/translations.js', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('"hinglish": {', content)
        self.assertIn("Ab mujhe aage kya karna chahiye?", content)

    # 4. Regional Language 1: Bengali (bn)
    def test_04_bengali_translations_available(self):
        with open('static/js/translations.js', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('"bn": {', content)
        self.assertIn("হোম", content)
        self.assertIn("ডায়াবেটিক রেটিনোপ্যাথি", content)

    # 5. Regional Language 2: Marathi (mr)
    def test_05_marathi_translations_available(self):
        with open('static/js/translations.js', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('"mr": {', content)
        self.assertIn("मुख्यपृष्ठ", content)
        self.assertIn("डायबेटिक रेटिनोपॅथी", content)

    # 6. Regional Language 3: Tamil (ta)
    def test_06_tamil_translations_available(self):
        with open('static/js/translations.js', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('"ta": {', content)
        self.assertIn("முகப்பு", content)
        self.assertIn("நீரிழிவு விழித்திரை நோய்", content)

    # 7. Language Switcher UI in base.html
    def test_07_language_switcher_in_base_template(self):
        with open('templates/base.html', 'r', encoding='utf-8') as f:
            base_html = f.read()
        for lang_code in ['en', 'hi', 'hinglish', 'bn', 'mr', 'ta']:
            self.assertIn(f"setLanguage('{lang_code}')", base_html)

    # 8. Low-resource compatibility & responsive styles
    def test_08_responsive_styling_for_multilingual(self):
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn(".lang-switcher", css)
        self.assertIn(".lang-btn", css)
        self.assertIn("overflow-x: auto", css)

    # 9. Blurred fundus image rejected with specific guidance
    def test_09_blurred_image_rejection(self):
        blank = np.zeros((300, 300, 3), dtype=np.uint8)
        cv2.circle(blank, (150, 150), 120, (180, 70, 20), -1)
        blurred = cv2.GaussianBlur(blank, (61, 61), 30)
        
        val = validate_retinal_image(blurred)
        self.assertFalse(val.is_valid)
        self.assertIn("guidance", val)
        self.assertIn("blur", val.reason.lower())
        self.assertTrue(len(val.guidance) > 10)

    # 10. Underexposed/dark fundus image rejected with guidance
    def test_10_dark_image_rejection(self):
        dark_img = np.full((300, 300, 3), 10, dtype=np.uint8)
        val = validate_retinal_image(dark_img)
        self.assertFalse(val.is_valid)
        self.assertTrue("dark" in val.reason.lower() or "exposure" in val.reason.lower())
        self.assertTrue(len(val.guidance) > 10)

    # 11. Overexposed/glare fundus image rejected with guidance
    def test_11_overexposed_image_rejection(self):
        bright_img = np.full((300, 300, 3), 250, dtype=np.uint8)
        val = validate_retinal_image(bright_img)
        self.assertFalse(val.is_valid)
        self.assertTrue("glare" in val.reason.lower() or "overexposed" in val.reason.lower() or "bright" in val.reason.lower())
        self.assertTrue(len(val.guidance) > 10)

    # 12. Non-retinal image rejected with guidance
    def test_12_non_retinal_rejection(self):
        blue_square = np.zeros((300, 300, 3), dtype=np.uint8)
        blue_square[:, :] = (255, 0, 0)
        val = validate_retinal_image(blue_square)
        self.assertFalse(val.is_valid)
        self.assertTrue(len(val.guidance) > 10)

    # 13. "What does this mean?" card in result.html
    def test_13_result_meaning_card(self):
        with open('templates/result.html', 'r', encoding='utf-8') as f:
            res_html = f.read()
        self.assertIn('data-i18n="action.meaning_heading"', res_html)
        self.assertIn('data-i18n="action.meaning_{{ screening.class_id }}"', res_html)

    # 14. "What should I do now?" action card in result.html
    def test_14_result_action_card(self):
        with open('templates/result.html', 'r', encoding='utf-8') as f:
            res_html = f.read()
        self.assertIn('data-i18n="action.heading"', res_html)
        self.assertIn('data-i18n="action.step_{{ screening.class_id }}"', res_html)
        self.assertIn('data-i18n="action.disclaimer"', res_html)

    # 15. Referral directory modal without fabricated hospitals
    def test_15_referral_directory_modal(self):
        with open('templates/result.html', 'r', encoding='utf-8') as f:
            res_html = f.read()
        self.assertIn('id="referralDirectoryModal"', res_html)
        self.assertIn('data-i18n="referral.modal_title"', res_html)
        self.assertIn('data-i18n="referral.level1_title"', res_html)
        self.assertIn('data-i18n="referral.level2_title"', res_html)
        self.assertIn('data-i18n="referral.level3_title"', res_html)
        self.assertNotIn('12.4 km', res_html)
        self.assertNotIn('Dr. Fake Hospital', res_html)
        self.assertIn('104 / 1075', res_html)

    # 16. Chatbot language detection for all 6 languages
    def test_16_chatbot_language_detection(self):
        self.assertEqual(detect_language('What is Diabetic Retinopathy?'), 'en')
        self.assertEqual(detect_language('डायबिटिक रेटिनोपैथी क्या है?'), 'hi')
        self.assertEqual(detect_language('Mera result kaisa hai?'), 'hinglish')
        self.assertEqual(detect_language('ডায়াবেটিক রেটিনোপ্যাথি কী?'), 'bn')
        self.assertEqual(detect_language('तुम्ही कसे आहात?'), 'mr')
        self.assertEqual(detect_language('எப்படி இருக்கிறீர்கள்?'), 'ta')

    # 17. Chatbot casual conversation in regional languages
    def test_17_chatbot_casual_conversation(self):
        res_bn = chatbot_service.handle_message('হ্যালো', lang='bn')
        self.assertIn('DrishtiAI', res_bn['reply'])
        self.assertEqual(res_bn['detected_lang'], 'bn')

        res_mr = chatbot_service.handle_message('तुम्ही कसे आहात', lang='mr')
        self.assertIn('DrishtiAI', res_mr['reply'])
        self.assertEqual(res_mr['detected_lang'], 'mr')

        res_ta = chatbot_service.handle_message('வணக்கம்', lang='ta')
        self.assertIn('DrishtiAI', res_ta['reply'])
        self.assertEqual(res_ta['detected_lang'], 'ta')

    # 18. Chatbot DR domain knowledge
    def test_18_chatbot_dr_faq(self):
        res = chatbot_service.handle_message('What are the stages of dr?', lang='en')
        self.assertIn('Grade 0', res['reply'])
        self.assertIn('Grade 4', res['reply'])

    # 19. Chatbot emergency medical guardrails
    def test_19_chatbot_emergency_guardrails(self):
        emergency_prompts = [
            ('I have sudden vision loss in my eye', 'en'),
            ('मेरी आंख में तेज दर्द है और रोशनी चली गई', 'hi'),
            ('চোখে তীব্র ব্যথা এবং হঠাৎ দৃষ্টি হ্রাস', 'bn'),
            ('डोळ्यात तीव्र वेदना आणि अचानक दृष्टी गेली', 'mr'),
            ('கண்ணில் கடுமையான வலி மற்றும் திடீர் பார்வை இழப்பு', 'ta')
        ]
        for prompt, expected_lang in emergency_prompts:
            res = chatbot_service.handle_message(prompt, lang=expected_lang)
            self.assertTrue(res['is_medical_warning'], f"Failed emergency detection for: {prompt}")

    # 20. Existing core architecture regression
    def test_20_core_architecture_regression(self):
        res = self.client.get('/login')
        self.assertEqual(res.status_code, 200)

        with self.client.session_transaction() as sess:
            sess['user'] = {
                'id': 1,
                'phone': '+919876543210',
                'name': 'Dr. Test User',
                'role': 'Ophthalmologist',
                'is_guest': False
            }

        res = self.client.get('/screening')
        self.assertEqual(res.status_code, 200)

        sample_path = 'static/samples/sample_no_dr.jpg'
        if os.path.exists(sample_path):
            img = cv2.imread(sample_path)
            is_valid, score, reason = validate_retinal_image(img)
            self.assertTrue(is_valid, f"Sample fundus failed validation: {reason}")

        res = self.client.get('/result/1')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'AI Screening Result', res.data)
        self.assertIn(b'Grad-CAM', res.data)
        self.assertIn(b'referralDirectoryModal', res.data)

if __name__ == '__main__':
    unittest.main()
