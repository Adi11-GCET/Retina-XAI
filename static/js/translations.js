const translations = {
  en: {
    // Nav
    "nav.home": "Home",
    "nav.screening": "Screening",
    "nav.dashboard": "Dashboard",
    "nav.history": "History",
    "nav.about": "About",
    "nav.new_screening": "New Screening",
    
    // Global & Badges
    "badge.ai_assist": "AI-ASSISTED RETINAL SCREENING",
    "badge.demo_mode": "Demo Mode: Demonstration AI Model",
    "badge.explainable": "Explainable Grad-CAM",
    "badge.human_loop": "Human-in-the-Loop",
    "badge.rural": "Rural Health Ready",
    
    // Home Hero
    "hero.title": "Making Retinal Screening More Explainable and Accessible",
    "hero.subtitle": "RETINA-XAI assists frontline healthcare workers in rural and underserved clinics to screen diabetic retinopathy fundus images with visual Grad-CAM explanations and referral triage.",
    "hero.btn_start": "Start Screening",
    "hero.btn_how": "Explore How It Works",
    
    // Home Problem
    "problem.heading": "Why RETINA-XAI?",
    "problem.subheading": "Addressing the critical gap in rural eye-care accessibility across India",
    "problem.card1_title": "Limited Specialist Access",
    "problem.card1_desc": "Over 70% of India's diabetic population resides in rural areas with severe shortages of trained ophthalmologists.",
    "problem.card2_title": "AI-Assisted Triage",
    "problem.card2_desc": "Rapid automated risk classification enables community health workers to prioritize high-risk patients for referral.",
    "problem.card3_title": "Explainable Decisions",
    "problem.card3_desc": "Grad-CAM visual heatmaps highlight the specific retinal vascular lesions that influenced the AI prediction.",
    
    // Home Workflow
    "workflow.heading": "How It Works",
    "workflow.subheading": "A 5-step clinical screening and explainability pipeline",
    "step1.title": "Upload",
    "step1.desc": "Fundus image capture at local clinic",
    "step2.title": "Analyze",
    "step2.desc": "Preprocessing & EfficientNet screening",
    "step3.title": "Predict",
    "step3.desc": "5-class severity & confidence score",
    "step4.title": "Explain",
    "step4.desc": "Grad-CAM visual attention heatmap",
    "step5.title": "Review",
    "step5.desc": "Healthcare worker notes & referral triage",
    
    // Rural Section
    "rural.heading": "Designed with Rural Healthcare in Mind",
    "rural.subheading": "Empowering primary health centres (PHCs) and vision centres without requiring on-site retina specialists",
    "rural.flow1": "Rural Health Centre",
    "rural.flow2": "Non-Mydriatic Camera",
    "rural.flow3": "RETINA-XAI Triage",
    "rural.flow4": "Explainable Risk",
    "rural.flow5": "Tele-Ophthalmologist",
    "rural.flow6": "Tertiary Referral",
    
    // Screening Page
    "screening.title": "New Retinal Screening",
    "screening.subtitle": "Upload a digital retinal fundus photograph or select a clinical sample case to begin AI-assisted evaluation.",
    "screening.drag_drop": "Drag & drop your fundus image here",
    "screening.or": "or",
    "screening.browse": "Browse Files",
    "screening.supported": "Supported: JPG, JPEG, PNG (Max file size: 10 MB)",
    "screening.sample_prompt": "Or select a preloaded clinical sample case:",
    "screening.sample_0": "No DR (Normal)",
    "screening.sample_1": "Mild DR",
    "screening.sample_2": "Moderate DR",
    "screening.sample_3": "Severe DR",
    "screening.sample_4": "Proliferative DR",
    "screening.btn_analyze": "Analyze Retina",
    
    // Processing Overlay
    "processing.heading": "Analyzing retinal image...",
    "stage.1": "Image uploaded and validated",
    "stage.2": "Preprocessing fundus & CLAHE enhancement",
    "stage.3": "Running EfficientNetB0 screening model",
    "stage.4": "Generating Grad-CAM visual explanation",
    "stage.5": "Preparing clinical screening report",
    
    // Result Page
    "result.title": "AI Screening Result",
    "result.patient_id": "Patient ID",
    "result.date": "Screening Date",
    "result.confidence": "Confidence",
    "result.probabilities": "Five-Class Probability Distribution",
    "result.status_title": "Screening Triage Recommendation",
    "result.explain_heading": "Why did the AI make this prediction?",
    "result.btn_reveal": "Explain Prediction (Grad-CAM)",
    "result.tab_original": "Original Retina",
    "result.tab_heatmap": "Attention Heatmap",
    "result.tab_overlay": "Blended Overlay",
    "result.legend_low": "Low Attention",
    "result.legend_med": "Medium Attention",
    "result.legend_high": "High Attention",
    "result.explanation_title": "AI Visual Explanation",
    "result.disclaimer_box": "Important: The heatmap represents model attention and is not proof that a specific lesion is present. It serves as visual decision support for qualified healthcare review.",
    
    // Human Review
    "review.title": "Human Review & Clinical Documentation",
    "review.notes_label": "Observations & Clinical Notes",
    "review.notes_placeholder": "Enter clinical observations, retinal examination notes, or patient history...",
    "review.referral_label": "Referral Required to Specialist / District Hospital?",
    "review.ref_yes": "Yes — Refer for specialist ophthalmic evaluation",
    "review.ref_no": "No — Routine follow-up at primary vision centre",
    "review.btn_save": "Save Screening Report",
    "review.btn_clear": "Clear Notes",
    "review.btn_print": "Print / Export Report",
    
    // Dashboard & History
    "dash.title": "Screening Dashboard",
    "dash.total": "Total Screenings",
    "dash.no_dr": "No DR",
    "dash.mild": "Mild DR",
    "dash.moderate": "Moderate DR",
    "dash.severe": "Severe DR",
    "dash.pdr": "Proliferative DR",
    "dash.referral_rate": "Referral Rate",
    "dash.chart_dist": "Screening Severity Distribution",
    "dash.chart_trends": "Recent Screening Trend",
    "dash.chart_classes": "Cumulative Class Counts",
    
    "hist.title": "Screening History",
    "hist.subtitle": "Audit log of all AI-assisted diabetic retinopathy screenings",
    "hist.search_ph": "Search by Patient ID or notes...",
    "hist.filter_all": "All Classes",
    "hist.th_id": "Patient ID",
    "hist.th_date": "Date & Time",
    "hist.th_result": "AI Result",
    "hist.th_conf": "Confidence",
    "hist.th_ref": "Referral",
    "hist.th_status": "Type",
    "hist.th_action": "Action",
    "hist.empty_title": "No screenings found",
    "hist.empty_desc": "No clinical screenings recorded matching your filter criteria.",
    
    // Disclaimer
    "footer.disclaimer": "This system is a research/educational prototype and is not intended to provide a medical diagnosis. Results should be reviewed by a qualified healthcare professional."
  },
  
  hi: {
    // Nav
    "nav.home": "मुख्य पृष्ठ",
    "nav.screening": "रेटिना जांच",
    "nav.dashboard": "डैशबोर्ड",
    "nav.history": "इतिहास",
    "nav.about": "परिचय",
    "nav.new_screening": "नई जांच",
    
    // Global & Badges
    "badge.ai_assist": "एआई-सहायक रेटिना जांच",
    "badge.demo_mode": "डेमो मोड: प्रदर्शन मॉडल",
    "badge.explainable": "पारदर्शी ग्रैड-कैम",
    "badge.human_loop": "चिकित्सक समीक्षा सहित",
    "badge.rural": "ग्रामीण स्वास्थ्य हेतु तैयार",
    
    // Home Hero
    "hero.title": "रेटिनल स्क्रीनिंग को अधिक सुलभ और पारदर्शी बनाना",
    "hero.subtitle": "रेटिना-एक्सएआई ग्रामीण व प्राथमिक स्वास्थ्य केंद्रों में स्वास्थ्य कार्यकर्ताओं को डायबिटिक रेटिनोपैथी की जांच, ग्रैड-कैम व्याख्या और त्वरित रेफरल में सहायता करता है।",
    "hero.btn_start": "जांच शुरू करें",
    "hero.btn_how": "कार्यप्रणाली देखें",
    
    // Home Problem
    "problem.heading": "रेटिना-एक्सएआई क्यों?",
    "problem.subheading": "भारत के ग्रामीण क्षेत्रों में नेत्र देखभाल की पहुंच में सुधार",
    "problem.card1_title": "विशेषज्ञों की सीमित पहुंच",
    "problem.card1_desc": "भारत के 70% से अधिक मधुमेह रोगी ग्रामीण क्षेत्रों में रहते हैं, जहाँ नेत्र रोग विशेषज्ञों की भारी कमी है।",
    "problem.card2_title": "एआई-सहायक स्क्रीनिंग",
    "problem.card2_desc": "स्वचालित जोखिम वर्गीकरण से सामुदायिक कार्यकर्ता उच्च जोखिम वाले रोगियों को तुरंत रेफरल हेतु प्राथमिकता दे सकते हैं।",
    "problem.card3_title": "पारदर्शी निर्णय",
    "problem.card3_desc": "ग्रैड-कैम विज़ुअल हीटमैप उन रेटिना रक्त वाहिकाओं और घावों को स्पष्ट रूप से उजागर करते हैं जिन्होंने भविष्यवाणी को प्रभावित किया।",
    
    // Home Workflow
    "workflow.heading": "यह कैसे काम करता है",
    "workflow.subheading": "5-चरणीय नैदानिक स्क्रीनिंग और दृश्य व्याख्या प्रक्रिया",
    "step1.title": "अपलोड",
    "step1.desc": "स्थानीय केंद्र पर फंडस छवि कैप्चर",
    "step2.title": "विश्लेषण",
    "step2.desc": "प्री-प्रोसेसिंग और एआई विश्लेषण",
    "step3.title": "भविष्यवाणी",
    "step3.desc": "5-श्रेणी गंभीरता और विश्वास स्कोर",
    "step4.title": "व्याख्या",
    "step4.desc": "ग्रैड-कैम दृश्य ध्यान हीटमैप",
    "step5.title": "समीक्षा",
    "step5.desc": "स्वास्थ्य कार्यकर्ता नोट्स और रेफरल",
    
    // Rural Section
    "rural.heading": "ग्रामीण स्वास्थ्य सेवाओं को ध्यान में रखकर निर्मित",
    "rural.subheading": "नेत्र विशेषज्ञों की अनुपस्थिति में भी प्राथमिक स्वास्थ्य केंद्रों (PHC) को सशक्त बनाना",
    "rural.flow1": "ग्रामीण स्वास्थ्य केंद्र",
    "rural.flow2": "फंडस कैमरा",
    "rural.flow3": "रेटिना-एक्सएआई",
    "rural.flow4": "जोखिम वर्गीकरण",
    "rural.flow5": "टेली-नेत्र विशेषज्ञ",
    "rural.flow6": "विशेषज्ञ रेफरल",
    
    // Screening Page
    "screening.title": "नई रेटिनल स्क्रीनिंग",
    "screening.subtitle": "एआई-सहायक मूल्यांकन शुरू करने के लिए डिजिटल रेटिनल फंडस छवि अपलोड करें या नैदानिक नमूना चुनें।",
    "screening.drag_drop": "अपनी फंडस छवि यहां खींचें और छोड़ें",
    "screening.or": "अथवा",
    "screening.browse": "फाइलें चुनें",
    "screening.supported": "समर्थित: जेपीजी, जेपीईजी, पीएनजी (अधिकतम फ़ाइल आकार: 10 एमबी)",
    "screening.sample_prompt": "या पहले से लोड किया गया नैदानिक नमूना चुनें:",
    "screening.sample_0": "कोई डीआर नहीं (सामान्य)",
    "screening.sample_1": "माइल्ड डीआर (हल्का)",
    "screening.sample_2": "मॉडरेट डीआर (मध्यम)",
    "screening.sample_3": "गंभीर डीआर (सिवियर)",
    "screening.sample_4": "प्रोलिफेरेटिव डीआर",
    "screening.btn_analyze": "रेटिना का विश्लेषण करें",
    
    // Processing Overlay
    "processing.heading": "रेटिना छवि का विश्लेषण जारी है...",
    "stage.1": "छवि अपलोड और सत्यापित",
    "stage.2": "फंडस प्री-प्रोसेसिंग और ग्रीन कंट्रास्ट संवर्धन",
    "stage.3": "एफिशिएंटनेट-बी0 स्क्रीनिंग मॉडल निष्पादन",
    "stage.4": "ग्रैड-कैम दृश्य व्याख्या तैयार हो रही है",
    "stage.5": "स्क्रीनिंग रिपोर्ट अंतिम रूप में तैयार",
    
    // Result Page
    "result.title": "एआई स्क्रीनिंग परिणाम",
    "result.patient_id": "रोगी आईडी",
    "result.date": "स्क्रीनिंग तिथि",
    "result.confidence": "विश्वास स्तर",
    "result.probabilities": "पांच-श्रेणी संभावना वितरण",
    "result.status_title": "स्क्रीनिंग रेफरल अनुशंसा",
    "result.explain_heading": "एआई ने यह भविष्यवाणी क्यों की?",
    "result.btn_reveal": "भविष्यवाणी की व्याख्या देखें (Grad-CAM)",
    "result.tab_original": "मूल रेटिना",
    "result.tab_heatmap": "ध्यान हीटमैप",
    "result.tab_overlay": "मिश्रित ओवरले",
    "result.legend_low": "कम ध्यान",
    "result.legend_med": "मध्यम ध्यान",
    "result.legend_high": "अधिक ध्यान",
    "result.explanation_title": "एआई दृश्य व्याख्या",
    "result.disclaimer_box": "महत्वपूर्ण: हीटमैप मॉडल का ध्यान दर्शाता है और यह प्रमाण नहीं है कि कोई विशिष्ट घाव मौजूद है। यह योग्य स्वास्थ्य पेशेवर की समीक्षा हेतु निर्णय समर्थन है।",
    
    // Human Review
    "review.title": "चिकित्सक समीक्षा एवं नैदानिक नोट्स",
    "review.notes_label": "निरीक्षण एवं नैदानिक नोट्स",
    "review.notes_placeholder": "रेटिना परीक्षण संबंधी नोट्स, टिप्पणियां अथवा इतिहास दर्ज करें...",
    "review.referral_label": "क्या विशेषज्ञ अथवा जिला अस्पताल रेफरल आवश्यक है?",
    "review.ref_yes": "हाँ — विशेषज्ञ नेत्र रोग मूल्यांकन हेतु रेफर करें",
    "review.ref_no": "नहीं — प्राथमिक दृष्टि केंद्र पर नियमित अनुवर्ती जांच",
    "review.btn_save": "स्क्रीनिंग रिपोर्ट सहेजें",
    "review.btn_clear": "नोट्स साफ़ करें",
    "review.btn_print": "रिपोर्ट प्रिंट / निर्यात करें",
    
    // Dashboard & History
    "dash.title": "स्क्रीनिंग डैशबोर्ड",
    "dash.total": "कुल स्क्रीनिंग",
    "dash.no_dr": "डीआर नहीं",
    "dash.mild": "माइल्ड डीआर",
    "dash.moderate": "मॉडरेट डीआर",
    "dash.severe": "सिवियर डीआर",
    "dash.pdr": "प्रोलिफेरेटिव डीआर",
    "dash.referral_rate": "रेफरल दर",
    "dash.chart_dist": "स्क्रीनिंग गंभीरता वितरण",
    "dash.chart_trends": "हालिया स्क्रीनिंग रुझान",
    "dash.chart_classes": "संचयी श्रेणी गणना",
    
    "hist.title": "स्क्रीनिंग इतिहास",
    "hist.subtitle": "सभी एआई-सहायक डायबिटिक रेटिनोपैथी स्क्रीनिंग का ऑडिट लॉग",
    "hist.search_ph": "रोगी आईडी अथवा नोट्स द्वारा खोजें...",
    "hist.filter_all": "सभी श्रेणियां",
    "hist.th_id": "रोगी आईडी",
    "hist.th_date": "दिनांक एवं समय",
    "hist.th_result": "एआई परिणाम",
    "hist.th_conf": "विश्वास",
    "hist.th_ref": "रेफरल",
    "hist.th_status": "प्रकार",
    "hist.th_action": "कार्रवाई",
    "hist.empty_title": "कोई रिकॉर्ड नहीं मिला",
    "hist.empty_desc": "आपके फ़िल्टर से मेल खाती कोई स्क्रीनिंग नहीं मिली।",
    
    // Disclaimer
    "footer.disclaimer": "यह प्रणाली एक शोध/शैक्षणिक प्रोटोटाइप है और चिकित्सीय निदान प्रदान करने के लिए नहीं है। परिणामों की समीक्षा योग्य नेत्र रोग विशेषज्ञ द्वारा की जानी चाहिए।"
  }
};

let currentLang = localStorage.getItem('retina_lang') || 'en';

function setLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('retina_lang', lang);
  
  // Update toggle buttons
  document.querySelectorAll('.lang-btn').forEach(btn => {
    if (btn.dataset.lang === lang) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  // Translate text elements with data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (translations[lang] && translations[lang][key]) {
      el.textContent = translations[lang][key];
    }
  });
  
  // Translate placeholders with data-i18n-ph
  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    const key = el.getAttribute('data-i18n-ph');
    if (translations[lang] && translations[lang][key]) {
      el.setAttribute('placeholder', translations[lang][key]);
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setLanguage(currentLang);
  
  document.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const selected = e.currentTarget.dataset.lang;
      setLanguage(selected);
    });
  });
});
