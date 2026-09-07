import unittest
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import time
from services.chatbot_service import chatbot_service
from utils.database import init_db, add_screening, create_or_update_user, get_user_by_id

class TestDrishtiAIChatbot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.test_pid = f"PT-TEST-{int(time.time()*1000)}"
        u1_id = create_or_update_user(full_name="Dr. Screener One", phone_number="9876543210")
        u2_id = create_or_update_user(full_name="Dr. Screener Two", phone_number="9876543211")
        cls.user1 = get_user_by_id(u1_id)
        cls.user2 = get_user_by_id(u2_id)

        # Create screening for user 1
        add_screening(
            patient_id=cls.test_pid,
            image_path="uploads/test1.jpg",
            heatmap_path="uploads/grad1.jpg",
            overlay_path="uploads/overlay1.jpg",
            prediction="Moderate DR",
            class_id=2,
            confidence=89.5,
            probabilities=[0.02, 0.05, 0.89, 0.03, 0.01],
            risk_status="Referral Recommended",
            notes="Clinical trial test note",
            referral_required=1,
            user_id=cls.user1['id']
        )

    def test_case_01_hi(self):
        res = chatbot_service.handle_message("Hi", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertIn("Hello! 👋", res["reply"])
        self.assertIn("DrishtiAI", res["reply"])
        print("\n[Case 1: 'Hi'] =>", res["reply"])

    def test_case_02_how_are_you(self):
        res = chatbot_service.handle_message("How are you?", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertIn("I'm doing great! 😊", res["reply"])
        self.assertIn("Diabetic Retinopathy", res["reply"])
        print("\n[Case 2: 'How are you?'] =>", res["reply"])

    def test_case_03_favorite_animal(self):
        res = chatbot_service.handle_message("What is your favorite animal?", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertIn("dog 🐶", res["reply"])
        self.assertIn("DrishtiAI", res["reply"])
        print("\n[Case 3: 'What is your favorite animal?'] =>", res["reply"])

    def test_case_04_tell_me_a_joke(self):
        res = chatbot_service.handle_message("Tell me a joke", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertTrue("eye doctor" in res["reply"].lower() or "web-sight" in res["reply"].lower())
        print("\n[Case 4: 'Tell me a joke'] =>", res["reply"])

    def test_case_05_thank_you(self):
        res = chatbot_service.handle_message("Thank you", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertIn("You're welcome! 😊", res["reply"])
        print("\n[Case 5: 'Thank you'] =>", res["reply"])

    def test_case_06_bye(self):
        res = chatbot_service.handle_message("Bye", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertIn("Goodbye! 👋", res["reply"])
        print("\n[Case 6: 'Bye'] =>", res["reply"])

    def test_case_07_what_is_diabetic_retinopathy(self):
        res = chatbot_service.handle_message("What is diabetic retinopathy?", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertIn("Diabetic Retinopathy (DR)", res["reply"])
        self.assertIn("blood vessels", res["reply"])
        print("\n[Case 7: 'What is diabetic retinopathy?'] =>", res["reply"][:120] + "...")

    def test_case_08_what_are_the_5_stages(self):
        res = chatbot_service.handle_message("What are the 5 stages?", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertIn("Grade 0", res["reply"])
        self.assertIn("Grade 4", res["reply"])
        print("\n[Case 8: 'What are the 5 stages?'] =>", res["reply"][:120] + "...")

    def test_case_09_what_is_grad_cam(self):
        res = chatbot_service.handle_message("What is Grad-CAM?", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertIn("Grad-CAM", res["reply"])
        self.assertIn("heatmap", res["reply"].lower())
        print("\n[Case 9: 'What is Grad-CAM?'] =>", res["reply"][:120] + "...")

    def test_case_10_why_was_my_image_rejected(self):
        res = chatbot_service.handle_message("Why was my image rejected?", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertTrue("rejected" in res["reply"].lower() or "validator" in res["reply"].lower())
        print("\n[Case 10: 'Why was my image rejected?'] =>", res["reply"][:120] + "...")

    def test_case_11_what_is_apple(self):
        res = chatbot_service.handle_message("What is Apple?", lang="en")
        self.assertEqual(res["mode"], "faq")
        self.assertIn("outside my current scope", res["reply"].lower())
        self.assertIn("DrishtiAI", res["reply"])
        print("\n[Case 11: 'What is Apple?'] =>", res["reply"])

    def test_case_12_hindi_how_are_you(self):
        res = chatbot_service.handle_message("आप कैसे हो?", lang="hi")
        self.assertEqual(res["detected_lang"], "hi")
        self.assertIn("मैं बहुत बढ़िया हूँ! 😊", res["reply"])
        print("\n[Case 12: 'आप कैसे हो?'] =>", res["reply"])

    def test_case_13_hindi_what_is_dr(self):
        res = chatbot_service.handle_message("डायबिटिक रेटिनोपैथी क्या है?", lang="hi")
        self.assertEqual(res["detected_lang"], "hi")
        self.assertIn("डायबिटिक रेटिनोपैथी (DR)", res["reply"])
        print("\n[Case 13: 'डायबिटिक रेटिनोपैथी क्या है?'] =>", res["reply"][:120] + "...")

    def test_case_14_hinglish_tum_kaise_ho(self):
        res = chatbot_service.handle_message("tum kaise ho?", lang="en")
        self.assertEqual(res["detected_lang"], "hinglish")
        self.assertIn("Main badhiya hoon! 😊", res["reply"])
        print("\n[Case 14: 'tum kaise ho?'] =>", res["reply"])

    def test_case_15_voice_input(self):
        # Verify voice input STT architecture and language parameter handling
        with open("static/js/chatbot.js", "r", encoding="utf-8") as f:
            chatbot_js = f.read()
        self.assertIn("SpeechRecognition", chatbot_js)
        self.assertIn("currentLang === 'hi' ? 'hi-IN' : 'en-IN'", chatbot_js)
        self.assertIn("toggleVoiceInput", chatbot_js)
        self.assertIn("submitUserMessage", chatbot_js)
        print("\n[Case 15: Voice Input] => SpeechRecognition configured for hi-IN and en-IN with mic toggle controls.")

    def test_case_16_text_to_speech(self):
        # Verify text-to-speech TTS architecture and Hindi/English voice synthesis
        with open("static/js/chatbot.js", "r", encoding="utf-8") as f:
            chatbot_js = f.read()
        with open("static/js/voice.js", "r", encoding="utf-8") as f:
            voice_js = f.read()
        self.assertIn("window.retinaVoice.speakText", chatbot_js)
        self.assertIn("speechSynthesis.speak", voice_js)
        self.assertIn("lang === 'hi' ? 'hi-IN' : 'en-US'", voice_js)
        print("\n[Case 16: Text-to-Speech] => SpeechSynthesisUtterance configured with dual language voice synthesis and speaker readout buttons.")

    def test_case_17_user_result_explanation_and_isolation(self):
        # Authenticated user 1
        res1 = chatbot_service.handle_message("Explain my result", user_id=self.user1['id'], lang="en")
        self.assertIn(self.test_pid, res1["reply"])
        self.assertIn("Moderate DR", res1["reply"])
        self.assertIn("Grade 2", res1["reply"])

        # Authenticated user 2 (has no screening)
        res2 = chatbot_service.handle_message("Explain my result", user_id=self.user2['id'], lang="en")
        self.assertIn("No screening record is available yet", res2["reply"])
        self.assertNotIn(self.test_pid, res2["reply"])

        # Unauthenticated request (user_id=None)
        res_anon = chatbot_service.handle_message("Explain my result", user_id=None, lang="en")
        self.assertIn("Please log in", res_anon["reply"])
        self.assertNotIn(self.test_pid, res_anon["reply"])

        print("\n[Case 17: Authenticated Result Isolation] =>")
        print("User 1:", res1["reply"][:100] + "...")
        print("User 2:", res2["reply"])
        print("Anonymous:", res_anon["reply"])

if __name__ == "__main__":
    unittest.main()
