import os
import json
import cv2
import numpy as np
from PIL import Image

data_root = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\data\A_Segmentation\A. Segmentation"
train_orig = os.path.join(data_root, "1. Original Images", "a. Training Set")
test_orig = os.path.join(data_root, "1. Original Images", "b. Testing Set")

train_gt = os.path.join(data_root, "2. All Segmentation Groundtruths", "a. Training Set")
test_gt = os.path.join(data_root, "2. All Segmentation Groundtruths", "b. Testing Set")

out_dir = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\data\preprocessed"
os.makedirs(os.path.join(out_dir, "images"), exist_ok=True)
os.makedirs(os.path.join(out_dir, "masks_composite"), exist_ok=True)

lesion_types = [
    ("MA", "1. Microaneurysms"),
    ("HE", "2. Haemorrhages"),
    ("EX", "3. Hard Exudates"),
    ("SE", "4. Soft Exudates"),
    ("OD", "5. Optic Disc")
]

manifest = []

def process_image_set(img_dir, gt_dir, split_name):
    files = sorted([f for f in os.listdir(img_dir) if f.endswith(".jpg")])
    for idx, f in enumerate(files):
        stem = os.path.splitext(f)[0]
        img_p = os.path.join(img_dir, f)
        out_img_path = os.path.join(out_dir, "images", f"{stem}.jpg")
        
        # If already cropped and saved, skip re-cropping to save time
        if not os.path.exists(out_img_path):
            img_bgr = cv2.imread(img_p)
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            mask = gray > 15
            check_shape = img_bgr[:, :, 0][np.ix_(mask.any(1), mask.any(0))].shape[0]
            if check_shape > 0:
                cropped = img_bgr[np.ix_(mask.any(1), mask.any(0))]
            else:
                cropped = img_bgr
            resized_img = cv2.resize(cropped, (256, 256), interpolation=cv2.INTER_AREA)
            cv2.imwrite(out_img_path, resized_img)
            
        lesion_stats = {}
        composite_mask = np.zeros((256, 256), dtype=np.uint8)
        
        for code, folder in lesion_types:
            mf = os.path.join(gt_dir, folder, f"{stem}_{code}.tif")
            if os.path.exists(mf):
                with Image.open(mf) as m:
                    arr = np.array(m)
                    # Convert to 2D binary mask regardless of channel count
                    if arr.ndim == 3:
                        binary_2d = arr[:, :, 0] > 0
                    else:
                        binary_2d = arr > 0
                        
                    pos_px = int(np.sum(binary_2d))
                    lesion_stats[code] = pos_px
                    if pos_px > 0 and code != "OD":
                        m_resized = cv2.resize(binary_2d.astype(np.uint8) * 255, (256, 256), interpolation=cv2.INTER_NEAREST)
                        composite_mask = np.maximum(composite_mask, m_resized)
            else:
                lesion_stats[code] = 0
                
        out_mask_path = os.path.join(out_dir, "masks_composite", f"{stem}_mask.png")
        cv2.imwrite(out_mask_path, composite_mask)
        
        # Clinical severity grading derived from lesion burden:
        ma_px = lesion_stats.get("MA", 0)
        he_px = lesion_stats.get("HE", 0)
        ex_px = lesion_stats.get("EX", 0)
        se_px = lesion_stats.get("SE", 0)
        
        # Clinical Grading Rules
        if se_px > 5000 and he_px > 70000:
            severity = 4  # Proliferative
            sev_name = "Proliferative Diabetic Retinopathy"
        elif se_px > 0 or he_px > 45000:
            severity = 3  # Severe DR
            sev_name = "Severe Diabetic Retinopathy"
        elif ex_px > 10000 or he_px > 12000:
            severity = 2  # Moderate DR
            sev_name = "Moderate Diabetic Retinopathy"
        else:
            severity = 1  # Mild DR
            sev_name = "Mild Diabetic Retinopathy"
            
        manifest.append({
            "stem": stem,
            "filename": f"{stem}.jpg",
            "split": split_name,
            "image_path": out_img_path,
            "composite_mask_path": out_mask_path,
            "severity_grade": severity,
            "severity_name": sev_name,
            "lesions": {
                "MA": ma_px,
                "HE": he_px,
                "EX": ex_px,
                "SE": se_px,
                "OD": lesion_stats.get("OD", 0)
            },
            "multi_label": [
                1 if ma_px > 0 else 0,
                1 if he_px > 0 else 0,
                1 if ex_px > 0 else 0,
                1 if se_px > 0 else 0
            ]
        })

print("Processing training set (54 images)...")
process_image_set(train_orig, train_gt, "train")
print("Processing testing set (27 images)...")
process_image_set(test_orig, test_gt, "test")

manifest_path = os.path.join(out_dir, "dataset_manifest.json")
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"\nManifest saved to {manifest_path} with {len(manifest)} processed images.")

# Display class breakdown
sev_counts = {1: 0, 2: 0, 3: 0, 4: 0}
for m in manifest:
    sev_counts[m["severity_grade"]] += 1

print("\nDerived Clinical Severity Distribution across 81 IDRiD images:")
for sev, cnt in sorted(sev_counts.items()):
    print(f"  Grade {sev}: {cnt} images ({cnt/81*100:.1f}%)")
