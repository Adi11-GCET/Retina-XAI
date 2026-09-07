import os
import re
import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from utils.database import get_user_latest_screening

logger = logging.getLogger('retina_xai.chatbot')

# Red flag keywords requiring immediate emergency ophthalmic attention
EMERGENCY_KEYWORDS = [
    'sudden vision loss', 'lost my vision', 'cannot see suddenly', 'blind in one eye',
    'severe eye pain', 'unbearable pain', 'flashes of light', 'black curtain',
    'chemical in eye', 'eye trauma', 'bleeding from eye', 'sudden blind',
    'अचानक दिखना बंद', 'आंख में तेज दर्द', 'रोशनी चली गई', 'अचानक अंधापन', 'आंख से खून',
    'achanak dikhna band', 'aankh me dard', 'aankh me tez dard', 'aankh se khoon',
    'হঠাৎ দৃষ্টি হ্রাস', 'চোখে তীব্র ব্যথা', 'অন্ধ হয়ে যাওয়া', 'চোখ থেকে রক্তপাত',
    'अचानक दृष्टी जाणे', 'डोळ्यात तीव्र वेदना', 'अचानक अंधत्व', 'डोळ्यातून रक्त',
    'திடீர் பார்வை இழப்பு', 'கண்ணில் கடுமையான வலி', 'திடீர் குருட்டுத்தன்மை', 'கண்ணில் ரத்தம்'
]

# Language Detection Helper
def detect_language(text: str, default_lang: str = 'en') -> str:
    """
    Detects whether text is in Bengali ('bn'), Tamil ('ta'), Marathi ('mr'),
    Hindi ('hi'), Hinglish ('hinglish'), or English ('en').
    """
    if not text:
        return default_lang

    # 1. Bengali script range: U+0980 to U+09FF
    if re.search(r'[\u0980-\u09ff]', text):
        return 'bn'

    # 2. Tamil script range: U+0B80 to U+0BFF
    if re.search(r'[\u0b80-\u0bff]', text):
        return 'ta'

    # 3. Devanagari script range: U+0900 to U+097F (Hindi & Marathi)
    if re.search(r'[\u0900-\u097f]', text):
        marathi_words = ['कसे', 'काय', 'आहे', 'नाही', 'नमस्कार', 'कसा', 'कशी', 'माझे', 'माझा', 'माझी', 'डोळे', 'तपासा', 'करा', 'होते']
        if any(w in text for w in marathi_words) or default_lang == 'mr':
            return 'mr'
        return 'hi'

    lower = text.lower()
    # 4. Check for common Hinglish words
    hinglish_words = [
        'kaise', 'kya', 'hai', 'hain', 'tum', 'aap', 'mera', 'meri', 'mere',
        'batao', 'shukriya', 'theek', 'thik', 'aankh', 'aankhein', 'kaun', 'kyon',
        'kyu', 'kripya', 'accha', 'achha', 'nahi', 'karo', 'bolo', 'dhanyawad',
        'namaste', 'namashkar', 'kaam', 'karte', 'ho', 'bhai', 'kaisa', 'kaisi',
        'madad', 'samjhao', 'samjha', 'dijiye', 'bataye', 'batayein', 'chahiye'
    ]
    words = re.findall(r'\b[a-z]+\b', lower)
    match_count = sum(1 for w in words if w in hinglish_words)
    if match_count >= 1:
        return 'hinglish'

    if default_lang in ('bn', 'ta', 'mr', 'hi', 'hinglish'):
        return default_lang

    return 'en'

