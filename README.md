# RETINA-XAI – Explainable AI for Diabetic Retinopathy Screening

RETINA-XAI is a prototype web application that explores how AI can assist in the early screening of diabetic retinopathy, especially in rural and underserved areas.

The project allows a user to upload a retinal fundus image, analyze it, view the predicted severity level, and see a visual explanation using Grad-CAM. It also includes a simple review system where healthcare workers can add notes and record whether a specialist referral is required.

> **Note:** This is an educational and demonstration project, not a medical diagnostic system.

---

## Features

### 🩺 5-Level Diabetic Retinopathy Classification

The application uses five severity levels:

* **0 – No Diabetic Retinopathy**
* **1 – Mild**
* **2 – Moderate**
* **3 – Severe**
* **4 – Proliferative**

The prediction is displayed along with the probability of each class.

### 🔍 Explainable AI with Grad-CAM

The project uses Grad-CAM to create a heatmap showing the areas of the retinal image that received more attention from the model.

Users can switch between:

* Original Image
* Heatmap
* Grad-CAM Overlay

This makes the prediction easier to understand instead of showing only a final class label.

### 📷 Sample Retina Images

Some sample cases are included in the application so that the complete workflow can be tested without uploading an image every time.

### 👨‍⚕️ Human Review

After analysis, the user can:

* Add observations or notes
* Select whether referral is required
* Save the screening report

This keeps a human reviewer involved instead of treating the AI prediction as a final diagnosis.

### 📊 History & Dashboard

The application stores previous screening reports in a SQLite database.

The dashboard provides simple visualizations such as:

* Distribution of screening results
* Confidence trends
* Number of cases in each severity class

### 🌐 English & Hindi

The interface supports both English and Hindi to make the prototype more suitable for users in different regions of India.

---

## Technology Used

### Frontend

* HTML
* CSS
* JavaScript
* Bootstrap 5
* Chart.js

### Backend

* Python
* Flask

### AI & Image Processing

* TensorFlow / Keras
* EfficientNetB0
* Grad-CAM
* OpenCV
* Pillow
* NumPy
* Matplotlib

### Database

* SQLite

---

## Project Workflow

The basic workflow of the application is:

**Upload Retina Image → Preprocess Image → AI Prediction → Show Severity → Generate Grad-CAM → Human Review → Save Report**

The application is designed so that AI assists the screening process while the final medical decision remains with a qualified healthcare professional.

---

## Running the Project

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd retina-xai
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Flask application

```bash
python app.py
```

### 4. Open in browser

```text
http://127.0.0.1:5000
```

---

## Using the Application

1. Open the **Screening** page.
2. Select one of the available sample cases or upload a retinal fundus image.
3. Click **Analyze Retina**.
4. View the predicted diabetic retinopathy severity.
5. Check the class probabilities and confidence score.
6. Open the **Original**, **Heatmap**, and **Overlay** views.
7. Add notes and select the referral status.
8. Save the screening report.
9. Visit **History** or **Dashboard** to view previous results.

---

## AI Model

The application is designed to work with an EfficientNetB0-based TensorFlow/Keras model.

The expected input size is:

```text
224 × 224 × 3
```

The model is expected to produce five output classes corresponding to the five diabetic retinopathy severity levels.

If a trained model is available, it can be placed at:

```text
model/dr_model.keras
```

The application can then use the model for inference.

### Demo Mode

For demonstration purposes, the project can also run without the trained model. In this case, the application uses its demo image-processing logic so that the complete website workflow can still be tested.

---

## Dataset References

The project is based on commonly used diabetic retinopathy image datasets, including:

* APTOS 2019 Blindness Detection
* EyePACS
* IDRiD
* Messidor / Messidor-2

These datasets are useful references for developing and evaluating diabetic retinopathy detection systems.

---

## Why Explainability?

A normal AI model may provide a prediction without clearly showing why it made that prediction.

Grad-CAM provides a visual indication of the image regions that contributed more to the model's prediction. This can make the system easier to inspect and can help a healthcare professional understand the model's output.

However, the heatmap should **not** be treated as proof that a specific retinal lesion is present.

---

## Limitations

This project is currently a prototype and has several limitations:

* It is not a certified medical device.
* AI predictions should not be used as a final diagnosis.
* Model performance depends on the quality and diversity of the training data.
* Grad-CAM is an explanation of model attention, not a medical diagnosis.
* A properly trained and validated model is required for real-world clinical use.
* Further testing with clinical datasets and medical professionals would be required before practical deployment.

---

## Future Improvements

Some possible future improvements are:

* Train and evaluate the model on a larger dataset
* Improve Grad-CAM explanations
* Add more Indian regional languages
* Add offline support for low-resource areas
* Improve image quality checks
* Add doctor/ophthalmologist review features
* Explore deployment on low-cost devices
* Perform proper clinical validation

---

## Disclaimer

**RETINA-XAI is an educational and research prototype created for demonstration purposes. It is not intended to diagnose, treat, or replace a qualified medical professional. Any real medical decision should be made by an appropriately qualified healthcare professional.**

---

## Author

**ADITIYA GUPTA**

B.Tech CSE (Data Science) Student

Interested in AI, Data Science and Web Development.
