import cv2
import numpy as np
from PIL import Image
import os

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def crop_dark_borders(img, tol=15):
    """
    Crops away uninformative black/dark borders common in fundus camera photography.
    """
    if img.ndim == 2:
        mask = img > tol
        return img[np.ix_(mask.any(1), mask.any(0))]
    elif img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        mask = gray > tol
        check_shape = img[:, :, 0][np.ix_(mask.any(1), mask.any(0))].shape[0]
        if check_shape == 0:  # Image is entirely dark
            return img
        else:
            img1 = img[:, :, 0][np.ix_(mask.any(1), mask.any(0))]
            img2 = img[:, :, 1][np.ix_(mask.any(1), mask.any(0))]
            img3 = img[:, :, 2][np.ix_(mask.any(1), mask.any(0))]
            return np.stack([img1, img2, img3], axis=-1)
    return img

def enhance_fundus_green_channel(img_rgb):
    """
    Enhances contrast using CLAHE on green/luminance channel.
    Diabetic retinopathy lesions (microaneurysms, hemorrhages, hard exudates)
    display highest structural contrast under green spectrum.
    """
    # Convert RGB to LAB
    lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    
    # Apply CLAHE to L-channel
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    
    # Merge and convert back to RGB
    limg = cv2.merge((cl, a, b))
    enhanced_rgb = cv2.cvtColor(limg, cv2.COLOR_LAB2RGB)
    return enhanced_rgb

def preprocess_image_for_model(image_path, target_size=(224, 224)):
    """
    Prepares image for EfficientNetB0 (224x224x3).
    Returns normalized numpy array (1, 224, 224, 3) and cropped RGB image.
    """
    # Read image using OpenCV
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise ValueError("Could not read image from path: " + str(image_path))
    
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    
    # Crop dark borders
    cropped = crop_dark_borders(img_rgb)
    
    # Resize to target
    resized = cv2.resize(cropped, target_size, interpolation=cv2.INTER_AREA)
    
    # Float conversion & normalize to [0, 1] or EfficientNet preprocessed range
    img_array = resized.astype(np.float32) / 255.0
    input_tensor = np.expand_dims(img_array, axis=0)
    
    return input_tensor, cropped, resized