# -------------------------------------------------------------------
# Casual Conversation Responses (6 Languages)
# -------------------------------------------------------------------
CASUAL_CONVERSATIONS = [
    {
        'id': 'how_are_you',
        'pattern': r'(?:\b(?:how\s+(?:are\s+you|r\s+u|do\s+you\s+do|are\s+things|is\s+it\s+going)|how\'?s\s+it\s+going|kaise\s+ho|kya\s+haal|kaisa\s+chal\s+raha)\b|आप\s+कैसे\s+(?:हो|हैं)|तुम\s+कैसे\s+हो|কেমন\s+আছেন|तुम्ही\s+कसे\s+आहात|எப்படி\s+இருக்கிறீர்கள்)',
        'en': "I'm doing great! 😊 I'm here to help you with Diabetic Retinopathy, your screening results, or any questions about using the DrishtiAI app. How can I help you today?",
        'hi': "मैं बहुत बढ़िया हूँ! 😊 मैं डायबिटिक रेटिनोपैथी, आपकी स्क्रीनिंग रिपोर्ट या DrishtiAI ऐप के उपयोग में आपकी मदद के लिए यहाँ हूँ। आज मैं आपकी क्या सहायता कर सकता हूँ?",
        'hinglish': "Main badhiya hoon! 😊 Main Diabetic Retinopathy, aapke screening results aur DrishtiAI app use karne me help karne ke liye yahan hoon. Aaj main aapki kya help kar sakta hoon?",
        'bn': "আমি খুব ভালো আছি! 😊 আমি আপনাকে ডায়াবেটিক রেটিনোপ্যাথি, স্ক্রিনিং ফলাফল এবং DrishtiAI অ্যাপ ব্যবহারে সহায়তা করতে এখানে আছি। আজ আপনাকে কীভাবে সাহায্য করতে পারি?",
        'mr': "मी मजेत आहे! 😊 मी तुम्हाला डायबेटिक रेटिनोपॅथी, तुमचे स्क्रीनिंग निकाल आणि DrishtiAI ॲप वापरण्यात मदत करण्यासाठी येथे आहे. आज मी तुम्हाला कशी मदत करू शकतो?",
        'ta': "நான் நலமாக இருக்கிறேன்! 😊 நீரிழிவு விழித்திரை நோய், உங்கள் பரிசோதனை முடிவுகள் மற்றும் DrishtiAI செயலியைப் பயன்படுத்துவதில் உதவ நான் இங்கு இருக்கிறேன். இன்று நான் உங்களுக்கு எவ்வாறு உதவ முடியும்?"
    },
    {
        'id': 'favorite_animal',
        'pattern': r'(?:\b(?:fav(?:ou?rite)?\s+animal|animal\s+do\s+you\s+like|fav(?:ou?rite)?\s+pet)\b|पसंदीदा\s+जानवर|पसंदीदा\s+पशु|পছন্দের\s+প্রাণী|आवडता\s+प्राणी|பிடித்த\s+விலங்கு)',
        'en': "I'd probably pick a dog 🐶 — friendly, loyal, and always happy to help! I'm mainly here to help with Diabetic Retinopathy and the DrishtiAI app, though. 😊",
        'hi': "मुझे शायद कुत्ता 🐶 सबसे ज्यादा पसंद आएगा — वफादार, प्यारा और हमेशा मदद के लिए तैयार! वैसे मुख्य रूप से मैं डायबिटिक रेटिनोपैथी और DrishtiAI ऐप में आपकी मदद के लिए यहाँ हूँ। 😊",
        'hinglish': "Mujhe dog 🐶 sabse zyada pasand hai — friendly, loyal aur hamesha help karne ko ready! Waise main yahan Diabetic Retinopathy aur DrishtiAI app me help karne ke liye hoon. 😊",
        'bn': "আমি কুকুর 🐶 পছন্দ করব — বন্ধুত্বপূর্ণ, বিশ্বস্ত এবং সবসময় সাহায্য করতে প্রস্তুত! তবে আমি মূলত ডায়াবেটিক রেটিনোপ্যাথি এবং DrishtiAI অ্যাপে সাহায্য করতে এখানে আছি। 😊",
        'mr': "मला कुत्रा 🐶 सर्वात जास्त आवडेल — निष्ठावान, प्रेमळ आणि नेहमी मदत करण्यास तयार! तरी मी प्रामुख्याने डायबेटिक रेटिनोपॅथी आणि DrishtiAI ॲपमध्ये मदतीसाठी येथे आहे. 😊",
        'ta': "எனக்கு நாய் 🐶 மிகவும் பிடிக்கும் — விசுவாசமானது மற்றும் எப்போதும் உதவத் தயாராக இருக்கும்! எனினும் நான் முக்கியமாக நீரிழிவு விழித்திரை நோய் மற்றும் DrishtiAI செயலிக்கு உதவவே இங்கு இருக்கிறேன். 😊"
    },
    {
        'id': 'tell_joke',
        'pattern': r'(?:\b(?:tell\s+(?:me\s+)?a\s+joke|make\s+me\s+laugh|any\s+joke|joke\s+sunao|ek\s+joke)\b|चुटकुला|कोई\s+जोक|मजाक|কৌতুক|विनोद|ஜோக்)',
        'en': "Why did the computer go to the eye doctor? Because it needed to improve its web-sight! 😄 On a serious note, regular retinal checkups keep your real eyesight safe. How can I help you with DrishtiAI today?",
        'hi': "कंप्यूटर आंखों के डॉक्टर के पास क्यों गया? क्योंकि उसकी 'वेब-साइट' (दृष्टि) कमजोर हो गई थी! 😄 मज़ाक से हटकर, समय पर रेटिना की जांच दृष्टि को सुरक्षित रखती है। DrishtiAI के बारे में आज आपको क्या जानना है?",
        'hinglish': "Computer eye doctor ke paas kyon gaya? Kyunki uski 'web-sight' kamzor ho gayi thi! 😄 Joke aside, regular eye checkup hamesha zaroori hai. DrishtiAI ke baare me main aapki kya help kar sakta hoon?",
        'bn': "কম্পিউটার চোখের ডাক্তারের কাছে কেন গেল? কারণ তার 'ওয়েব-দৃষ্টি' উন্নত করা দরকার ছিল! 😄 কৌতুক পাশে রেখে, নিয়মিত রেটিনা পরীক্ষা দৃষ্টি সুরক্ষিত রাখে। আজ DrishtiAI সম্পর্কে কী জানতে চান?",
        'mr': "संगणक डोळ्यांच्या डॉक्टरांकडे का गेला? कारण त्याची 'वेब-साइट' (दृष्टी) कमकुवत झाली होती! 😄 गंमत सोडली तर, डोळ्यांची नियमित तपासणी दृष्टी सुरक्षित ठेवते. DrishtiAI बद्दल काय जाणून घ्यायचे आहे?",
        'ta': "கணினி ஏன் கண் மருத்துவரிடம் சென்றது? ஏனென்றால் அதன் 'வெப்-பார்வை' மங்கலாக இருந்தது! 😄 நகைச்சுவை ஒருபுறம் இருக்க, வழக்கமான கண் பரிசோதனை உங்கள் பார்வையைப் பாதுகாக்கும். DrishtiAI பற்றி நான் என்ன உதவ வேண்டும்?"
    },
    {
        'id': 'thank_you',
        'pattern': r'(?:\b(?:thank\s*you|thanks|thx|thank\s*u|shukriya|dhanyawad|dhanyavad|bahut\s+shukriya)\b|धन्यवाद|शुक्रिया|आभार|ধন্যবাদ|धन्यवाद|நன்றி)',
        'en': "You're welcome! 😊 I'm always happy to help. Let me know if you have any other questions about DrishtiAI.",
        'hi': "आपका स्वागत है! 😊 मुझे आपकी मदद करके खुशी हुई। DrishtiAI या रेटिना जांच से जुड़ा कोई अन्य सवाल हो तो बेझिझक पूछें।",
        'hinglish': "You're welcome! 😊 Main hamesha aapki help ke liye available hoon. DrishtiAI se related koi aur sawal ho toh zaroor poochiye.",
        'bn': "আপনাকে স্বাগতম! 😊 সাহায্য করতে পেরে আনন্দিত। DrishtiAI বা রেটিনা পরীক্ষা সম্পর্কে আরও কোনো প্রশ্ন থাকলে নির্দ্বিধায় জিজ্ঞাসা করুন।",
        'mr': "आपले स्वागत आहे! 😊 मदत करून आनंद झाला. DrishtiAI किंवा डोळ्यांच्या तपासणीबद्दल काही प्रश्न असल्यास नक्की विचारा.",
        'ta': "நல்வரவு! 😊 உதவ முடிந்ததில் மகிழ்ச்சி. DrishtiAI அல்லது கண் பரிசோதனை பற்றி வேறு ஏதேனும் கேள்விகள் இருந்தால் கேளுங்கள்."
    },
    {
        'id': 'bye',
        'pattern': r'(?:\b(?:bye|goodbye|see\s+you|see\s+ya|alvida|tata|phir\s+milenge|chalta\s+hoon)\b|अलविदा|बाय|फिर\s+मिलेंगे|বিদায়|निरोप|பிரியாவிடை)',
        'en': "Goodbye! 👋 Take care of your eye health, and feel free to come back if you need help.",
        'hi': "अलविदा! 👋 अपनी आंखों की सेहत का ख्याल रखें, और कोई भी सहायता चाहिए हो तो कभी भी पूछें।",
        'hinglish': "Goodbye! 👋 Apna aur apni aankhon ka khayal rakhein, aur kabhi bhi help chahiye ho toh DrishtiAI par zaroor aayein.",
        'bn': "বিদায়! 👋 আপনার চোখের স্বাস্থ্যের যত্ন নিন, কোনো সাহায্যের প্রয়োজন হলে আবার আসবেন।",
        'mr': "निरोप! 👋 डोळ्यांच्या आरोग्याची काळजी घ्या आणि मदतीची गरज भासल्यास पुन्हा भेटा.",
        'ta': "பிரியாவிடை! 👋 உங்கள் கண் நலனில் அக்கறை செலுத்துங்கள், உதவி தேவைப்படும்போது மீண்டும் வாருங்கள்."
    },
    {
        'id': 'good_morning_night',
        'pattern': r'(?:\b(?:good\s+(?:morning|afternoon|evening|night)|shubh\s+(?:prabhat|ratri))\b|शुभ\s+(?:प्रभात|रात्रि|संध्या|दिन)|সুপ্রভাত|শুভরাত্রি|शुभ\s+सकाळ|காலை\s+வணக்கம்)',
        'en': "Greetings! ☀️ Wishing you healthy eyes and well-being. How can I assist you with your screening or the DrishtiAI portal today?",
        'hi': "शुभ दिन! ☀️ आशा है आपका दिन मंगलमय और स्वस्थ रहेगा। आज मैं डायबिटिक रेटिनोपैथी या DrishtiAI ऐप में आपकी क्या सहायता कर सकता हूँ?",
        'hinglish': "Greetings! ☀️ Wishing you great health and vision. Aaj main DrishtiAI portal ya screening me aapki kya help kar sakta hoon?",
        'bn': "শুভেচ্ছা! ☀️ আপনার সুস্বাস্থ্য কামনা করি। আজ DrishtiAI পোর্টালে আপনার কী সাহায্য করতে পারি?",
        'mr': "नमस्कार! ☀️ तुम्हाला उत्तम आरोग्य लाभावे ही शुभेच्छा. आज मी DrishtiAI पोर्टलवर कशी मदत करू शकतो?",
        'ta': "வணக்கம்! ☀️ உங்களுக்கு நல்ல ஆரோக்கியம் கிடைக்க வாழ்த்துகள். இன்று DrishtiAI போர்ட்டலில் நான் எவ்வாறு உதவ முடியும்?"
    },
    {
        'id': 'greeting',
        'pattern': r'(?:^\s*(?:hi|hello|hey|heya|hola|namaste|namaskar)\b|नमस्ते|नमस्कार|हेलो|हाय|हॅलो|হ্যালো|வணக்கம்)',
        'en': "Hello! 👋 Welcome to DrishtiAI. I can help you understand Diabetic Retinopathy, explain screening results, and guide you through the app. How can I help you today?",
        'hi': "नमस्ते! 👋 DrishtiAI में आपका स्वागत है। मैं डायबिटिक रेटिनोपैथी को समझने, स्क्रीनिंग परिणाम देखने और ऐप चलाने में आपकी मदद कर सकता हूँ। आज मैं आपकी क्या सहायता करूँ?",
        'hinglish': "Hello! 👋 DrishtiAI me aapka swagat hai. Main Diabetic Retinopathy samjhane, screening result explain karne aur app use karne me help kar sakta hoon. Aaj main aapki kya help karoon?",
        'bn': "নমস্কার! 👋 DrishtiAI-তে স্বাগতম। আমি ডায়াবেটিক রেটিনোপ্যাথি বুঝতে, স্ক্রিনিং ফলাফল ব্যাখ্যা করতে এবং অ্যাপ পরিচালনায় সহায়তা করতে পারি। আজ কীভাবে সাহায্য করব?",
        'mr': "नमस्कार! 👋 DrishtiAI मध्ये आपले स्वागत आहे. मी डायबेटिक रेटिनोपॅथी समजून घेणे, तपासणी निकाल आणि ॲप वापरण्यात मदत करू शकतो. आज काय मदत करू?",
        'ta': "வணக்கம்! 👋 DrishtiAI-க்கு நல்வரவு. நீரிழிவு விழித்திரை நோயைப் புரிந்துகொள்ளவும், பரிசோதனை முடிவுகளை அறியவும் நான் உதவ முடியும். இன்று என்ன உதவி தேவை?"
    },
    {
        'id': 'who_are_you',
        'pattern': r'(?:\b(?:who\s+are\s+you|what\s+are\s+you|your\s+name|tum\s+kaun\s+ho|aap\s+kaun\s+hai)\b|तुम\s+कौन\s+हो|आप\s+कौन\s+हैं|तुम्हारा\s+नाम|आपका\s+नाम|তুমি\s+কে|तुम्ही\s+कोण\s+आहात|நீ\s+யார்)',
        'en': "I am the DrishtiAI Assistant 🤖 — your digital companion for Diabetic Retinopathy education, Grad-CAM interpretability, and navigation across the DrishtiAI portal.",
        'hi': "मैं दृष्टिAI सहायक 🤖 हूँ — डायबिटिक रेटिनोपैथी को समझने, Grad-CAM हीटमैप की व्याख्या करने और DrishtiAI पोर्टल के उपयोग में आपका डिजिटल सहयोगी।",
        'hinglish': "Main DrishtiAI Assistant 🤖 hoon — Diabetic Retinopathy samjhane, Grad-CAM heatmaps interpret karne aur DrishtiAI portal use karne me aapka digital companion.",
        'bn': "আমি DrishtiAI সহকারী 🤖 — ডায়াবেটিক রেটিনোপ্যাথি শিক্ষা, Grad-CAM ব্যাখ্যা এবং DrishtiAI পোর্টাল নেভিগেশনে আপনার ডিজিটাল সহযোগী।",
        'mr': "मी DrishtiAI सहाय्यक 🤖 आहे — डायबेटिक रेटिनोपॅथी माहिती, Grad-CAM स्पष्टीकरण आणि DrishtiAI पोर्टल वापरासाठी तुमचा डिजिटल सोबती.",
        'ta': "நான் DrishtiAI உதவியாளர் 🤖 — நீரிழிவு விழித்திரை நோய் விழிப்புணர்வு, Grad-CAM விளக்கங்கள் மற்றும் DrishtiAI போர்டல் வழிகாட்டலுக்கான உங்கள் டிஜிட்டல் தோழன்."
    }
]

