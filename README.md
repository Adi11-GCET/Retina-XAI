# RETINA-XAI: Explainable AI for Diabetic Retinopathy Screening in Rural India

**RETINA-XAI** (Clinical Interface: **DrishtiAI**) is a robust, bilingual AI-assisted healthcare platform developed for diabetic retinopathy screening and triage in rural and semi-urban vision centers.

$$\text{Retinal Image} \longrightarrow \text{Domain Validation} \longrightarrow \text{DR Severity Classification} \longrightarrow \text{Grad-CAM XAI} \longrightarrow \text{IDRiD Lesion Segmentation} \longrightarrow \text{Bilingual Voice Triage} \longrightarrow \text{Audit Log}$$

The platform adheres to strict clinical governance: AI acts as an **assistive screening and triage tool**, providing explainable attention heatmaps and anatomical lesion segmentations to empower frontline health workers, without ever replacing a qualified ophthalmologist.

---

## 1. Key System Capabilities

- **Diabetic Retinopathy Classification (5 Severity Grades)**:
  - Grade 0: No DR (Routine annual check-up)
  - Grade 1: Mild DR (Non-proliferative, microaneurysms only)
  - Grade 2: Moderate DR (Hemorrhages, hard exudates)
  - Grade 3: Severe DR (4-2-1 international clinical rule)
  - Grade 4: Proliferative DR (Neovascularization, high retinal detachment risk)
- **Multi-Feature Retinal Validation Guardrail**:
  - Automatically rejects non-retinal uploads (human faces, landscapes, pets, documents, blurry screenshots) with HTTP 400 and bilingual voice alerts.
  - Non-retinal photos **never** receive a false "No DR" diagnosis.
- **Explainable AI (Grad-CAM)**:
  - Backpropagation gradient heatmaps revealing convolutional focus areas.
  - Interactive tabs: **Overlay**, **Heatmap**, and **Original Retina**.
- **Pixel-Level Lesion & Optic Disc Segmentation (IDRiD PyTorch U-Net)**:
  - Trained directly on the Indian Diabetic Retinopathy Image Dataset (IDRiD).
  - Segments 5 anatomical and pathological targets:
    - **Optic Disc (OD)** — Cyan
    - **Haemorrhages (HE)** — Crimson
    - **Microaneurysms (MA)** — Magenta
    - **Hard Exudates (EX)** — Gold
    - **Soft Exudates (SE)** — Mint Green
  - Interactive tabs: **Overlay**, **Binary Mask**, and **Original Fundus**.
- **Bilingual English + हिन्दी Voice Assistant**:
  - Text-to-speech audio reading of screening verdicts and triage advice.
  - Voice-to-text dictation for doctor clinical notes.
  - Voice-driven patient history search.
- **Clinical Accessibility**:
  - Dark / Light mode toggle.
  - High-contrast font zoom controls (A- / A / A+).
  - Preloaded clinical reference cases across all 5 DR grades.

---

## 2. IDRiD Dataset & Segmentation Model

### Dataset Specifications & Strict Evaluation Split
The model was trained and evaluated on the Indian Diabetic Retinopathy Image Dataset (**IDRiD** - Part A: Segmentation):
- **Total Images**: Exactly 81 fundus photographs (`4288 × 2848` RGB JPEGs).
- **Split Protocol**:
  - **Training Subset**: 44 images (`IDRiD_01` to `IDRiD_54` subset) used for model gradient updates.
  - **Validation Subset**: 10 images (`IDRiD_04`, `06`, `13`, `18`, `20`, `33`, `45`, `49`, `50`, `53`) used **solely** for model selection and checkpoint saving.
  - **Held-Out Test Set**: 27 images (`IDRiD_55` to `IDRiD_81`) **completely untouched** during training and model selection.
- **Ground-Truth Masks**: Binary TIFF masks (`{0, 1}`) across 5 folders:
  1. `1. Microaneurysms/`
  2. `2. Haemorrhages/`
  3. `3. Hard Exudates/`
  4. `4. Soft Exudates/`
  5. `5. Optic Disc/`
- **Clinical Honesty Note**: The IDRiD segmentation dataset contains **NO diabetic retinopathy severity labels**. It provides ground-truth pixel masks for anatomical structures and lesions, not disease grades. The DR classification model (`model/retina_idrid_model.pth`) and the segmentation model (`model/retinal_segmentation_model.pth`) operate as complementary, specialized components.

### Model Architecture: RetinalUNet
- **Framework**: PyTorch (`torch 2.14.0+cpu`).
- **Structure**: 4-level encoder-decoder with skip connections and double convolutions (64 $\to$ 128 $\to$ 256 $\to$ 512 $\to$ 256 $\to$ 128 $\to$ 64 $\to$ 32 channels).
- **Input Resolution**: $256 \times 256 \times 3$.
- **Output Channels**: 5 sigmoid activation channels (multi-label segmentation).
- **Loss Function**: Combined BCE with Soft Dice Loss ($\mathcal{L} = 0.4 \cdot \text{BCE} + 0.6 \cdot \text{Dice}$).
- **Optimization**: AdamW ($\text{lr} = 10^{-3}$, weight decay $= 10^{-4}$) with Cosine Annealing scheduler over 15 epochs.
- **Checkpoint Selection**: Selected at **Epoch 13** based strictly on the lowest validation loss ($0.6817$) on the 10-image validation subset.

