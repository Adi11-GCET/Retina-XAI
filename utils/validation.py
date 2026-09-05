"""
RETINA-XAI Heuristic Retinal-Image Validation Guardrail
------------------------------------------------------
A rule-based pre-screening guardrail designed to filter out obviously non-retinal
photographs (e.g. human portraits, animals, outdoor landscapes, text documents,
screenshots, and blank/corrupted files) before images enter the deep learning pipeline.

HEURISTIC CRITERIA:
1. Active circular/elliptical field-of-view (FOV) aperture illumination.
2. Hemoglobin/melanin chromatic absorption spectrum (Red dominance over Blue in physiological ranges).
3. Warm retinal hue concentration in HSV color space.
4. Green channel structural/vascular gradient variation.

IMPORTANT NOTE & LIMITATIONS:
This module is a heuristic validation guardrail, not a certified binary classifier.
Edge cases (e.g., highly atypical ocular pathology, severe vitreous hemorrhage,
or non-retinal red/orange textures) may occasionally challenge heuristic boundaries.
It provides a practical front-end safety filter for clinical triage prototypes.
"""

import cv2
import numpy as np
import os


class ValidationResult(dict):
    """
    Result object that supports both dict indexing (result['is_valid_retina'])
    and tuple unpacking (is_valid, score, reason = validate_retinal_image(...)).
    """
    def __init__(self, is_valid, score, reason, metrics=None):
        metrics = metrics or {}
        super().__init__(
            is_valid_retina=is_valid,
            is_valid=is_valid,
            score=score,
            reason=reason,
            metrics=metrics
        )
        self.is_valid_retina = is_valid
        self.is_valid = is_valid
        self.score = score
        self.reason = reason
        self.metrics = metrics

    def __iter__(self):
        return iter((self.is_valid, self.score, self.reason))

    def __getitem__(self, item):
        if isinstance(item, int):
            return (self.is_valid, self.score, self.reason)[item]
        return super().__getitem__(item)


def validate_retinal_image(image_input):
    """
    Validates whether an input image is an authentic retinal fundus photograph.

    Parameters:
        image_input (str or np.ndarray): File path to image or BGR numpy array.

    Returns:
        ValidationResult: Dict-like and tuple-like result containing
                          is_valid_retina, score, reason, and metrics.
    """
    if isinstance(image_input, str):
        if not os.path.exists(image_input):
            return ValidationResult(False, 0.0, "Image file not found.")
        img_bgr = cv2.imread(image_input)
    elif isinstance(image_input, np.ndarray):
        img_bgr = image_input
    else:
        return ValidationResult(False, 0.0, "Invalid image data format.")

    if img_bgr is None or img_bgr.size == 0:
        return ValidationResult(False, 0.0, "Image could not be read or is corrupted.")

    h, w = img_bgr.shape[:2]
    if h < 64 or w < 64:
        return ValidationResult(False, 0.0, "Image resolution is too low for ophthalmic screening (minimum 64x64).")

    # Standardize working resolution
    sample_size = (256, 256)
    small_bgr = cv2.resize(img_bgr, sample_size, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY)

    # 1. Active Field of View (FOV) Mask
    # Fundus cameras capture the retina through a dark mask aperture
    active_mask = gray > 15
    active_pixel_count = int(np.sum(active_mask))
    total_pixels = sample_size[0] * sample_size[1]
    active_fraction = float(active_pixel_count) / float(total_pixels)

    if active_fraction < 0.15:
        return ValidationResult(False, 0.05, "Image is predominantly dark or blank.")

    active_pixels_bgr = small_bgr[active_mask]
    b = active_pixels_bgr[:, 0].astype(np.float32)
    g = active_pixels_bgr[:, 1].astype(np.float32)
    r = active_pixels_bgr[:, 2].astype(np.float32)

    mean_b = float(np.mean(b))
    mean_g = float(np.mean(g))
    mean_r = float(np.mean(r))

    # 2. Chromatic Absorption Spectrum (Vascular / Retinal Hemoglobin Profile)
    # The retinal fundus is illuminated through the pupil; red is strongly reflected
    # by retinal pigment epithelium and choroid, while blue is heavily absorbed.
    # In a natural retina, Blue / Red is rarely above 0.65.
    blue_to_red_ratio = mean_b / (mean_r + 1e-5)

    if mean_r < 35.0:
        return ValidationResult(False, 0.15, "Insufficient red channel illumination for fundus evaluation.")

    # In documents, skies, outdoor nature, landscapes: Blue is prominent (B/R >= 0.70)
    if blue_to_red_ratio > 0.70:
        return ValidationResult(
            False, 0.20,
            f"Chromatic profile inconsistent with retina (Blue/Red ratio: {blue_to_red_ratio:.2f}, expected < 0.70).",
            {"blue_to_red": blue_to_red_ratio, "mean_r": mean_r}
        )

    # 3. Warm Retinal Hue Concentration in HSV Color Space
    # Retinal hues cluster heavily between 0-28 and 155-180 in OpenCV Hue (0-180)
    small_hsv = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2HSV)
    h_channel = small_hsv[:, :, 0][active_mask]
    warm_hue_count = np.sum((h_channel <= 28) | (h_channel >= 155))
    warm_hue_ratio = float(warm_hue_count) / float(active_pixel_count)

    if warm_hue_ratio < 0.60:
        return ValidationResult(
            False, 0.25,
            f"Hue distribution inconsistent with retinal fundus (Warm hue ratio: {warm_hue_ratio:.2f}, expected >= 0.60).",
            {"warm_hue_ratio": warm_hue_ratio}
        )

    # 4. Green Channel Structural & Vascular Contrast
    # The green channel exhibits microvascular patterns. Flat solid colors or uniform documents
    # have very low green standard deviation across active areas.
    std_g = float(np.std(g))
    if std_g < 6.0:
        return ValidationResult(False, 0.25, "Image lacks retinal vascular contrast (uniform or artificial graphic).")

    # 5. Document / Bright Screen Rejection
    # Scanned documents, white paper, and screenshots have high luminance across all 3 channels
    if mean_r > 220.0 and mean_g > 220.0 and mean_b > 210.0:
        return ValidationResult(False, 0.10, "Image appears to be a white document, screenshot, or overexposed paper.")

    # Compute a confidence score of retinal likelihood (0.0 to 1.0)
    score = min(1.0, (
        (1.0 - min(blue_to_red_ratio, 1.0)) * 0.40 +
        warm_hue_ratio * 0.40 +
        min(std_g / 30.0, 1.0) * 0.20
    ))

    return ValidationResult(
        True, round(score, 3), "Valid Retinal Fundus Photograph",
        {
            "blue_to_red": round(blue_to_red_ratio, 3),
            "warm_hue_ratio": round(warm_hue_ratio, 3),
            "green_std": round(std_g, 2),
            "active_fraction": round(active_fraction, 3)
        }
    )