# -------------------------------------------------------------------
# Clinical & Application Knowledge Base (6 Languages)
# -------------------------------------------------------------------
FAQ_KNOWLEDGE_BASE = [
    {
        'id': 'what_is_dr',
        'keywords': ['what is dr', 'what is diabetic retinopathy', 'diabetic retinopathy', 'diabetes eye', 'sugar eye', 'डायबिटिक रेटिनोपैथी क्या है', 'रेटिनोपैथी क्या है', 'dr kya hai', 'diabetic retinopathy kya hai', 'ডায়াবেটিক রেটিনোপ্যাথি', 'डायबेटिक रेटिनोपॅथी म्हणजे काय', 'நீரிழிவு விழித்திரை நோய் என்றால் என்ன'],
        'en': (
            "Diabetic Retinopathy (DR) is an eye complication caused by chronically high blood sugar in diabetes mellitus. "
            "Excess glucose weakens and damages the tiny blood vessels in the retina (the light-sensing tissue at the back of the eye). "
            "In early stages, blood vessels swell and leak fluid or blood (microaneurysms, hemorrhages, and exudates). "
            "In advanced stages, abnormal fragile vessels proliferate (neovascularization), which can lead to severe vision impairment if not identified and managed early."
        ),
        'hi': (
            "डायबिटिक रेटिनोपैथी (DR) मधुमेह (शुगर) के कारण आंखों के पर्दे (रेटिना) को होने वाला गंभीर नुकसान है। "
            "लंबे समय तक ब्लड शुगर नियंत्रित न रहने से रेटिना की सूक्ष्म रक्त नलिकाएं कमजोर हो जाती हैं, जिससे सूजन, खून का रिसाव या नई नाजुक नसें बनने लगती हैं। "
            "नियमित वार्षिक जांच और समय पर उपचार से दृष्टि को सुरक्षित रखा जा सकता है।"
        ),
        'hinglish': (
            "Diabetic Retinopathy (DR) diabetes (sugar) ki wajah se aankhon ke parde (retina) ko hone wala damage hai. "
            "High blood glucose ki wajah se retina ki micro blood vessels leak ya block hone lagti hain. "
            "Shuruat me microaneurysms aur exudates aate hain, aur advanced stage me abnormal nasein banti hain. Regular screening se vision loss ko roka ja sakta hai."
        ),
        'bn': (
            "ডায়াবেটিক রেটিনোপ্যাথি (DR) হলো ডায়াবেটিসের কারণে চোখের পেছনের রেটিনার রক্তনালী ক্ষতিগ্রস্ত হওয়ার একটি জটিলতা। "
            "রক্তে শর্করার মাত্রা দীর্ঘ সময় বেশি থাকলে রক্তনালী ফুলে যায় বা রক্তপাত ঘটে। নিয়মিত বার্ষিক পরীক্ষা ও প্রাথমিক চিকিৎসার মাধ্যমে অন্ধত্ব প্রতিরোধ করা যায়।"
        ),
        'mr': (
            "डायबेटिक रेटिनोपॅथी (DR) हा मधुमेहामुळे डोळ्यांच्या पडद्याला (रेटिना) होणारा आजार आहे. "
            "रक्तातील साखरेचे प्रमाण दीर्घकाळ जास्त राहिल्याने सूक्ष्म रक्तवाहिन्या खराब होतात व गळती होते. वेळेवर तपासणी आणि उपचाराने दृष्टी वाचवता येते."
        ),
        'ta': (
            "நீரிழிவு விழித்திரை நோய் (DR) என்பது நீரிழிவு நோயினால் கண்ணின் விழித்திரையில் உள்ள ரத்தக் குழாய்கள் சேதமடைவதால் ஏற்படும் பாதிப்பாகும். "
            "ரத்த சர்க்கரை அளவு கட்டுப்பாடற்று இருக்கும்போது ரத்தக் கசிவு ஏற்படுகிறது. ஆரம்ப கால பரிசோதனை மூலம் பார்வை இழப்பைத் தடுக்க முடியும்."
        )
    },
    {
        'id': 'stages_of_dr',
        'keywords': ['stages', 'stages of dr', 'grades', 'grade 0', 'grade 1', 'grade 2', 'grade 3', 'grade 4', 'icdr', '5 stages', 'पड़ाव', 'स्टेज', 'ग्रेड', '5 stage', 'stages kya hai', 'ধাপ', 'टप्पे', 'நிலைகள்'],
        'en': (
            "DrishtiAI classifies Diabetic Retinopathy into 5 international ICDR clinical severity stages:\n\n"
            "• Grade 0 — No DR: Retina is healthy with no detectable diabetic microvascular abnormalities.\n"
            "• Grade 1 — Mild DR: Isolated microaneurysms (tiny capillary outpouchings) only. Advised annual monitoring.\n"
            "• Grade 2 — Moderate DR: Multiple microaneurysms, blot hemorrhages, and hard exudates. Specialist evaluation recommended.\n"
            "• Grade 3 — Severe DR: Marked hemorrhages in all 4 quadrants, venous beading, or IRMA. Urgent specialist referral required.\n"
            "• Grade 4 — Proliferative DR: Fragile neovascularization or vitreous hemorrhage with high risk of retinal detachment. Urgent tertiary intervention required."
        ),
        'hi': (
            "DrishtiAI डायबिटिक रेटिनोपैथी को 5 अंतर्राष्ट्रीय क्लिनिकल चरणों (स्टेज) में वर्गीकृत करता है:\n\n"
            "• ग्रेड 0 (No DR): रेटिना पूरी तरह सामान्य और स्वस्थ है।\n"
            "• ग्रेड 1 (Mild DR): केवल शुरुआती बारीक माइक्रोएन्यूरिज्म (नस का फूलना)। वार्षिक निगरानी अनुशंसित।\n"
            "• ग्रेड 2 (Moderate DR): खून के धब्बे और रिसाव (Exudates)। नेत्र विशेषज्ञ से जांच जरूरी।\n"
            "• ग्रेड 3 (Severe DR): चारों चतुर्थांशों में गंभीर रक्तस्राव। तत्काल विशेषज्ञ रेफरल आवश्यक।\n"
            "• ग्रेड 4 (Proliferative DR): असामान्य नई नाजुक नसें। तुरंत आपातकालीन तृतीयक इलाज आवश्यक।"
        ),
        'hinglish': (
            "DrishtiAI me Diabetic Retinopathy ki 5 stages hoti hain:\n\n"
            "• Grade 0 (No DR): Retina bilkul normal aur healthy hai.\n"
            "• Grade 1 (Mild DR): Sirf shuruati microaneurysms hote hain. 12-month routine monitoring.\n"
            "• Grade 2 (Moderate DR): Multiple hemorrhages aur exudates. Specialist doctor ko dikhana recommended hai.\n"
            "• Grade 3 (Severe DR): Extensive retinal bleeding. Urgent eye specialist referral zaroori hai.\n"
            "• Grade 4 (Proliferative DR): New abnormal vessels proliferate. Immediate tertiary eye care zaroori hai."
        ),
        'bn': (
            "DrishtiAI ডায়াবেটিক রেটিনোপ্যাথিকে ৫টি আন্তর্জাতিক ধাপে ভাগ করে:\n\n"
            "• গ্রেড ০ (No DR): রেটিনা সম্পূর্ণ সুস্থ।\n"
            "• গ্রেড ১ (Mild DR): প্রাথমিক ক্ষুদ্র মাইক্রোঅ্যানিউরিজম। বার্ষিক পর্যবেক্ষণ প্রয়োজন।\n"
            "• গ্রেড ২ (Moderate DR): রক্তপাত ও তরল নিঃসরণ। বিশেষজ্ঞ ডাক্তার দেখানো প্রয়োজন।\n"
            "• গ্রেড ৩ (Severe DR): রেটিনার চারটি অংশে ব্যাপক রক্তপাত। দ্রুত রেফারেল জরুরি।\n"
            "• গ্রেড ৪ (Proliferative DR): নতুন ভঙ্গুর রক্তনালী সৃষ্টি। জরুরি অস্ত্রোপচার/চিকিৎসা প্রয়োজন।"
        ),
        'mr': (
            "DrishtiAI डायबेटिक रेटिनोपॅथीचे ५ आंतरराष्ट्रीय टप्प्यांत वर्गीकरण करते:\n\n"
            "• ग्रेड ० (No DR): डोळ्यांचा पडदा निरोगी आहे.\n"
            "• ग्रेड १ (Mild DR): केवळ सूक्ष्म बदल (Microaneurysms). वार्षिक तपासणी पुरेशी.\n"
            "• ग्रेड २ (Moderate DR): रक्तस्राव आणि पाझरणे. नेत्रतज्ज्ञांचा सल्ला आवश्यक.\n"
            "• ग्रेड ३ (Severe DR): डोळ्याच्या पडद्यावर तीव्र रक्तस्राव. त्वरित तज्ज्ञ डॉक्टरांकडे जाणे आवश्यक.\n"
            "• ग्रेड ४ (Proliferative DR): नवीन नाजूक रक्तवाहिन्या. अंधत्व टाळण्यासाठी त्वरित उपचार आवश्यक."
        ),
        'ta': (
            "DrishtiAI நீரிழிவு விழித்திரை நோயை 5 சர்வதேச மருத்துவ நிலைகளாகப் பிரிக்கிறது:\n\n"
            "• நிலை 0 (No DR): விழித்திரை முற்றிலும் ஆரோக்கியமாக உள்ளது.\n"
            "• நிலை 1 (Mild DR): மிக ஆரம்ப நிலை. ஆண்டுதோறும் பரிசோதனை தேவை.\n"
            "• நிலை 2 (Moderate DR): மிதமான ரத்தக் கசிவு. கண் மருத்துவரிடம் ஆலோசனை பெறவும்.\n"
            "• நிலை 3 (Severe DR): தீவிர ரத்தக் கசிவு. உடனடியாக நிபுணரிடம் பரிந்துரை தேவை.\n"
            "• நிலை 4 (Proliferative DR): புதிய பலவீனமான ரத்த நாளங்கள். பார்வை இழப்பைத் தடுக்க அவசர சிகிச்சை தேவை."
        )
    },
    {
        'id': 'dr_symptoms',
        'keywords': ['symptoms', 'dr symptoms', 'signs', 'warning signs', 'लक्षण', 'संकेत', 'symptom kya hai', 'lakshan', 'উপসর্গ', 'लक्षणे', 'அறிகுறிகள்'],
        'en': (
            "In early stages, Diabetic Retinopathy often has NO warning symptoms! That is why regular annual retinal screening is vital.\n\n"
            "As it advances, symptoms may include:\n"
            "• Blurry or fluctuating vision\n"
            "• Floating dark spots or cobweb-like strings (floaters)\n"
            "• Dark or empty areas in your field of vision\n"
            "• Difficulty seeing at night or impaired color perception\n\n"
            "Note: If you experience sudden vision loss, consult an eye hospital immediately."
        ),
        'hi': (
            "शुरुआती चरणों में डायबिटिक रेटिनोपैथी के अक्सर कोई लक्षण नहीं होते! इसीलिए हर साल रेटिना की नियमित जांच अनिवार्य है।\n\n"
            "बढ़ने पर ये लक्षण दिख सकते हैं:\n"
            "• धुंधला या बदलता हुआ दिखना\n"
            "• आंखों के सामने काले धब्बे या जाले तैरते दिखना (Floaters)\n"
            "• दृष्टि के किसी हिस्से में कालापन\n"
            "• रात में देखने में कठिनाई\n\n"
            "ध्यान दें: अचानक रोशनी कम होने पर तुरंत नेत्र अस्पताल जाएं।"
        ),
        'hinglish': (
            "Early stage me DR ke aksar koi symptoms nahi hote, isliye annual screening zaroori hai!\n\n"
            "Badhne par ye signs milte hain:\n"
            "• Blurred ya fluctuating vision\n"
            "• Eye ke samne dark spots ya floaters tairna\n"
            "• Night vision me problem aana\n"
            "• Colors ka feeka lagna\n\n"
            "Important: Achanak vision chali jaye toh turant emergency hospital jayein."
        ),
        'bn': (
            "প্রাথমিক পর্যায়ে ডায়াবেটিক রেটিনোপ্যাথির কোনো স্পষ্ট লক্ষণ থাকে না! তাই নিয়মিত পরীক্ষা অপরিহার্য।\n\n"
            "রোগ বাড়লে:\n"
            "• দৃষ্টি ঝাপসা হওয়া\n"
            "• চোখের সামনে কালো দাগ বা জালের মতো ভাসা\n"
            "• রাতে দেখতে অসুবিধা\n\n"
            "সতর্কতা: হঠাৎ দৃষ্টি চলে গেলে অবিলম্বে হাসপাতালে যান।"
        ),
        'mr': (
            "सुरुवातीच्या काळात डायबेटिक रेटिनोपॅथीची कोणतीही लक्षणे दिसत नाहीत! म्हणूनच वार्षिक तपासणी महत्त्वाची आहे.\n\n"
            "आजार वाढल्यास:\n"
            "• नजर अंधुक होणे\n"
            "• डोळ्यांसमोर काळे ठिपके तरंगणे\n"
            "• रात्री कमी दिसणे\n\n"
            "सूचना: अचानक दृष्टी कमी झाल्यास त्वरित नेत्र रुग्णालयात जा."
        ),
        'ta': (
            "ஆரம்ப நிலையில் எந்தவித எச்சரிக்கை அறிகுறிகளும் இருக்காது! எனவே வருடாந்திர பரிசோதனை அவசியம்.\n\n"
            "முற்றிய நிலையில்:\n"
            "• மங்கலான பார்வை\n"
            "• கண்களின் முன் கருப்புப் புள்ளிகள் மிதப்பது\n"
            "• இரவில் பார்ப்பதில் சிரமம்\n\n"
            "குறிப்பு: திடீரென பார்வை குறைந்தால் உடனே கண் மருத்துவமனைக்குச் செல்லுங்கள்."
        )
    },
    {
        'id': 'gradcam',
        'keywords': ['gradcam', 'grad cam', 'grad-cam', 'heatmap', 'explanation', 'why heatmap', 'attention', 'हीटमैप', 'ग्रैडकैम', 'gradcam kya hai', 'হিটম্যাপ', 'ஹீட்மேப்'],
        'en': (
            "Grad-CAM (Gradient-weighted Class Activation Mapping) is our Explainable AI (XAI) feature. "
            "Instead of giving an unverified prediction, Grad-CAM creates a visual attention heatmap overlaid on the fundus photograph. "
            "Warm colors (red/orange) highlight the specific retinal areas and lesions that led the deep learning model to its prediction. "
            "This empowers community health workers and clinicians to verify the clinical reasoning behind every screening."
        ),
        'hi': (
            "Grad-CAM हमारी पारदर्शी व्याख्यात्मक AI (Explainable AI) तकनीक है। "
            "यह केवल परिणाम नहीं बताता, बल्कि रेटिना की फोटो पर लाल और पीले रंगों का हीटमैप बनाकर दिखाता है कि AI ने किन घावों या रक्त वाहिकाओं को देखकर यह निर्णय लिया है। "
            "इससे स्वास्थ्य कार्यकर्ता और डॉक्टर AI के तर्क को अपनी आंखों से देखकर सत्यापित कर सकते हैं।"
        ),
        'hinglish': (
            "Grad-CAM ek Explainable AI technique hai. "
            "Ye fundus photo par heat color overlay banata hai jisme red/orange areas batate hain ki AI model ne prediction dete waqt kin lesions (hemorrhages/exudates) par focus kiya. "
            "Isse doctors aur screeners AI ke decision ko visually verify kar sakte hain."
        ),
        'bn': (
            "Grad-CAM হলো বোধগম্য কৃত্রিম বুদ্ধিমত্তা (XAI)। "
            "এটি রেটিনা ছবির ওপর একটি ভিজ্যুয়াল হিটম্যাপ তৈরি করে দেখায় যে AI মডেল রেটিনার কোন অংশের ক্ষতির ওপর ভিত্তি করে ফলাফল নির্ধারণ করেছে।"
        ),
        'mr': (
            "Grad-CAM हे आमचे स्पष्टीकरण देणारे AI (XAI) तंत्रज्ञान आहे. "
            "हे केवळ निकाल सांगत नाही, तर रंगांच्या साहाय्याने पडद्यावरील कोणत्या भागाकडे मॉडेलने लक्ष दिले ते स्पष्ट करते."
        ),
        'ta': (
            "Grad-CAM என்பது வெளிப்படையான AI (XAI) தொழில்நுட்பம் ஆகும். "
            "இது விழித்திரை படத்தில் எந்தப் பகுதியை வைத்து AI முடிவெடுத்தது என்பதை வண்ண ஹீட்மேப் மூலம் தெளிவாகக் காட்டுகிறது."
        )
    },
    {
        'id': 'segmentation',
        'keywords': ['segmentation', 'retinal segmentation', 'unet', 'u-net', 'lesion segmentation', 'optic disc', 'सेगमेंटेशन', 'नक्शा', 'segmentation kya hai', 'সেগমেন্টেশন', 'பிரித்தல்'],
        'en': (
            "Retinal segmentation is powered by our IDRiD-trained U-Net deep learning model. "
            "It conducts pixel-level mapping to identify and isolate specific microvascular lesions:\n"
            "• Microaneurysms (MA)\n"
            "• Hemorrhages (HE)\n"
            "• Hard Exudates (EX)\n"
            "• Optic Disc (OD)\n"
            "You can toggle between Original, Segmentation Mask, and Blended Overlays on the screening result page."
        ),
        'hi': (
            "रेटिनल सेगमेंटेशन हमारे IDRiD U-Net डीप लर्निंग मॉडल द्वारा संचालित है। "
            "यह रेटिना के प्रत्येक पिक्सेल की जांच करके घावों को अलग-अलग रंगों में मैप करता है:\n"
            "• माइक्रोएन्यूरिज्म (MA)\n"
            "• रक्तस्राव (Hemorrhages - HE)\n"
            "• सख्त रिसाव (Hard Exudates - EX)\n"
            "• ऑप्टिक डिस्क (Optic Disc - OD)\n"
            "परिणाम पृष्ठ पर आप मूल फोटो, मास्क और ओवरले दृश्य के बीच स्विच कर सकते हैं।"
        ),
        'hinglish': (
            "Retinal segmentation hamara U-Net deep learning model hai jo IDRiD dataset par trained hai. "
            "Ye pixel-by-pixel retinal lesions detect karta hai jaise Microaneurysms (MA), Hemorrhages (HE), Hard Exudates (EX) aur Optic Disc (OD). "
            "Result page par aap mask aur overlay view toggle karke detailed analysis dekh sakte hain."
        ),
        'bn': (
            "আমাদের U-Net ডিপ লার্নিং মডেলের মাধ্যমে রেটিনাল সেগমেন্টেশন সম্পন্ন হয়। "
            "এটি প্রতিটি পিক্সেল স্তরে মাইক্রোঅ্যানিউরিজম, রক্তক্ষরণ এবং অপটিক ডিস্ক নিখুঁতভাবে চিহ্নিত করে।"
        ),
        'mr': (
            "रेटिनल सेगमेंटेशन U-Net मॉडेलद्वारे चालवले जाते. "
            "हे डोळ्यातील मायक्रोॲन्युरिझम, रक्तस्राव आणि ऑप्टिक डिस्क पिक्सेल पातळीवर ओळखून स्वतंत्रपणे दाखवते."
        ),
        'ta': (
            "விழித்திரை பிரித்தல் (Segmentation) U-Net ஆழ்ந்த கற்றல் மாதிரி மூலம் இயக்கப்படுகிறது. "
            "இது மைக்ரோஅன்யூரிஸம்கள், ரத்தக் கசிவுகள் மற்றும் ஆப்டிக் டிஸ்க் ஆகியவற்றை பிக்சல் அளவில் துல்லியமாக அடையாளப்படுத்துகிறது."
        )
    },
    {
        'id': 'upload_help',
        'keywords': ['how to upload', 'upload image', 'upload fundus', 'take picture', 'upload photo', 'new screening', 'इमेज कैसे अपलोड करें', 'अपलोड', 'upload kaise kare', 'আপলোড', 'अपलोड कसे करावे', 'பதிவேற்றுவது எப்படி'],
        'en': (
            "To screen a patient's retina:\n"
            "1. Click 'New Screening' in the top navigation bar.\n"
            "2. Select one of the preloaded clinical sample cases, or drag & drop an authentic retinal fundus photograph (JPG, JPEG, or PNG up to 10 MB).\n"
            "3. Click 'Analyze Retinal Image'. The multi-stage AI pipeline validates the photo, predicts DR severity, generates Grad-CAM heatmaps, and segments lesions within seconds."
        ),
        'hi': (
            "मरीज की रेटिना जांच करने के लिए:\n"
            "1. ऊपर नेविगेशन बार में 'New Screening' (नई जांच) पर क्लिक करें।\n"
            "2. कोई प्रीलोडेड सैंपल चुनें, या अपने डिवाइस से साफ रेटिनल फंडस फोटो (JPG/PNG अधिकतम 10 MB) ड्रैग और ड्रॉप करें।\n"
            "3. 'Analyze Retinal Image' पर क्लिक करें। सिस्टम कुछ ही सेकंड में फोटो की पुष्टि कर AI परिणाम, हीटमैप और सेगमेंटेशन तैयार कर देगा।"
        ),
        'hinglish': (
            "New screening karne ke steps:\n"
            "1. Top menu me 'New Screening' par click karein.\n"
            "2. Sample case select karein ya browse karke clear retinal fundus image (JPG/PNG max 10MB) upload karein.\n"
            "3. 'Analyze Retinal Image' button dabayein. AI model image validate karke Grad-CAM aur segmentation ke sath result show karega."
        ),
        'bn': (
            "রোগীর রেটিনা স্ক্রিনিং করতে:\n"
            "১. 'New Screening' অপশনে ক্লিক করুন।\n"
            "২. নমুনা ছবি বা ফানডাস ক্যামেরা থেকে তোলা পরিষ্কার ছবি আপলোড করুন।\n"
            "৩. 'Analyze Retinal Image' বাটনে ক্লিক করুন। কয়েক সেকেন্ডেই ফলাফল পাওয়া যাবে।"
        ),
        'mr': (
            "तपासणीसाठी:\n"
            "१. 'New Screening' वर क्लिक करा.\n"
            "२. फंडस कॅमेऱ्याचा फोटो निवडा किंवा अपलोड करा.\n"
            "३. 'Analyze Retinal Image' बटण दाबा. काही सेकंदांत संपूर्ण निकाल समोर येईल."
        ),
        'ta': (
            "பரிசோதனை செய்ய:\n"
            "1. 'New Screening' கிளிக் செய்யவும்.\n"
            "2. விழித்திரை புகைப்படத்தைப் பதிவேற்றவும்.\n"
            "3. 'Analyze Retinal Image' பொத்தானை அழுத்தவும். சில நொடிகளில் முடிவு கிடைக்கும்."
        )
    },
    {
        'id': 'rejected_image',
        'keywords': ['why was my image rejected', 'image rejected', 'invalid image', 'validation failed', 'rejection', 'इमेज रिजेक्ट क्यों', 'अमान्य इमेज', 'image reject kyu hui', 'ছবি বাতিল', 'फोटो नाकारला', 'படம் நிராகரிக்கப்பட்டது'],
        'en': (
            "DrishtiAI includes an automated multi-feature domain validator to protect clinical safety. A photo is rejected if:\n"
            "• It is not a retinal fundus image (e.g. general object, external eye photo, face, or document).\n"
            "• Image illumination is severely underexposed (too dark) or overexposed (washed out).\n"
            "• Retinal vascular contrast or circular field-of-view is insufficient.\n\n"
            "Please ensure you upload a standard non-mydriatic or dilated fundus camera photograph."
        ),
        'hi': (
            "मरीजों की सुरक्षा के लिए DrishtiAI फोटो की गुणवत्ता और वैधता की स्वचालित जांच करता है। फोटो इन कारणों से रिजेक्ट हो सकती है:\n"
            "• फोटो रेटिना फंडस की न होकर किसी वस्तु, चेहरे या बाहरी आंख की हो।\n"
            "• फोटो बहुत अधिक अंधेरी (underexposed) या बहुत ज्यादा चमकीली (overexposed) हो।\n"
            "• रेटिना की रक्त नलिकाएं या गोलाकार दृश्य स्पष्ट न हो।\n\n"
            "कृपया केवल मानक रेटिनल फंडस कैमरा से ली गई फोटो ही अपलोड करें।"
        ),
        'hinglish': (
            "DrishtiAI clinical safety ke liye image quality check karta hai. Image reject hone ke reasons:\n"
            "• Photo retinal fundus ki nahi hai (face, general photo ya document).\n"
            "• Photo bohot zyada dark ya overexposed/whiteout hai.\n"
            "• Circular retina boundary ya blood vessels clearly visible nahi hain.\n\n"
            "Kripya standard fundus camera se li gayi clear image upload karein."
        ),
        'bn': (
            "নিরাপত্তার স্বার্থে DrishtiAI স্বয়ংক্রিয়ভাবে ছবির মান যাচাই করে। ছবি বাতিল হতে পারে যদি:\n"
            "• এটি আসল রেটিনা ফানডাস ছবি না হয়।\n"
            "• ছবি অতিরিক্ত অন্ধকার, অতি-উজ্জ্বল বা অস্পষ্ট হয়।"
        ),
        'mr': (
            "तपासणीच्या सुरक्षिततेसाठी DrishtiAI फोटोची गुणवत्ता तपासते. फोटो नाकारण्याचे कारण:\n"
            "• फोटो डोळ्याच्या पडद्याचा नसून इतर वस्तूचा किंवा चेहऱ्याचा असणे.\n"
            "• फोटो अतिशय अंधुक किंवा खूप तेजस्वी असणे."
        ),
        'ta': (
            "மருத்துவப் பாதுகாப்பிற்காக DrishtiAI படத்தின் தரத்தை சரிபார்க்கிறது. படம் நிராகரிக்கப்படக் காரணங்கள்:\n"
            "• படம் விழித்திரை படமாக இல்லாமல் முகமாகவோ வேறு பொருளாகவோ இருப்பது.\n"
            "• படம் அதிக இருட்டாகவோ அல்லது அதிக வெளிச்சமாகவோ இருப்பது."
        )
    },
    {
        'id': 'otp_help',
        'keywords': ['otp not arriving', 'otp issue', 'why no otp', 'otp problem', 'resend otp', 'otp नहीं आ रहा', 'ओटीपी समस्या', 'otp nahi aa raha', 'ওটিপি সমস্যা', 'ओटीपी येत नाही', 'OTP வரவில்லை'],
        'en': (
            "If your verification OTP is not arriving:\n"
            "1. Ensure you entered a valid 10-digit mobile number.\n"
            "2. Watch the 60-second countdown timer on the screen; once it reaches zero, click 'Resend OTP'.\n"
            "3. Check your mobile network reception.\n"
            "4. For demonstration/evaluation testing, you can use the instant Demo OTP code (652070) displayed on the screen."
        ),
        'hi': (
            "यदि आपका सत्यापन OTP नहीं आ रहा है:\n"
            "1. जांच लें कि आपका 10 अंकों का मोबाइल नंबर सही दर्ज किया गया है।\n"
            "2. स्क्रीन पर 60 सेकंड का टाइमर देखें; शून्य होने पर 'Resend OTP' बटन दबाएं।\n"
            "3. अपने फोन का नेटवर्क सिग्नल चेक करें।\n"
            "4. डेमो मूल्यांकन के लिए स्क्रीन पर दिया गया डेमो कोड (652070) तुरंत उपयोग कर सकते हैं।"
        ),
        'hinglish': (
            "Agar OTP receive nahi ho raha:\n"
            "1. Check karein ki 10-digit mobile number sahi enter kiya hai.\n"
            "2. Screen par 60-second timer khatam hone ke baad 'Resend OTP' dabayein.\n"
            "3. Phone ka network connection check karein.\n"
            "4. Testing aur demo ke liye screen par diya gaya Demo OTP (652070) use karke direct login kar sakte hain."
        ),
        'bn': (
            "যদি OTP না আসে:\n"
            "১. মোবাইল নম্বর সঠিক কিনা যাচাই করুন।\n"
            "২. ৬০ সেকেন্ড পর 'Resend OTP' বাটনে চাপ দিন।\n"
            "৩. ডেমো পরীক্ষার জন্য স্ক্রিনে দেখানো কোড (652070) ব্যবহার করতে পারেন।"
        ),
        'mr': (
            "OTP येत नसल्यास:\n"
            "१. मोबाईल क्रमांक योग्य असल्याची खात्री करा.\n"
            "२. ६० सेकंदांनंतर 'Resend OTP' दाबा.\n"
            "३. चाचणीसाठी स्क्रीनवर दिसणारा डेमो कोड (652070) वापरू शकता."
        ),
        'ta': (
            "OTP வரவில்லை என்றால்:\n"
            "1. 10 இலக்க மொபைல் எண் சரியானதா என சரிபார்க்கவும்.\n"
            "2. 60 வினாடிகளுக்குப் பிறகு 'Resend OTP' அழுத்தவும்.\n"
            "3. டெமோ பரிசோதனைக்கு திரையில் உள்ள (652070) குறியீட்டைப் பயன்படுத்தலாம்."
        )
    },
    {
        'id': 'account_and_history',
        'keywords': ['history', 'screening history', 'my history', 'csv export', 'download csv', 'logout', 'account', 'audit log', 'इतिहास', 'लॉगआउट', 'csv डाउनलोड', 'history kaise dekhe', 'ইতিহাস', 'इतिहास', 'வரலாறு'],
        'en': (
            "Your DrishtiAI account ensures strict user data isolation:\n"
            "• Screening History: Click 'History' in the top navbar to see all screenings performed under your account.\n"
            "• Search & Filter: Filter by severity grade (0 to 4) or search by patient ID.\n"
            "• Export CSV: Click 'Export CSV' on the History page to download your records.\n"
            "• Privacy & Isolation: You can never view or access another user's screening records.\n"
            "• Sign Out: Click the exit icon next to your name in the navbar to log out safely."
        ),
        'hi': (
            "आपका DrishtiAI खाता डेटा सुरक्षा और पृथक्करण सुनिश्चित करता है:\n"
            "• स्क्रीनिंग इतिहास: अपने खाते की सभी जांच देखने के लिए ऊपर 'History' पर क्लिक करें।\n"
            "• फ़िल्टर और खोज: गंभीरता ग्रेड (0 से 4) के आधार पर फ़िल्टर करें या पेशेंट ID खोजें।\n"
            "• CSV डाउनलोड: अपने रिकॉर्ड्स को डाउनलोड करने के लिए 'Export CSV' बटन दबाएं।\n"
            "• गोपनीयता: एक उपयोगकर्ता दूसरे उपयोगकर्ता का डेटा कभी नहीं देख सकता।\n"
            "• लॉगआउट: सुरक्षित बाहर निकलने के लिए अपने नाम के पास दिए गए साइन आउट आइकन पर क्लिक करें।"
        ),
        'hinglish': (
            "DrishtiAI account me strict user isolation hota hai:\n"
            "• History: Top bar me 'History' par click karke aap sirf apne kiye hue screenings dekh sakte hain.\n"
            "• Filter & Search: Grade 0-4 filter karein ya Patient ID search karein.\n"
            "• Export CSV: Apne records ko CSV format me download karne ke liye 'Export CSV' button dabayein.\n"
            "• Privacy: User A kabhi User B ka record nahi dekh sakta.\n"
            "• Logout: Top right profile ke paas logout icon par click karein."
        ),
        'bn': (
            "আপনার অ্যাকাউন্ট সম্পূর্ণ ব্যক্তিগত ও সুরক্ষিত:\n"
            "• 'History' থেকে আপনার অতীতের সমস্ত স্ক্রিনিং রেকর্ড দেখা যাবে।\n"
            "• 'Export CSV' দিয়ে রেকর্ড ডাউনলোড করা সম্ভব। অন্য ব্যবহারকারীর রেকর্ড সুরক্ষিত থাকে।"
        ),
        'mr': (
            "तुमचे खाते सुरक्षित आहे:\n"
            "• 'History' पृष्ठावर तुमच्या सर्व नोंदी दिसतील.\n"
            "• 'Export CSV' बटणाने डेटा डाउनलोड करा. इतरांचा डेटा पूर्णपणे सुरक्षित राहतो."
        ),
        'ta': (
            "உங்கள் கணக்கு தனிப்பட்ட பாதுகாப்பைக் கொண்டது:\n"
            "• 'History' பக்கத்தில் உங்களின் அனைத்து பரிசோதனைப் பதிவுகளையும் பார்க்கலாம்.\n"
            "• 'Export CSV' மூலம் பதிவிறக்கலாம். பிறரின் விவரங்களை யாரும் பார்க்க முடியாது."
        )
    },
    {
        'id': 'voice_features',
        'keywords': ['voice', 'voice feature', 'how to use voice', 'microphone', 'audio', 'tts', 'text to speech', 'stt', 'बोलकर', 'आवाज कैसे इस्तेमाल करें', 'माइक', 'voice feature kya hai', 'ভয়েস', 'व्हॉईस', 'குரல்'],
        'en': (
            "DrishtiAI includes built-in multi-language hands-free voice features:\n"
            "• Speech-to-Text (Voice Input): Click the microphone icon in the top toolbar or inside this chatbot drawer to dictate in your selected language.\n"
            "• Text-to-Speech (Voice Output): Click 'Read Report Aloud' on any screening result page or the speaker icon on chat bubbles to listen to the summary aloud.\n"
            "• Voice Search: Dictate search queries on the History page using the microphone in the search bar."
        ),
        'hi': (
            "DrishtiAI में हाथों के उपयोग के बिना बोलने और सुनने की सुविधाएं उपलब्ध हैं:\n"
            "• बोलकर टाइप करें: ऊपर टूलबार या चैटबॉट में माइक आइकन दबाकर अपनी भाषा में बोलें।\n"
            "• बोलकर सुनें (TTS): रिजल्ट पेज पर 'Read Report Aloud' या चैट बबल पर स्पीकर आइकन दबाकर रिपोर्ट सुनें।\n"
            "• वॉयस सर्च: हिस्ट्री पेज पर माइक बटन दबाकर मरीज का नाम या ID बोलकर खोजें।"
        ),
        'hinglish': (
            "DrishtiAI me hands-free voice feature available hai:\n"
            "• Voice Input (STT): Top bar me ya chatbot me Mic button daba kar English ya Hindi me bolein.\n"
            "• Voice Output (TTS): Result page par 'Read Report Aloud' ya chat bubble par speaker icon daba kar sunnein.\n"
            "• Voice Search: History page par bolkar patient search kar sakte hain."
        ),
        'bn': (
            "DrishtiAI-তে কণ্ঠস্বরের মাধ্যমে কাজ করার সুবিধা রয়েছে:\n"
            "• ভয়েস ইনপুট: মাইক বাটনে চাপ দিয়ে সরাসরি কথা বলে টাইপ করুন।\n"
            "• ভয়েস আউটপুট: 'Read Report Aloud' বাটনে চাপ দিয়ে ফলাফল শুনে নিন।"
        ),
        'mr': (
            "DrishtiAI मध्ये व्हॉईस सुविधा उपलब्ध आहे:\n"
            "• व्हॉईस इनपुट: मायक्रोफोन बटण दाबून बोलून टाइप करा.\n"
            "• व्हॉईस आउटपुट: 'Read Report Aloud' बटण दाबून संपूर्ण रिपोर्ट ऐका."
        ),
        'ta': (
            "DrishtiAI-ல் பல மொழி குரல் வசதிகள் உள்ளன:\n"
            "• குரல் உள்ளீடு: மைக்ரோஃபோனை அழுத்திப் பேசி உள்ளிடலாம்.\n"
            "• அறிக்கை வாசிப்பு: 'Read Report Aloud' அழுத்தி முடிவுகளைக் குரல் வடிவில் கேட்கலாம்."
        )
    },
    {
        'id': 'accessibility_theme_lang',
        'keywords': ['dark mode', 'theme', 'change language', 'hindi english', 'zoom', 'font size', 'text size', 'डार्क मोड', 'भाषा', 'हिन्दी', 'भाषा कैसे बदलें', 'theme change', 'ভাষা পরিবর্তন', 'भाषा बदला', 'மொழி மாற்றம்'],
        'en': (
            "Accessibility and display controls are located in the top-right toolbar:\n"
            "• Theme: Click the Moon/Sun icon to toggle between Light and Dark high-contrast clinical themes.\n"
            "• Language: Switch between English, हिन्दी, Hinglish, বাংলা, मराठी, and தமிழ் seamlessly.\n"
            "• Text Scaling: Use the A-, A, and A+ buttons to scale typography for comfortable reading."
        ),
        'hi': (
            "सुगमता और प्रदर्शन विकल्प ऊपर दाईं ओर दिए गए टूलबार में हैं:\n"
            "• थीम: लाइट और डार्क मोड के बीच स्विच करने के लिए चांद/सूरज के आइकन पर क्लिक करें।\n"
            "• भाषा: English, हिन्दी, Hinglish, বাংলা, मराठी, और தமிழ் में से अपनी पसंदीदा भाषा चुनें।\n"
            "• टेक्स्ट साइज: अक्षरों का आकार छोटा, सामान्य या बड़ा करने के लिए A-, A, A+ का उपयोग करें।"
        ),
        'hinglish': (
            "Accessibility controls top-right bar me hain:\n"
            "• Theme: Moon/Sun icon se Light aur Dark mode switch karein.\n"
            "• Language: 6 languages (English, Hindi, Hinglish, Bengali, Marathi, Tamil) switch karein.\n"
            "• Text Size: A-, A, A+ buttons se font size adjust karein."
        ),
        'bn': (
            "ব্যবহারের সুবিধার্থে উপরে নিয়ন্ত্রণ বাটন রয়েছে:\n"
            "• থিম: লাইট ও ডার্ক মোড পরিবর্তন করুন।\n"
            "• ভাষা: ইংরেজি, হিন্দি, হিংলিশ, বাংলা, মারাঠি ও তামিল ভাষা নির্বাচন করুন।\n"
            "• লেখার আকার: A-, A, A+ দিয়ে ফন্ট সাইজ নিয়ন্ত্রণ করুন।"
        ),
        'mr': (
            "सुविधा नियंत्रण पर्याय:\n"
            "• थीम: लाइट आणि डार्क मोड स्विच करा.\n"
            "• भाषा: इंग्रजी, हिंदी, हिंग्लिश, बंगाली, मराठी किंवा तमिळ भाषा निवडा.\n"
            "• अक्षरांचा आकार: A-, A, A+ बटणांनी फॉन्ट आकार बदला."
        ),
        'ta': (
            "பயன்பாட்டு வசதிகள் மேல்பகுதியில் உள்ளன:\n"
            "• தீம்: வெளிச்சம் மற்றும் இருண்ட பயன்முறை மாற்றம்.\n"
            "• மொழி: ஆங்கிலம், இந்தி, ஹிங்கிலிஷ், வங்கம், மராத்தி மற்றும் தமிழ் மொழி மாற்றம்.\n"
            "• எழுத்து அளவு: A-, A, A+ பொத்தான்கள் மூலம் எழுத்து அளவை மாற்றலாம்."
        )
    },
    {
        'id': 'rural_mission',
        'keywords': ['rural', 'vision centre', 'phc', 'teleophthalmology', 'mission', 'aim', 'ग्रामीण', 'उद्देश्य', 'rural health', 'গ্রামীণ মিশন', 'ग्रामीण आरोग्य', 'கிராமப்புற நோக்கம்'],
        'en': (
            "RETINA-XAI (DrishtiAI) is engineered specifically for rural and underserved vision centres and primary health centres (PHCs) across India. "
            "Because over 70% of diabetic patients live in rural areas with severe shortages of ophthalmologists, our lightweight system runs on low-resource hardware, "
            "empowering community healthcare workers to conduct rapid, transparent, and explainable diabetic retinopathy triage."
        ),
        'hi': (
            "RETINA-XAI (DrishtiAI) को भारत के ग्रामीण व प्राथमिक स्वास्थ्य केंद्रों (PHCs) और विजन सेंटरों के लिए विशेष रूप से डिज़ाइन किया गया है। "
            "भारत के 70% से अधिक मधुमेह रोगी ग्रामीण इलाकों में रहते हैं जहाँ नेत्र विशेषज्ञों की भारी कमी है। "
            "हमारा सिस्टम कम संसाधनों वाले हार्डवेयर पर भी पारदर्शी और त्वरित रेटिना जांच की सुविधा प्रदान करता है।"
        ),
        'hinglish': (
            "RETINA-XAI (DrishtiAI) India ke rural vision centres aur PHCs ke liye specially design kiya gaya hai. "
            "Rural areas me ophthalmologists ki kami ko door karne ke liye ye lightweight AI triage provide karta hai taaki frontline health workers transparently DR screening kar sakein."
        ),
        'bn': (
            "RETINA-XAI (DrishtiAI) বিশেষভাবে গ্রামীণ প্রাথমিক স্বাস্থ্য কেন্দ্রের জন্য তৈরি। "
            "গ্রামীণ এলাকায় চক্ষু বিশেষজ্ঞের স্বল্পতা দূর করতে এটি স্বাস্থ্যকর্মীদের স্বচ্ছ ও দ্রুত স্ক্রিনিং করতে সক্ষম করে।"
        ),
        'mr': (
            "RETINA-XAI (DrishtiAI) ग्रामीण प्राथमिक आरोग्य केंद्रांसाठी डिझाइन केलेले आहे. "
            "ग्रामीण भागातील डोळ्यांच्या डॉक्टरांची कमतरता लक्षात घेऊन हे हलके आणि पारदर्शक AI साधन तयार करण्यात आले आहे."
        ),
        'ta': (
            "RETINA-XAI (DrishtiAI) இந்தியாவின் கிராமப்புற ஆரம்ப சுகாதார நிலையங்களுக்காக உருவாக்கப்பட்டது. "
            "கண் மருத்துவர்கள் பற்றாக்குறை உள்ள கிராமப்புறங்களில் துரித விழித்திரை பரிசோதனையை வழங்க இது உதவுகிறது."
        )
    }
]