### Empirical Held-Out Test Metrics (Evaluated ONCE on Unseen IDRiD_55 to IDRiD_81)
Evaluated strictly once on the 27 held-out test images after training was complete (recorded in `model/segmentation_metadata.json`):

| Structure / Lesion | Test Dice Score | Test IoU (Jaccard) | Precision | Recall | Clinical Performance Summary |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Optic Disc (OD)** | **0.7820** | **0.6421** | 0.6682 | **0.9425** | Strong anatomical boundary delineation and localization |
| **Hard Exudates (EX)** | **0.1461** | **0.0788** | 0.1125 | 0.2082 | Coarse detection of lipid deposits |
| **Soft Exudates (SE)** | **0.1236** | **0.0659** | 0.1203 | 0.1270 | Sparse detection (cotton-wool spots) |
| **Haemorrhages (HE)** | **0.0016** | **0.0008** | 0.0025 | 0.0012 | Very weak recall on fine vascular flame lesions |
| **Microaneurysms (MA)** | **0.0000** | **0.0000** | 0.0000 | 0.0000 | Sub-pixel bottleneck: downsampling loss at $256 \times 256$ |
| **Overall Test Mean** | **0.2107** | **0.1575** | — | — | Solid on optic disc; weak on micro-lesions |

> **IMPORTANT CLINICAL NOTICE ON SEGMENTATION PERFORMANCE:**
> Segmentation performance is **weak** for Microaneurysms (Dice 0.0000), Haemorrhages (Dice 0.0016), and Soft Exudates (Dice 0.1236). This model **does NOT provide clinical-grade segmentation** and must not be used for diagnostic lesion quantification. It serves solely as an exploratory decision-support demonstration for optic disc orientation and general exudate clustering.

---

## 3. Heuristic Retinal-Image Validation Guardrail

To filter out obviously non-retinal uploads (e.g., human portraits, animals, outdoor landscapes, documents, screenshots, and blank files) before they enter the deep learning pipeline, `utils/validation.py` enforces a heuristic pre-screening guardrail:

1. **Active Circular Field of View (FOV)**: Checks whether an illuminated fundus aperture occupies $\ge 15\%$ of the frame.
2. **Hemoglobin Chromatic Profile**: Retinal tissue strongly reflects red and absorbs blue. Evaluates $\frac{\text{Mean}(B)}{\text{Mean}(R)} < 0.70$ and $\text{Mean}(R) \ge 35$.
3. **Warm Retinal Hue Dominance**: In OpenCV HSV space, retinal hues cluster in $[0, 28] \cup [155, 180]$. Checks for $\ge 60\%$ warm pixel concentration.
4. **Microvascular Green-Channel Contrast**: Computes standard deviation in the green channel ($\text{std}(G) \ge 6.0$) to reject solid blocks, flat graphics, and overexposed scans.

When an upload fails this heuristic guardrail, the server returns **HTTP 400** with `is_invalid_image: True`, displays an error toast, and vocalizes a bilingual voice reminder asking for an authentic fundus photograph.

---

## 4. Technology Stack

- **Backend**: Python 3, Flask web microframework, SQLite3.
- **Deep Learning**: PyTorch (`torch`, `torchvision`), EfficientNet, U-Net.
- **Computer Vision**: OpenCV (`cv2`), Pillow (`PIL`), NumPy.
- **Frontend**: HTML5, Vanilla CSS3 (custom clinical theme tokens), JavaScript (ES6+), Bootstrap 5.
- **Speech APIs**: Native browser Web Speech API (`SpeechSynthesis` and `SpeechRecognition`).

---

## 5. Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Adi11-GCET/retina-xai.git
   cd retina-xai
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Flask server**:
   ```bash
   python app.py
   ```

4. **Access the application**:
   Open your browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

---

## 6. Verification & Testing

Run the automated test suite covering all pages, API endpoints, the multi-feature retinal validator, and segmentation outputs:

```bash
python -m unittest test_app.py
```

Expected output:
```
Ran 15 tests in 0.945s
OK
```

---

## 7. Limitations & Clinical Governance

> **IMPORTANT CLINICAL NOTICE:**
> - **Not a Medical Device**: This platform is an educational and research prototype for clinical decision support. It is **NOT certified as a primary diagnostic device** by CDSCO, FDA, or CE.
> - **High-Resolution Lesion Challenge**: The current U-Net operates at $256 \times 256$ resolution. Tiny microaneurysms (often only 2–5 pixels wide) require patch-based attention networks ($512 \times 512$ or $1024 \times 1024$) with Focal Tversky loss for reliable segmentation.
> - **Human Review Required**: All AI triage recommendations, Grad-CAM attention heatmaps, and lesion segmentations must be reviewed and countersigned by a licensed medical officer or certified ophthalmologist.
