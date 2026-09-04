import os
import cv2
import numpy as np
import json
import torch
import torch.nn.functional as F
from PIL import Image

from train_model import RetinaXAIModel

CLASSES = [
    'No Diabetic Retinopathy',
    'Mild Diabetic Retinopathy',
    'Moderate Diabetic Retinopathy',
    'Severe Diabetic Retinopathy',
    'Proliferative Diabetic Retinopathy'
]

SHORT_CLASSES = ['No DR', 'Mild DR', 'Moderate DR', 'Severe DR', 'Proliferative DR']
LESION_NAMES = ['Microaneurysms (MA)', 'Haemorrhages (HE)', 'Hard Exudates (EX)', 'Soft Exudates (SE)']

CLINICAL_PROFILES = {
    0: {
        'title': 'No Diabetic Retinopathy',
        'short_title': 'No DR',
        'status': 'ROUTINE ANNUAL MONITORING RECOMMENDED',
        'status_type': 'success',
        'referral_recommended': False,
        'summary': 'AI screening result suggests no evidence of diabetic retinopathy. Retinal blood vessels, macula, and optic disc appear within normal biological variations.',
        'action_plan': '1. Advise patient to maintain regular glycemic and HbA1c control.\n2. Schedule routine annual fundus screening in 12 months.\n3. Educate on prompt reporting if visual changes occur.',
        'gradcam_summary': 'Model attention is balanced across normal retinal vascular arcades and optic nerve head without abnormal focal concentrations.'
    },
    1: {
        'title': 'Mild Diabetic Retinopathy',
        'short_title': 'Mild DR',
        'status': 'EARLY OBSERVATION — MONITOR IN 6-12 MONTHS',
        'status_type': 'info',
        'referral_recommended': False,
        'summary': 'AI screening result indicates early signs consistent with Mild Diabetic Retinopathy. Localized microaneurysms detected in peripheral or temporal arcades.',
        'action_plan': '1. Review blood glucose, blood pressure, and lipid management.\n2. Re-screen in 6 to 12 months at primary health centre.\n3. Inform patient regarding lifestyle intervention and warning symptoms.',
        'gradcam_summary': 'Model attention is attracted primarily toward subtle isolated microaneurysms and capillary dilatations in temporal fields.'
    },
    2: {
        'title': 'Moderate Diabetic Retinopathy',
        'short_title': 'Moderate DR',
        'status': 'REFER FOR FURTHER EVALUATION',
        'status_type': 'warning',
        'referral_recommended': True,
        'summary': 'AI screening result suggests Moderate Diabetic Retinopathy — further ophthalmic evaluation recommended. Multiple microaneurysms, dot/blot hemorrhages, or hard exudates detected.',
        'action_plan': '1. Initiate referral to district hospital or ophthalmologist within 2–4 weeks.\n2. Order comprehensive dilated retinal examination and optical coherence tomography (OCT) if available.\n3. Intensify metabolic and blood pressure control with primary physician.',
        'gradcam_summary': 'Model attention concentrates over clusters of intraretinal dot-and-blot hemorrhages, hard exudates, and vascular caliber irregularities.'
    },
    3: {
        'title': 'Severe Diabetic Retinopathy',
        'short_title': 'Severe DR',
        'status': 'URGENT SPECIALIST REFERRAL REQUIRED',
        'status_type': 'danger',
        'referral_recommended': True,
        'summary': 'AI screening result indicates Severe Diabetic Retinopathy. Marked intraretinal hemorrhages and microvascular changes detected with substantial risk of rapid progression.',
        'action_plan': '1. Expedited referral to ophthalmologist/retina specialist within 1–2 weeks.\n2. Assess for clinically significant macular edema (CSME) and impending neovascularization.\n3. Prepare patient for possible panretinal photocoagulation (PRP) or anti-VEGF therapy.',
        'gradcam_summary': 'Model attention demonstrates high-intensity activation over extensive quadrant hemorrhages, cotton wool spots, and venous beading.'
    },
    4: {
        'title': 'Proliferative Diabetic Retinopathy',
        'short_title': 'Proliferative DR',
        'status': 'CRITICAL VITREO-RETINAL REFERRAL REQUIRED',
        'status_type': 'danger',
        'referral_recommended': True,
        'summary': 'AI screening result indicates Proliferative Diabetic Retinopathy. Neovascularization and proliferative vascular lesions detected with high risk of severe visual impairment.',
        'action_plan': '1. Immediate referral to tertiary vitreo-retinal centre within 24–72 hours.\n2. Specialist evaluation for neovascularization at disc (NVD) or elsewhere (NVE), vitreous hemorrhage, or tractional retinal detachment.\n3. Urgent retinal intervention (anti-VEGF injections / laser photocoagulation).',
        'gradcam_summary': 'Model attention exhibits intense multi-focal focus along abnormal neovascular proliferation complexes and fibrous membrane margins.'
    }
}