# -------------------------------------------------------------------
# Out-of-Scope Response Generator
# -------------------------------------------------------------------
def get_out_of_scope_response(lang: str) -> str:
    if lang == 'hi':
        return (
            "मैं दृष्टिAI सहायक हूँ, और मैं मुख्य रूप से डायबिटिक रेटिनोपैथी तथा DrishtiAI ऐप के उपयोग में सहायता करता हूँ। "
            "यह प्रश्न मेरे कार्यक्षेत्र से बाहर है। आप मुझसे आंखों के स्वास्थ्य, DR स्क्रीनिंग, अपने परिणाम या ऐप के उपयोग से संबंधित कोई भी सवाल पूछ सकते हैं। 😊"
        )
    elif lang == 'hinglish':
        return (
            "Main DrishtiAI Assistant hoon, aur main primarily Diabetic Retinopathy aur DrishtiAI app use karne me help karta hoon. "
            "Yeh question mere scope ke bahar hai. Aap mujhse eye health, DR screening, result explanation ya app problem ke baare me pooch sakte hain. 😊"
        )
    elif lang == 'bn':
        return (
            "আমি DrishtiAI সহকারী। আমি মূলত ডায়াবেটিক রেটিনোপ্যাথি এবং DrishtiAI অ্যাপ্লিকেশন ব্যবহারে সহায়তা করি। "
            "এই প্রশ্নটি আমার আওতার বাইরে। আপনি চোখের স্বাস্থ্য, স্ক্রিনিং ফলাফল বা অ্যাপ সম্পর্কিত প্রশ্ন করতে পারেন। 😊"
        )
    elif lang == 'mr':
        return (
            "मी DrishtiAI सहाय्यक आहे. मी प्रामुख्याने डायबेटिक रेटिनोपॅथी आणि DrishtiAI ॲप संदर्भात मदत करतो. "
            "हा प्रश्न माझ्या कार्यकक्षेबाहेर आहे. आपण डोळ्यांचे आरोग्य किंवा ॲपबद्दल विचारू शकता. 😊"
        )
    elif lang == 'ta':
        return (
            "நான் DrishtiAI உதவியாளர். நான் முதன்மையாக நீரிழிவு விழித்திரை நோய் மற்றும் DrishtiAI செயலியைப் பயன்படுத்துவதில் உதவுகிறேன். "
            "இந்தக் கேள்வி எனது எல்லைக்கு அப்பாற்பட்டது. நீங்கள் கண் நலம் அல்லது செயலி பற்றி கேட்கலாம். 😊"
        )
    return (
        "I'm DrishtiAI Assistant, so I mainly help with Diabetic Retinopathy and using the DrishtiAI application. "
        "This question is outside my current scope. You can ask me about eye health, DR screening, your screening result, or any problem using the app. 😊"
    )

