import os
import json
from collections import defaultdict
from PIL import Image

data_root = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\data\A_Segmentation"

print("="*70)
print("RECURSIVE DATASET INSPECTION")
print("="*70)

tree = {}
file_types = defaultdict(int)
all_files = []

for root, dirs, files in os.walk(data_root):
    rel_root = os.path.relpath(root, data_root)
    tree[rel_root] = {
        'dirs': dirs,
        'file_count': len(files),
        'sample_files': files[:5]
    }
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        file_types[ext] += 1
        all_files.append((rel_root, f, ext))

print(f"\nTotal directories found: {len(tree)}")
print(f"Total files found: {len(all_files)}")
print(f"File extensions breakdown: {dict(file_types)}")

print("\nDIRECTORY STRUCTURE OVERVIEW:")
for folder, info in sorted(tree.items()):
    if folder == ".":
        print(f"  [Root]: {info['file_count']} files, Subdirs: {info['dirs']}")
    else:
        print(f"  [{folder}]: {info['file_count']} files")
        if info['sample_files']:
            print(f"     Samples: {info['sample_files']}")

# Inspect specific image properties
print("\nINSPECTING SAMPLE IMAGES...")
for rel_root, f, ext in all_files:
    if ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']:
        full_p = os.path.join(data_root, rel_root, f)
        try:
            with Image.open(full_p) as img:
                print(f"  File: {f} | Path: {rel_root} | Format: {img.format} | Size: {img.size} | Mode: {img.mode}")
            break
        except Exception as e:
            print(f"  Error reading {f}: {e}")

# Check for CSV, Excel, or label files
label_files = [f for f in all_files if f[2] in ['.csv', '.xlsx', '.xls', '.txt', '.json']]
print(f"\nLabel/Metadata files discovered: {len(label_files)}")
for rel_root, f, ext in label_files:
    print(f"  - {os.path.join(rel_root, f)}")
    
print("="*70)
