# RETINA-XAI / DrishtiAI Model Directory

Trained PyTorch weights deployed in this directory:

- `retina_idrid_model.pth`: 5-Class Diabetic Retinopathy classification model (Custom PyTorch CNN with `ResidualConvBlock` feature hierarchy trained on IDRiD).
- `retinal_segmentation_model.pth`: U-Net retinal lesion and optic disc pixel segmentation model.

## Model Specifications:
- **Framework**: PyTorch (CPU-optimized, single-thread inference)
- **Input Dimensions**: `224 x 224 x 3` (RGB normalized with ImageNet statistics)
- **Output**: 5-class softmax distribution:
  - Class 0: No DR
  - Class 1: Mild DR
  - Class 2: Moderate DR
  - Class 3: Severe DR
  - Class 4: Proliferative DR
- **Grad-CAM Target**: Final convolutional feature maps (`features[11]` residual block)
- **Segmentation Targets**: Optic Disc (OD), Haemorrhages (HE), Microaneurysms (MA), Hard Exudates (EX), Soft Exudates (SE).

## Graceful Fallback:
If `.pth` weights are not present, RETINA-XAI automatically activates its built-in **Demonstration AI & Retinal Feature Heatmap Engine**, ensuring all screens, visual overlays, and clinician review workflows operate smoothly.
