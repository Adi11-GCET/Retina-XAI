import os
import zipfile
import sys

zip_path = r"C:\Users\Aditiya Gupta\Downloads\A. Segmentation .zip"
extract_to = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\data\A_Segmentation"

print(f"Reading ZIP file: {zip_path} (Size: {os.path.getsize(zip_path)} bytes)...")
os.makedirs(extract_to, exist_ok=True)

with zipfile.ZipFile(zip_path, 'r') as zf:
    print(f"Total entries in archive: {len(zf.infolist())}")
    print("Extracting archive (this may take a moment)...")
    zf.extractall(extract_to)

print("Extraction completed successfully!")
