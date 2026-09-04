# RETINA-XAI: Explainable AI for Diabetic Retinopathy Screening in Rural India

**RETINA-XAI** is an AI-assisted healthcare prototype designed for rural and underserved clinical environments. It demonstrates an end-to-end clinical triage workflow:

$$\text{Retinal Fundus Image} \longrightarrow \text{Preprocessing} \longrightarrow \text{AI Screening} \longrightarrow \text{5-Class Prediction} \longrightarrow \text{Grad-CAM Visual Explanation} \longrightarrow \text{Human Review} \longrightarrow \text{Doctor Notes} \longrightarrow \text{Audit History \& Dashboard}$$

The system positions AI as a **screening and triage assistant**, never as a replacement for a certified ophthalmologist.

---

## 1. Key Features

- **5-Class Diabetic Retinopathy Grading**:
  - Class 0: No DR
  - Class 1: Mild DR
  - Class 2: Moderate DR
  - Class 3: Severe DR
  - Class 4: Proliferative DR
- **Grad-CAM Visual Explainability (XAI)**:
  - Interactive visualization revealing which retinal vascular lesions and anatomical regions drove model predictions.
  - Tabbed viewing modes: **Original Retina**, **Attention Heatmap**, and **Blended Overlay**.
  - Intuitive low-to-high attention colormap legend.
- **Preloaded Clinical Sample Cases**:
  - 1-click sample selector with preloaded reference fundus cases across all 5 severity stages for immediate evaluation without needing external images.
- **Human-in-the-Loop Clinical Review**:
  - Healthcare worker notes, observations, and structured specialist referral determination (Yes / No).
- **Audit History & Analytics Dashboard**:
  - Searchable, filterable audit log of past screenings.
  - Interactive Chart.js visualizations: Screening Severity Distribution (Doughnut), Recent Confidence Trend (Line), and Cumulative Class Counts (Bar).
- **Bilingual Interface (English & हिन्दी)**:
  - Instant dual-language toggle designed for frontline community health workers and rural vision technicians.
- **Robust Demo Mode & Model Fallback**:
  - Runs with real TensorFlow/EfficientNetB0 models when available, or activates a high-fidelity OpenCV retinal morphology & attention heatmap engine when running in demonstration environments.

---

## 2. Technology Stack

- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5, Bootstrap Icons, Chart.js.
- **Backend**: Python, Flask web microframework.
- **Image Processing**: OpenCV (`opencv-python`), Pillow, NumPy, Matplotlib.
- **Machine Learning**: TensorFlow / Keras, EfficientNetB0 (`224x224x3`), Grad-CAM.
- **Database**: SQLite3 with auto-initialization and demo records.

---

## 3. Installation

1. Clone or open the repository folder:
   ```bash
   cd retina-xai
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 4. Running the Application Locally

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Open your web browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

3. To experience the workflow in 2 minutes:
   - Navigate to **Screening** (`/screening`).
   - Click one of the preloaded clinical sample cases (e.g., *Moderate DR* or *Mild DR*), or drag-and-drop a custom fundus photograph.
   - Click **Analyze Retina** to observe the multi-stage progress animation.
   - Review the 5-class probability breakdown, circular confidence gauge, and triage recommendation.
   - Click **Overlay**, **Heatmap**, or **Original** tabs under the Grad-CAM explanation.
   - Enter clinical notes, select referral status, and click **Save Screening Report**.
   - Check **History** (`/history`) and **Dashboard** (`/dashboard`) to see updated statistics.
   - Toggle **हिन्दी** in the navbar to test regional language localization.

---

## 5. Model Placement & Production Integration

To connect a custom-trained deep learning model:
1. Save your trained Keras model as `model/dr_model.keras`.
2. Ensure input dimensions match `(224, 224, 3)` with standard RGB normalization.
3. Model output should be a 5-unit Softmax dense layer.
4. Restart `app.py`. The backend will automatically detect the model file and switch from **Demo Mode** to **Live Model Inference**.

---

## 6. Reference Datasets

The architecture and clinical severity categories align with major international retinal datasets:
- **APTOS 2019 Blindness Detection**: Clinical fundus images captured across rural and semi-urban clinics in Tamil Nadu, India (Aravind Eye Hospital).
- **EyePACS**: Large-scale diabetic retinopathy screening dataset with diverse camera hardware.
- **IDRiD**: Indian Diabetic Retinopathy Image Dataset with pixel-level lesion ground truths.
- **Messidor / Messidor-2**: Validated European ophthalmology benchmark.

---

## 7. Explainable AI & Grad-CAM Methodology

Gradient-weighted Class Activation Mapping (Grad-CAM) calculates the gradient of the predicted class score $y^c$ with respect to feature activation maps $A^k$ of the final convolutional layer:

$$\alpha_k^c = \frac{1}{Z} \sum_i \sum_j \frac{\partial y^c}{\partial A_{i,j}^k}$$

$$L_{\text{Grad-CAM}}^c = \text{ReLU}\left(\sum_k \alpha_k^c A^k\right)$$

This highlights specific intraretinal microaneurysms, hemorrhages, and exudates, fostering clinical transparency and assisting non-specialist clinicians in verifying AI predictions.

---

## 8. Limitations & Medical Disclaimer

> **IMPORTANT DISCLAIMER:**
> This software is a research and educational prototype developed for demonstration and hackathon evaluation. It is **NOT a certified medical diagnostic device** and is not intended to provide definitive medical diagnosis. All screening outputs, confidence scores, and Grad-CAM visualizations must be reviewed by a qualified healthcare professional or ophthalmologist.

---

## 9. Future Development Roadmap

- **Phase 1 (Current)**: End-to-end screening MVP, EfficientNetB0 + Grad-CAM, human notes, SQLite audit trail, English/Hindi UI.
- **Phase 2**: Grad-CAM++, Score-CAM, and SHAP kernel explanations for sub-lesion localization.
- **Phase 3**: Regional language expansion: Bengali (বাংলা), Tamil (தமிழ்), Telugu (తెలుగు), Marathi (मराठी).
- **Phase 4**: Quantized ONNX / TFLite edge inference for offline low-cost field devices (e.g. Raspberry Pi 5).
- **Phase 5**: Integration with India's Ayushman Bharat Digital Mission (ABDM) and rural primary health centre workflows.
- **Phase 6**: Tele-ophthalmology referral portal connecting district and tertiary eye hospitals.