EMERGENCY_REPLIES = {
    'hi': (
        "⚠️ **तत्काल चिकित्सीय चेतावनी**: आपके द्वारा बताए गए लक्षण (जैसे अचानक रोशनी कम होना या तेज दर्द) गंभीर आपातकालीन स्थिति हो सकते हैं।\n\n"
        "DrishtiAI एक शुरुआती स्क्रीनिंग प्रोटोटाइप है और आपातकालीन चिकित्सा का विकल्प नहीं है। "
        "कृपया बिना किसी देरी के तुरंत अपने निकटतम नेत्र विशेषज्ञ या अस्पताल के आपातकालीन विभाग में संपर्क करें।"
    ),
    'hinglish': (
        "⚠️ **URGENT WARNING**: Aapke bataye gaye symptoms (achanak roshni kam hona ya severe eye pain) emergency situation ho sakte hain.\n\n"
        "DrishtiAI sirf screening tool hai, emergency medical care ka option nahi. "
        "Kripya bina kisi delay ke turant eye hospital ya emergency doctor se contact karein."
    ),
    'bn': (
        "⚠️ **জরুরি চিকিৎসা সতর্কতা**: আপনার বর্ণিত লক্ষণগুলো (হঠাৎ দৃষ্টি হ্রাস বা তীব্র চোখের ব্যথা) তীব্র জরুরি অবস্থা হতে পারে।\n\n"
        "DrishtiAI একটি স্ক্রিনিং প্ল্যাটফর্ম এবং জরুরি চিকিৎসার বিকল্প নয়। অবিলম্বে নিকটস্থ চক্ষু হাসপাতাল বা ডাক্তারের কাছে যান।"
    ),
    'mr': (
        "⚠️ **तातडीची वैद्यकीय सूचना**: आपण सांगितलेली लक्षणे (अचानक दृष्टी कमी होणे किंवा तीव्र वेदना) तातडीची आपत्कालीन स्थिती दर्शवतात.\n\n"
        "DrishtiAI हे प्राथमिक स्क्रीनिंग साधन असून आपत्कालीन उपचाराचा पर्याय नाही. कृपया विलंब न करता तात्काळ नेत्र रुग्णालयात संपर्क साधा."
    ),
    'ta': (
        "⚠️ **அவசர மருத்துவ எச்சரிக்கை**: நீங்கள் விவரித்த அறிகுறிகள் (திடீர் பார்வை இழப்பு அல்லது கடுமையான வலி) அவசர நிலையைக் குறிக்கலாம்.\n\n"
        "DrishtiAI ஒரு முதற்கட்ட பரிசோதனைக் கருவியாகும், அவசர சிகிச்சைக்கு மாற்றாகாது. உடனடியாக கண் மருத்துவமனைக்குச் செல்லவும்."
    ),
    'en': (
        "⚠️ **URGENT MEDICAL NOTICE**: The symptoms you described (such as sudden vision change, flashes, or severe eye pain) may indicate an acute eye emergency.\n\n"
        "DrishtiAI is an automated triage prototype and cannot manage clinical emergencies. "
        "Please seek immediate medical evaluation at an emergency eye hospital or contact an ophthalmologist without delay."
    )
}

