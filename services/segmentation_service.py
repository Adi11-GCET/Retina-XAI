"""
RETINA-XAI Retinal Lesion & Structure Segmentation Service
----------------------------------------------------------
Inference service for the trained PyTorch RetinalUNet model.
Generates 5-class segmentation masks and composite overlays for:
  1. Microaneurysms (MA) - Magenta
  2. Haemorrhages (HE) - Crimson
  3. Hard Exudates (EX) - Golden Yellow
  4. Soft Exudates (SE) - Mint Green
  5. Optic Disc (OD) - Cyan
"""

import os
import cv2
import numpy as np
import torch
from PIL import Image

from train_segmentation_model import RetinalUNet, LESION_CATEGORIES

# Color map for segmentation overlays (in BGR for OpenCV):
# BGR order:
STRUCTURE_COLORS_BGR = {
    "MA": (180, 20, 220),   # Microaneurysms: Magenta
    "HE": (20, 20, 200),    # Haemorrhages: Crimson Red
    "EX": (0, 215, 255),    # Hard Exudates: Golden Yellow
    "SE": (120, 220, 40),   # Soft Exudates: Mint Green
    "OD": (255, 210, 0)     # Optic Disc: Cyan / Light Blue
}

STRUCTURE_LABELS = {
    "MA": "Microaneurysms (MA)",
    "HE": "Haemorrhages (HE)",
    "EX": "Hard Exudates (EX)",
    "SE": "Soft Exudates (SE)",
    "OD": "Optic Disc (OD)"
}

_SEG_MODEL = None
_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model", "retinal_segmentation_model.pth")


def initialize_segmentation_model():
    global _SEG_MODEL
    if os.path.exists(_MODEL_PATH):
        try:
            model = RetinalUNet(in_channels=3, num_classes=5)
            checkpoint = torch.load(_MODEL_PATH, map_location="cpu")
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()
            _SEG_MODEL = model
            print(f"[RETINA-XAI] Successfully loaded RetinalUNet segmentation model from {_MODEL_PATH}")
            return True
        except Exception as e:
            print(f"[RETINA-XAI] Error loading RetinalUNet: {e}")
            _SEG_MODEL = None
    return False


def get_segmentation_model():
    global _SEG_MODEL
    if _SEG_MODEL is None:
        initialize_segmentation_model()
    return _SEG_MODEL


def predict_retinal_segmentation(image_path, output_dir, patient_id):
    """
    Executes segmentation inference on a fundus image and writes out visualization artifacts.

    Returns:
        dict: Paths to generated segmentation mask and overlay, plus detected lesion details.
    """
    os.makedirs(output_dir, exist_ok=True)
    seg_mask_filename = f"{patient_id}_seg_mask.jpg"
    seg_overlay_filename = f"{patient_id}_seg_overlay.jpg"

    seg_mask_path = os.path.join(output_dir, seg_mask_filename)
    seg_overlay_path = os.path.join(output_dir, seg_overlay_filename)

    rel_seg_mask = f"static/generated/{seg_mask_filename}"
    rel_seg_overlay = f"static/generated/{seg_overlay_filename}"

    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise ValueError(f"Unable to read image at {image_path}")

    h_orig, w_orig = img_bgr.shape[:2]

    model = get_segmentation_model()

    if model is not None:
        try:
            # Preprocess image to (1, 3, 256, 256)
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            img_resized = cv2.resize(img_rgb, (256, 256), interpolation=cv2.INTER_AREA)

            arr = img_resized.astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            norm = (arr - mean) / std

            tensor_input = torch.from_numpy(norm.transpose(2, 0, 1)).unsqueeze(0).float()

            with torch.no_grad():
                logits = model(tensor_input)
                probs = torch.sigmoid(logits).numpy()[0]  # Shape: (5, 256, 256)

            # Build full-resolution composite mask and overlay
            composite_mask_rgb = np.zeros((h_orig, w_orig, 3), dtype=np.uint8)
            overlay_bgr = img_bgr.copy()

            detected_structures = []
            structure_details = {}

            # Process each category
            for idx, (code, _) in enumerate(LESION_CATEGORIES):
                # Channel probability map
                prob_map = probs[idx]
                thresh = 0.50 if code == "OD" else 0.35
                bin_mask_small = (prob_map > thresh).astype(np.uint8)

                # Resize mask back to original resolution
                bin_mask_full = cv2.resize(bin_mask_small, (w_orig, h_orig), interpolation=cv2.INTER_NEAREST)
                pixel_count = int(np.sum(bin_mask_full > 0))

                bgr_color = STRUCTURE_COLORS_BGR[code]
                rgb_color = (bgr_color[2], bgr_color[1], bgr_color[0])

                if pixel_count > 10:
                    detected_structures.append(STRUCTURE_LABELS[code])
                    structure_details[code] = {
                        "name": STRUCTURE_LABELS[code],
                        "pixel_count": pixel_count,
                        "color_rgb": rgb_color,
                        "color_hex": f"#{rgb_color[0]:02x}{rgb_color[1]:02x}{rgb_color[2]:02x}"
                    }

                    # Paint on composite mask
                    mask_indices = bin_mask_full > 0
                    composite_mask_rgb[mask_indices] = rgb_color

                    # Blend onto overlay with semi-transparency
                    color_layer = np.zeros_like(img_bgr)
                    color_layer[mask_indices] = bgr_color
                    alpha = 0.55
                    overlay_bgr[mask_indices] = cv2.addWeighted(
                        img_bgr[mask_indices], 1.0 - alpha, color_layer[mask_indices], alpha, 0
                    )

            # Save generated artifacts
            # OpenCV writes BGR
            cv2.imwrite(seg_mask_path, cv2.cvtColor(composite_mask_rgb, cv2.COLOR_RGB2BGR))
            cv2.imwrite(seg_overlay_path, overlay_bgr)

            return {
                "success": True,
                "seg_mask_path": rel_seg_mask,
                "seg_overlay_path": rel_seg_overlay,
                "detected_structures": detected_structures,
                "structure_details": structure_details,
                "detected_lesions": structure_details,
                "model_active": True
            }

        except Exception as e:
            print(f"[RETINA-XAI] Segmentation inference error: {e}")

    # Fallback if model not ready or inference error
    fallback_mask = np.zeros((h_orig, w_orig, 3), dtype=np.uint8)
    cv2.imwrite(seg_mask_path, fallback_mask)
    cv2.imwrite(seg_overlay_path, img_bgr)

    return {
        "success": False,
        "seg_mask_path": rel_seg_mask,
        "seg_overlay_path": rel_seg_overlay,
        "detected_structures": [],
        "structure_details": {},
        "detected_lesions": {},
        "model_active": False
    }
