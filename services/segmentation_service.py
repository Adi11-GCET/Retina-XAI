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

Optimized for low-memory CPU deployment (Render Free 0.1 CPU, 512MB RAM).
"""

import os
import gc
import time
import cv2
import numpy as np
import torch
from PIL import Image

# Enforce single-thread CPU execution to eliminate thread contention on 0.1 CPU
torch.set_num_threads(1)
try:
    torch.set_num_interop_threads(1)
except Exception:
    pass

from train_segmentation_model import RetinalUNet, LESION_CATEGORIES

# Color map for segmentation overlays (in BGR for OpenCV):
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
    if _SEG_MODEL is not None:
        return True
    if os.path.exists(_MODEL_PATH):
        t0 = time.perf_counter()
        try:
            model = RetinalUNet(in_channels=3, num_classes=5)
            checkpoint = torch.load(_MODEL_PATH, map_location="cpu")
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()
            _SEG_MODEL = model
            load_elapsed = (time.perf_counter() - t0) * 1000
            print(f"[RETINA-XAI TIMING] RetinalUNet segmentation model loaded in {load_elapsed:.1f}ms from {_MODEL_PATH}", flush=True)
            return True
        except Exception as e:
            print(f"[RETINA-XAI] Error loading RetinalUNet: {e}", flush=True)
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
    Optimized to minimize memory footprint and avoid duplicate tensor copies.

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

    # Constrain working resolution for overlay/mask to max 1024px to prevent large array memory spikes
    max_dim = max(h_orig, w_orig)
    if max_dim > 1024:
        scale = 1024.0 / max_dim
        w_work, h_work = int(w_orig * scale), int(h_orig * scale)
        img_bgr = cv2.resize(img_bgr, (w_work, h_work), interpolation=cv2.INTER_AREA)
    else:
        h_work, w_work = h_orig, w_orig

    model = get_segmentation_model()

    if model is not None:
        try:
            # Preprocess image to (1, 3, 256, 256)
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            img_resized = cv2.resize(img_rgb, (256, 256), interpolation=cv2.INTER_AREA)
            del img_rgb

            arr = img_resized.astype(np.float32) / 255.0
            del img_resized
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            norm = (arr - mean) / std
            del arr

            tensor_input = torch.from_numpy(norm.transpose(2, 0, 1)).unsqueeze(0).float()
            del norm

            model.eval()
            with torch.inference_mode():
                logits = model(tensor_input)
                probs = torch.sigmoid(logits).cpu().numpy()[0]  # Shape: (5, 256, 256)

            del tensor_input, logits
            gc.collect()

            # Build composite mask and overlay at constrained working resolution
            composite_mask_rgb = np.zeros((h_work, w_work, 3), dtype=np.uint8)
            overlay_bgr = img_bgr.copy()

            detected_structures = []
            structure_details = {}

            # Process each category
            for idx, (code, _) in enumerate(LESION_CATEGORIES):
                prob_map = probs[idx]
                thresh = 0.50 if code == "OD" else 0.35
                bin_mask_small = (prob_map > thresh).astype(np.uint8)

                # Resize mask to working resolution
                bin_mask_full = cv2.resize(bin_mask_small, (w_work, h_work), interpolation=cv2.INTER_NEAREST)
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

                    # Blend onto overlay with semi-transparency without allocating full-sized zero-arrays
                    alpha = 0.55
                    sub_bgr = overlay_bgr[mask_indices].astype(np.float32)
                    bgr_arr = np.array(bgr_color, dtype=np.float32)
                    overlay_bgr[mask_indices] = np.clip(
                        sub_bgr * (1.0 - alpha) + bgr_arr * alpha, 0, 255
                    ).astype(np.uint8)
                    del sub_bgr, bgr_arr

                del bin_mask_small, bin_mask_full

            # Save generated artifacts
            cv2.imwrite(seg_mask_path, cv2.cvtColor(composite_mask_rgb, cv2.COLOR_RGB2BGR))
            cv2.imwrite(seg_overlay_path, overlay_bgr)

            del img_bgr, composite_mask_rgb, overlay_bgr, probs
            gc.collect()

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
            print(f"[RETINA-XAI] Segmentation inference error: {e}", flush=True)

    # Fallback if model not ready or inference error
    fallback_mask = np.zeros((h_work, w_work, 3), dtype=np.uint8)
    cv2.imwrite(seg_mask_path, fallback_mask)
    cv2.imwrite(seg_overlay_path, img_bgr)
    del fallback_mask, img_bgr
    gc.collect()

    return {
        "success": False,
        "seg_mask_path": rel_seg_mask,
        "seg_overlay_path": rel_seg_overlay,
        "detected_structures": [],
        "structure_details": {},
        "detected_lesions": {},
        "model_active": False
    }