DIAGNOSIS_REFUSALS = {
    'hi': (
        "DrishtiAI एक AI-सहायक स्क्रीनिंग प्रोटोटाइप है। यह स्वयं किसी बीमारी का अंतिम निदान नहीं करता और न ही दवाइयां लिखता है। "
        "कृपया किसी भी उपचार या दवा के लिए पंजीकृत नेत्र विशेषज्ञ (Ophthalmologist) से परामर्श लें।"
    ),
    'hinglish': (
        "DrishtiAI ek AI-assisted screening prototype hai. Ye direct medical diagnosis nahi karta aur na hi medicines prescribe karta hai. "
        "Kisi bhi treatment ya eye drops ke liye registered ophthalmologist (aankhon ke doctor) se consult karein."
    ),
    'bn': (
        "DrishtiAI একটি এআই স্ক্রিনিং প্রযুক্তি। এটি সরাসরি কোনো রোগ নির্ণয় করে না বা ওষুধ নির্দেশ করে না। "
        "যেকোনো চিকিৎসা বা ড্রপসের জন্য নিবন্ধিত চক্ষু চিকিৎসকের পরামর্শ নিন।"
    ),
    'mr': (
        "DrishtiAI हे प्राथमिक AI तपासणी साधन आहे. हे अंतिम रोगनिदान करत नाही किंवा औषध लिहून देत नाही. "
        "कोणत्याही उपचारासाठी नोंदणीकृत नेत्ररोग तज्ज्ञांचा सल्ला घ्या."
    ),
    'ta': (
        "DrishtiAI என்பது ஒரு AI பரிசோதனை உதவி மட்டுமே. இது நேரடியாக நோய் கண்டறிவதோ மருந்து பரிந்துரைப்பதோ இல்லை. "
        "சிகிச்சை அல்லது மருந்துகளுக்கு பதிவுபெற்ற கண் மருத்துவரை அணுகவும்."
    ),
    'en': (
        "DrishtiAI is an AI screening and educational prototype. It does not diagnose medical conditions directly or prescribe treatments/eye drops. "
        "All screening findings must be verified by a licensed ophthalmologist before taking any medication or medical action."
    )
}

