import os
import numpy as np
from PIL import Image
from collections import defaultdict

data_root = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\data\A_Segmentation\A. Segmentation"
train_orig = os.path.join(data_root, "1. Original Images", "a. Training Set")
test_orig = os.path.join(data_root, "1. Original Images", "b. Testing Set")

train_images = sorted([f for f in os.listdir(train_orig) if f.endswith(".jpg")])
test_images = sorted([f for f in os.listdir(test_orig) if f.endswith(".jpg")])

print(f"Original Images: Training = {len(train_images)}, Testing = {len(test_images)}, Total = {len(train_images) + len(test_images)}")

lesion_types = [
    ("MA", "1. Microaneurysms"),
    ("HE", "2. Haemorrhages"),
    ("EX", "3. Hard Exudates"),
    ("SE", "4. Soft Exudates"),
    ("OD", "5. Optic Disc")
]

# Analyze lesion presence and pixel count for each image
def analyze_set(image_list, orig_dir, gt_set_name):
    gt_base = os.path.join(data_root, "2. All Segmentation Groundtruths", gt_set_name)
    stats = {}
    for img_name in image_list:
        stem = os.path.splitext(img_name)[0]
        stats[stem] = {}
        for code, folder in lesion_types:
            folder_path = os.path.join(gt_base, folder)
            mask_filename = f"{stem}_{code}.tif"
            mask_path = os.path.join(folder_path, mask_filename)
            if os.path.exists(mask_path):
                with Image.open(mask_path) as m:
                    arr = np.array(m)
                    pos_pixels = int(np.sum(arr > 0))
                    stats[stem][code] = {
                        'exists': True,
                        'positive_pixels': pos_pixels,
                        'has_lesion': pos_pixels > 0
                    }
            else:
                stats[stem][code] = {
                    'exists': False,
                    'positive_pixels': 0,
                    'has_lesion': False
                }
    return stats

print("\nAnalyzing training set masks...")
train_stats = analyze_set(train_images, train_orig, "a. Training Set")
print("Analyzing testing set masks...")
test_stats = analyze_set(test_images, test_orig, "b. Testing Set")

# Aggregate statistics
all_stats = {**train_stats, **test_stats}
lesion_counts = defaultdict(int)
image_lesion_summary = defaultdict(int)

for stem, lesions in all_stats.items():
    active_lesions = [code for code, d in lesions.items() if d['has_lesion'] and code != 'OD']
    for code in lesions:
        if lesions[code]['has_lesion']:
            lesion_counts[code] += 1
    image_lesion_summary[tuple(sorted(active_lesions))] += 1

print("\nLESION PRESENCE ACROSS 81 IMAGES:")
for code, name in lesion_types:
    print(f"  {name} ({code}): {lesion_counts[code]} images have positive pixels")

# Check sample mask properties
sample_mask_p = os.path.join(data_root, "2. All Segmentation Groundtruths", "a. Training Set", "1. Microaneurysms", "IDRiD_01_MA.tif")
with Image.open(sample_mask_p) as sm:
    arr = np.array(sm)
    print(f"\nSample Mask: IDRiD_01_MA.tif | Shape: {arr.shape} | Unique values: {np.unique(arr)}")

# Print sample image lesion profile
print("\nSAMPLE IMAGE LESION PROFILES:")
for stem in list(all_stats.keys())[:8]:
    active = [f"{code} ({all_stats[stem][code]['positive_pixels']} px)" for code, d in all_stats[stem].items() if d['has_lesion']]
    print(f"  {stem}: {', '.join(active) if active else 'No lesions detected'}")