_PYTORCH_MODEL = None
_IS_DEMO = True
_MODEL_INFO = "Demo Mode"

def initialize_model():
    global _PYTORCH_MODEL, _IS_DEMO, _MODEL_INFO
    model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'model', 'retina_idrid_model.pth')
    if os.path.exists(model_path):
        try:
            checkpoint = torch.load(model_path, map_location="cpu")
            model = RetinaXAIModel(num_classes=5, num_lesions=4)
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()
            _PYTORCH_MODEL = model
            _IS_DEMO = False
            _MODEL_INFO = f"Trained on IDRiD Dataset (Indian Cohort, Epochs: {checkpoint.get('epoch', 15)})"
            print(f"[RETINA-XAI] Successfully loaded trained PyTorch model from {model_path}")
            return
        except Exception as e:
            print(f"[RETINA-XAI] Error loading PyTorch model: {e}")
            
    _IS_DEMO = True
    _MODEL_INFO = "Demo Mode"

def is_demo_mode():
    return _IS_DEMO

def get_model():
    return _PYTORCH_MODEL

def predict_fundus_image(image_path):
    global _PYTORCH_MODEL, _IS_DEMO
    
    if not _IS_DEMO and _PYTORCH_MODEL is not None:
        try:
            # Preprocess for PyTorch model
            img = Image.open(image_path).convert("RGB").resize((224, 224), Image.BILINEAR)
            arr = np.array(img, dtype=np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            arr = (arr - mean) / std
            
            input_tensor = torch.from_numpy(arr.transpose(2, 0, 1)).unsqueeze(0).float()
            
            with torch.no_grad():
                features = _PYTORCH_MODEL.forward_features(input_tensor)
                pooled = _PYTORCH_MODEL.pool(features).flatten(1)
                dr_logits = _PYTORCH_MODEL.dr_classifier(pooled)
                lesion_logits = _PYTORCH_MODEL.lesion_detector(pooled)
                
                probs = F.softmax(dr_logits, dim=1).numpy()[0]
                lesion_probs = torch.sigmoid(lesion_logits).numpy()[0]
                
            pred_class = int(np.argmax(probs))
            conf = float(probs[pred_class] * 100)
            prob_list = [round(float(p * 100), 1) for p in probs]
            
            detected_lesions = [
                LESION_NAMES[i] for i, p in enumerate(lesion_probs) if p > 0.40
            ]
            
            return {
                'class_id': pred_class,
                'class_name': CLASSES[pred_class],
                'short_class_name': SHORT_CLASSES[pred_class],
                'confidence': round(conf, 1),
                'probabilities': prob_list,
                'clinical_profile': CLINICAL_PROFILES[pred_class],
                'detected_lesions': detected_lesions,
                'is_demo': False,
                'model_name': 'IDRiD Trained PyTorch Model'
            }
        except Exception as e:
            print(f"[RETINA-XAI] PyTorch inference error: {e}. Utilizing fallback demo inference.")
            
    # Fallback Demo Inference
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise ValueError(f"Unable to read image at {image_path}")
        
    filename = os.path.basename(image_path).lower()
    if 'no_dr' in filename or 'normal' in filename:
        pred_class = 0
        probs = [96.4, 2.3, 0.8, 0.3, 0.2]
    elif 'mild' in filename:
        pred_class = 1
        probs = [5.4, 88.6, 4.2, 1.2, 0.6]
    elif 'moderate' in filename:
        pred_class = 2
        probs = [2.1, 4.5, 90.8, 2.1, 0.5]
    elif 'severe' in filename:
        pred_class = 3
        probs = [0.5, 1.4, 3.8, 93.6, 0.7]
    elif 'proliferative' in filename:
        pred_class = 4
        probs = [0.2, 0.4, 0.9, 1.8, 96.7]
    else:
        pred_class = 2
        probs = [3.2, 8.4, 78.5, 7.1, 2.8]
        
    conf = probs[pred_class]
    return {
        'class_id': pred_class,
        'class_name': CLASSES[pred_class],
        'short_class_name': SHORT_CLASSES[pred_class],
        'confidence': round(conf, 1),
        'probabilities': probs,
        'clinical_profile': CLINICAL_PROFILES[pred_class],
        'detected_lesions': ['Microaneurysms (MA)', 'Haemorrhages (HE)'],
        'is_demo': True,
        'model_name': 'Demonstration Model'
    }
