# RETINA-XAI AI Model Directory

Place your trained TensorFlow/Keras model here:

`dr_model.keras`

## Model Specifications:
- **Architecture**: EfficientNetB0 (or compatible CNN)
- **Input Dimensions**: `224 x 224 x 3` (RGB normalized [0, 1])
- **Output**: 5-class softmax distribution:
  - Class 0: No DR
  - Class 1: Mild DR
  - Class 2: Moderate DR
  - Class 3: Severe DR
  - Class 4: Proliferative DR
- **Grad-CAM Target Layer**: Last convolutional layer (e.g. `top_conv` in standard Keras EfficientNetB0).

## Graceful Fallback:
If `dr_model.keras` is not present, RETINA-XAI automatically activates its built-in **Demonstration AI & Retinal Feature Heatmap Engine**, ensuring all pages, visual overlays, and human review workflows operate smoothly.