class ChatbotService:
    """
    DrishtiAI Assistant Service.
    Enforces strict medical guardrails, handles casual conversation across 6 languages,
    answers domain-specific queries, politely bounds out-of-scope queries,
    and supports both external AI APIs and the built-in intelligent FAQ engine.
    """
    def __init__(self):
        self.ai_provider = os.environ.get('AI_PROVIDER', '').lower().strip()
        self.ai_api_key = os.environ.get('AI_API_KEY', '').strip()
        self.ai_model = os.environ.get('AI_MODEL', 'gemini-1.5-flash').strip()

    def handle_message(self, user_message: str, user_id: int = None, lang: str = 'en', history: list = None) -> dict:
        clean_text = (user_message or '').strip()
        if not clean_text:
            msg_map = {
                'hi': "कृपया अपना प्रश्न लिखें या बोलें।",
                'hinglish': "Kripya apna question type ya speak karein.",
                'bn': "অনুগ্রহ করে আপনার প্রশ্ন টাইপ করুন বা বলুন।",
                'mr': "कृपया आपला प्रश्न टाइप करा किंवा बोला.",
                'ta': "தயவுசெய்து உங்கள் கேள்வியை தட்டச்சு செய்யவும் அல்லது பேசவும்.",
                'en': "Please type or speak your question."
            }
            msg = msg_map.get(lang, msg_map['en'])
            return {'reply': msg, 'mode': 'faq', 'is_medical_warning': False, 'detected_lang': lang}

        # Automatically detect language of prompt
        detected_lang = detect_language(clean_text, default_lang=lang)
        lower_text = clean_text.lower()

        # 1. Check for Emergency Red Flags
        if any(keyword in lower_text for keyword in EMERGENCY_KEYWORDS):
            reply = EMERGENCY_REPLIES.get(detected_lang, EMERGENCY_REPLIES['en'])
            return {'reply': reply, 'mode': 'faq', 'is_medical_warning': True, 'detected_lang': detected_lang}

        # 2. Check for "Explain My Result" Intent
        explain_triggers = [
            'explain my result', 'explain result', 'latest result', 'my report',
            'mera result', 'result samjhao', 'meri report', 'परिणाम समझाएं',
            'रिजल्ट समझाओ', 'मेरा रिजल्ट', 'latest screening',
            'ফলাফল ব্যাখ্যা', 'निकाल समजून सांगा', 'முடிவை விளக்குங்கள்'
        ]
        if any(trigger in lower_text for trigger in explain_triggers):
            res = self._explain_user_result(user_id, detected_lang)
            res['detected_lang'] = detected_lang
            return res

        # 3. Check for Direct Medical Diagnosis / Prescription Requests
        diag_triggers = [
            'diagnose me', 'do i have', 'give me medicine', 'prescribe', 'what drops',
            'क्या मुझे चश्मा', 'दवा बताइए', 'इलाज बताइए', 'dawa batao', 'treatment do',
            'drops prescribe karo', 'ওষুধ দিন', 'औषध द्या', 'மருந்து கொடுங்கள்'
        ]
        if any(dt in lower_text for dt in diag_triggers):
            reply = DIAGNOSIS_REFUSALS.get(detected_lang, DIAGNOSIS_REFUSALS['en'])
            return {'reply': reply, 'mode': 'faq', 'is_medical_warning': False, 'detected_lang': detected_lang}

        # 4. If External AI API is configured, use it for rich conversational responses
        if self.ai_api_key and self.ai_provider in ('gemini', 'google', 'openai'):
            try:
                ai_reply = self._call_external_ai(clean_text, detected_lang, history)
                if ai_reply:
                    return {'reply': ai_reply, 'mode': 'ai', 'is_medical_warning': False, 'detected_lang': detected_lang}
            except Exception as e:
                logger.warning(f"External AI Provider failed ({e}), falling back to built-in FAQ.")

        # 5. Check for Casual Conversation Intents (Greetings, How are you, Jokes, Pets, etc.)
        casual_reply = self._match_casual(clean_text, detected_lang)
        if casual_reply:
            return {'reply': casual_reply, 'mode': 'faq', 'is_medical_warning': False, 'detected_lang': detected_lang}

        # 6. Check for Domain-Specific FAQ Knowledge
        faq_reply = self._match_faq(lower_text, detected_lang)
        if faq_reply:
            return {'reply': faq_reply, 'mode': 'faq', 'is_medical_warning': False, 'detected_lang': detected_lang}

        # 7. Out-of-Scope Fallback (Polite boundary setting instead of generic robotic repetition)
        out_of_scope = get_out_of_scope_response(detected_lang)
        return {'reply': out_of_scope, 'mode': 'faq', 'is_medical_warning': False, 'detected_lang': detected_lang}

    def _match_casual(self, text: str, lang: str) -> str:
        """Matches casual queries like greetings, jokes, how are you, pets, thanks, bye."""
        lower = text.lower().strip()
        for item in CASUAL_CONVERSATIONS:
            if re.search(item['pattern'], lower, re.IGNORECASE):
                return item.get(lang) or item.get('en')
        return None

    def _match_faq(self, query: str, lang: str) -> str:
        """Matches domain-specific diabetic retinopathy and DrishtiAI application questions."""
        best_match = None
        max_score = 0

        for entry in FAQ_KNOWLEDGE_BASE:
            score = 0
            for kw in entry['keywords']:
                if kw in query:
                    score += len(kw) * 2
            if score > max_score:
                max_score = score
                best_match = entry

        if best_match and max_score >= 6:
            return best_match.get(lang) or best_match.get('en')

        return None

    def _explain_user_result(self, user_id: int, lang: str = 'en') -> dict:
        """Explains the latest screening result specifically for the authenticated user."""
        no_login_msgs = {
            'hi': "कृपया अपनी रिपोर्ट देखने के लिए पहले लॉगिन करें।",
            'hinglish': "Apni screening report dekhne ke liye kripya pehle login karein.",
            'bn': "আপনার রিপোর্ট দেখতে অনুগ্রহ করে প্রথমে লগইন করুন।",
            'mr': "तुमचा रिपोर्ट पाहण्यासाठी कृपया प्रथम लॉगिन करा.",
            'ta': "உங்கள் அறிக்கையைப் பார்க்க முதலில் உள்நுழையவும்.",
            'en': "Please log in to view and explain your screening result."
        }
        if not user_id:
            msg = no_login_msgs.get(lang, no_login_msgs['en'])
            return {'reply': msg, 'mode': 'faq', 'is_medical_warning': False}

        screening = get_user_latest_screening(user_id)
        no_record_msgs = {
            'hi': "अभी आपका कोई स्क्रीनिंग रिकॉर्ड उपलब्ध नहीं है। आप 'New Screening' पेज पर जाकर नई जांच शुरू कर सकते हैं।",
            'hinglish': "Abhi aapka koi screening record available nahi hai. Aap 'New Screening' page par jakar nayi screening shuru kar sakte hain.",
            'bn': "এখনো আপনার কোনো স্ক্রিনিং রেকর্ড নেই। 'New Screening' থেকে পরীক্ষা শুরু করুন।",
            'mr': "सध्या तुमचा कोणताही तपासणी रेकॉर्ड उपलब्ध नाही. नवीन तपासणी सुरू करा.",
            'ta': "தங்களுக்கான பரிசோதனைப் பதிவுகள் எதுவும் இல்லை. புதிய பரிசோதனையைத் தொடங்கவும்.",
            'en': "No screening record is available yet for your account. You can start a new screening from the New Screening page."
        }
        if not screening:
            msg = no_record_msgs.get(lang, no_record_msgs['en'])
            return {'reply': msg, 'mode': 'faq', 'is_medical_warning': False}

        patient_id = screening.get('patient_id', 'Unknown')
        pred = screening.get('prediction', 'No DR')
        class_id = screening.get('class_id', 0)
        confidence = screening.get('confidence', 0.0)
        referral = screening.get('referral_required', 0)

        if lang == 'hi':
            summary = (
                f"📋 **नवीनतम स्क्रीनिंग परिणाम ({patient_id})**:\n\n"
                f"• **परिणाम**: {pred} (ग्रेड {class_id} / 4)\n"
                f"• **AI विश्वास स्तर (Confidence)**: {confidence}%\n"
                f"• **रेफरल स्थिति**: {'नेत्र विशेषज्ञ के पास रेफरल की सिफारिश की गई है।' if referral == 1 else 'स्थानीय प्राथमिक केंद्र में नियमित वार्षिक निगरानी।'}\n\n"
                f"💡 **व्याख्या**: यह AI जांच रेटिना के सूक्ष्म घावों का विश्लेषण करके तैयार की गई है। "
                f"कृपया ध्यान दें कि यह अंतिम निदान नहीं है; अंतिम निर्णय हेतु योग्य डॉक्टर से परामर्श अवश्य लें।"
            )
        elif lang == 'hinglish':
            summary = (
                f"📋 **Latest Screening Summary ({patient_id})**:\n\n"
                f"• **Result**: {pred} (Grade {class_id} of 4)\n"
                f"• **AI Confidence**: {confidence}%\n"
                f"• **Triage Recommendation**: {'Specialist ophthalmologist referral recommended.' if referral == 1 else 'Local vision centre me routine annual monitoring.'}\n\n"
                f"💡 **Explanation**: Neural network ne retinal features evaluate kiye hain. "
                f"Please note ki ye ek automated screening output hai, clinical diagnosis nahi. Final confirmation ke liye eye doctor se consult karein."
            )
        elif lang == 'bn':
            summary = (
                f"📋 **সর্বশেষ স্ক্রিনিং ফলাফল ({patient_id})**:\n\n"
                f"• **ফলাফল**: {pred} (গ্রেড {class_id} / 4)\n"
                f"• **AI কনফিডেন্স**: {confidence}%\n"
                f"• **পরামর্শ**: {'চক্ষু বিশেষজ্ঞের রেফারেল প্রয়োজন।' if referral == 1 else 'স্থানীয় কেন্দ্রে বার্ষিক নিয়মিত পর্যবেক্ষণ।'}\n\n"
                f"💡 **ব্যাখ্যা**: এটি একটি প্রাথমিক এআই স্ক্রিনিং রিপোর্ট। চূড়ান্ত রোগনির্ণয়ের জন্য চক্ষু বিশেষজ্ঞের পরামর্শ নিন।"
            )
        elif lang == 'mr':
            summary = (
                f"📋 **नवीनतम तपासणी निकाल ({patient_id})**:\n\n"
                f"• **निकाल**: {pred} (ग्रेड {class_id} / 4)\n"
                f"• **AI अचूकता (Confidence)**: {confidence}%\n"
                f"• **शिफारस**: {'तज्ज्ञ नेत्ररोग डॉक्टरांकडे त्वरित संदर्भ (Referral) आवश्यक.' if referral == 1 else 'नियमित वार्षिक तपासणी.'}\n\n"
                f"💡 **स्पष्टीकरण**: हे एक स्वयंचलित AI स्क्रीनिंग आहे. अंतिम निदानासाठी नेत्ररोग तज्ज्ञांचा सल्ला घ्या."
            )
        elif lang == 'ta':
            summary = (
                f"📋 **சமீபத்திய பரிசோதனை முடிவு ({patient_id})**:\n\n"
                f"• **முடிவு**: {pred} (நிலை {class_id} / 4)\n"
                f"• **AI நம்பிக்கை**: {confidence}%\n"
                f"• **பரிந்துரை**: {'கண் மருத்துவரிடம் ஆலோசனை தேவை.' if referral == 1 else 'ஆண்டுதோறும் வழக்கமான பரிசோதனை போதுமானது.'}\n\n"
                f"💡 **விளக்கம்**: இது ஒரு தானியங்கி AI பரிசோதனை முடிவு மட்டுமே. இறுதி உறுதிப்படுத்தலுக்கு கண் மருத்துவரை அணுகவும்."
            )
        else:
            summary = (
                f"📋 **Latest Screening Summary ({patient_id})**:\n\n"
                f"• **Prediction**: {pred} (Severity Grade {class_id} of 4)\n"
                f"• **AI Confidence Score**: {confidence}%\n"
                f"• **Triage Recommendation**: {'Specialist ophthalmic referral recommended.' if referral == 1 else 'Routine annual primary care monitoring.'}\n\n"
                f"💡 **Explanation**: The deep neural network detected features consistent with Grade {class_id}. "
                f"Please note this is an automated screening triage output, not a certified clinical diagnosis. Always confirm with an ophthalmologist."
            )
        return {'reply': summary, 'mode': 'faq', 'is_medical_warning': False}

    def _call_external_ai(self, prompt: str, lang: str, history: list = None) -> str:
        lang_names = {
            'hi': 'Devanagari Hindi',
            'hinglish': 'Hinglish (Hindi written in Latin script)',
            'bn': 'Bengali',
            'mr': 'Marathi',
            'ta': 'Tamil',
            'en': 'English'
        }
        target_lang = lang_names.get(lang, 'English')
        system_instruction = (
            "You are DrishtiAI Assistant, a friendly, rural-empathetic healthcare AI assistant for RETINA-XAI / DrishtiAI. "
            "You help community health workers and patients understand Diabetic Retinopathy, explain screening results and Grad-CAM, and troubleshoot the DrishtiAI web application.\n\n"
            "BEHAVIORAL GUIDELINES:\n"
            "1. CASUAL CONVERSATION:\n"
            "   - For greetings, friendly check-ins ('Hi', 'How are you?'), harmless jokes, and casual inquiries ('What is your favorite animal?', 'Thank you', 'Bye'), respond warmly, naturally, and briefly with an occasional emoji. Do NOT give long robotic lectures or unnecessary medical disclaimers on casual greetings.\n"
            "2. MEDICAL SAFETY & PROTOCOL:\n"
            "   - You are an educational triage assistant, NOT a doctor.\n"
            "   - Do NOT diagnose diseases or prescribe medications.\n"
            "   - For urgent red-flag symptoms (sudden vision loss, severe eye pain, flashes of light, chemical exposure), urge immediate emergency consultation with an eye hospital.\n"
            "   - Clearly distinguish between AI screening and clinical diagnosis.\n"
            "3. DOMAIN FOCUS & OUT-OF-SCOPE:\n"
            "   - For unrelated questions outside eye care, Diabetic Retinopathy, and the DrishtiAI application (e.g. 'What is Apple?', 'Who won the football match?', 'Capital of Japan'): politely decline and explain that you are designed for Diabetic Retinopathy and DrishtiAI.\n"
            f"4. LANGUAGE MATCHING:\n"
            f"   - Respond naturally in {target_lang}.\n"
            "5. CONCISENESS:\n"
            "   - Keep answers natural, friendly, and concise. Be detailed only when explicitly asked for in-depth clinical explanation."
        )

        if self.ai_provider in ('gemini', 'google'):
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.ai_model}:generateContent?key={self.ai_api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"{system_instruction}\n\nUser Question: {prompt}"}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 300
                }
            }
            req = urllib.request.Request(
                api_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                candidates = res_data.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts:
                        return parts[0].get('text', '').strip()
        return None

chatbot_service = ChatbotService()
