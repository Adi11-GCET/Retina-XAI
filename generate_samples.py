import os
import cv2
import numpy as np
from services.gradcam import generate_gradcam_heatmap

def create_synthetic_fundus(filename, severity=0, size=(512, 512)):
    w, h = size
    img = np.zeros((h, w, 3), dtype=np.uint8)
    
    # 1. Circular retinal background mask
    center = (w // 2, h // 2)
    radius = int(min(w, h) * 0.46)
    
    # Base retinal gradient (orange-red to deep amber)
    y, x = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((x - center[0])**2 + (y - center[1])**2)
    
    # Retinal color base
    # Center is warm reddish-orange (B: 25, G: 65, R: 180)
    # Periphery gets darker (B: 5, G: 20, R: 90)
    norm_dist = np.clip(dist_from_center / radius, 0, 1)
    
    b_ch = (25 * (1 - norm_dist) + 5 * norm_dist).astype(np.uint8)
    g_ch = (65 * (1 - norm_dist) + 20 * norm_dist).astype(np.uint8)
    r_ch = (185 * (1 - norm_dist) + 95 * norm_dist).astype(np.uint8)
    
    base_retina = cv2.merge([b_ch, g_ch, r_ch])
    
    # Apply circular mask
    mask = dist_from_center <= radius
    img[mask] = base_retina[mask]
    
    # 2. Optic Disc (Nasal side: x ~ 0.35 * w, y ~ 0.5 * h)
    disc_center = (int(w * 0.34), int(h * 0.50))
    disc_radius = int(radius * 0.18)
    # Outer bright yellow-orange disc
    cv2.circle(img, disc_center, disc_radius, (90, 205, 240), -1)
    # Inner physiological cup (paler yellow-white)
    cv2.circle(img, disc_center, int(disc_radius * 0.55), (140, 235, 255), -1)
    
    # 3. Macula / Fovea (Temporal side: x ~ 0.62 * w, y ~ 0.51 * h)
    macula_center = (int(w * 0.62), int(h * 0.51))
    macula_radius = int(radius * 0.22)
    
    # Darker avascular zone
    macula_overlay = img.copy()
    cv2.circle(macula_overlay, macula_center, macula_radius, (10, 35, 120), -1)
    cv2.addWeighted(macula_overlay, 0.45, img, 0.55, 0, img)
    # Central foveal reflex
    cv2.circle(img, macula_center, 4, (120, 180, 230), -1)
    
    # 4. Retinal Blood Vessels (Arcades originating from optic disc)
    vessel_color_main = (15, 20, 110)
    vessel_color_branch = (20, 30, 130)
    
    # Arcades: Superior temporal, inferior temporal, superior nasal, inferior nasal
    arcades = [
        # Superior temporal
        [(disc_center[0], disc_center[1]), (int(w*0.42), int(h*0.32)), (int(w*0.58), int(h*0.28)), (int(w*0.75), int(h*0.35))],
        # Inferior temporal
        [(disc_center[0], disc_center[1]), (int(w*0.42), int(h*0.68)), (int(w*0.58), int(h*0.72)), (int(w*0.75), int(h*0.65))],
        # Superior nasal
        [(disc_center[0], disc_center[1]), (int(w*0.26), int(h*0.35)), (int(w*0.18), int(h*0.30))],
        # Inferior nasal
        [(disc_center[0], disc_center[1]), (int(w*0.26), int(h*0.65)), (int(w*0.18), int(h*0.70))]
    ]
    
    for arc in arcades:
        pts = np.array(arc, np.int32)
        cv2.polylines(img, [pts], isClosed=False, color=vessel_color_main, thickness=5, lineType=cv2.LINE_AA)
        
    # Secondary smaller branches
    branches = [
        [(int(w*0.42), int(h*0.32)), (int(w*0.48), int(h*0.40))],
        [(int(w*0.58), int(h*0.28)), (int(w*0.65), int(h*0.38))],
        [(int(w*0.42), int(h*0.68)), (int(w*0.48), int(h*0.60))],
        [(int(w*0.58), int(h*0.72)), (int(w*0.65), int(h*0.62))],
        [(int(w*0.65), int(h*0.38)), (int(w*0.72), int(h*0.42))],
        [(int(w*0.65), int(h*0.62)), (int(w*0.72), int(h*0.58))]
    ]
    for br in branches:
        pts = np.array(br, np.int32)
        cv2.polylines(img, [pts], isClosed=False, color=vessel_color_branch, thickness=2, lineType=cv2.LINE_AA)
        
    # Smooth base vessels slightly
    img = cv2.GaussianBlur(img, (3, 3), 0)
    
    # 5. Diabetic Retinopathy Lesions by Severity
    np.random.seed(42 + severity * 7)
    
    if severity >= 1:
        # Microaneurysms (tiny dark red dots, 2-4px)
        num_ma = {1: 8, 2: 24, 3: 50, 4: 70}[severity]
        for _ in range(num_ma):
            mx = int(np.random.normal(macula_center[0] + np.random.choice([-1, 1])*40, 50))
            my = int(np.random.normal(macula_center[1], 60))
            if np.sqrt((mx - center[0])**2 + (my - center[1])**2) < radius * 0.85:
                cv2.circle(img, (mx, my), np.random.randint(2, 4), (10, 10, 85), -1)
                
    if severity >= 2:
        # Blot Hemorrhages (larger irregular dark red patches, 6-12px)
        num_blot = {2: 8, 3: 25, 4: 40}[severity]
        for _ in range(num_blot):
            bx = int(np.random.uniform(w*0.35, w*0.80))
            by = int(np.random.uniform(h*0.25, h*0.75))
            if np.sqrt((bx - center[0])**2 + (by - center[1])**2) < radius * 0.85:
                rad = np.random.randint(5, 11)
                cv2.circle(img, (bx, by), rad, (15, 15, 95), -1)
                
        # Hard Exudates (bright yellowish-white deposits, lipid residues)
        num_ex = {2: 12, 3: 35, 4: 55}[severity]
        for _ in range(num_ex):
            ex_x = int(macula_center[0] + np.random.normal(0, 45))
            ex_y = int(macula_center[1] + np.random.normal(0, 45))
            if np.sqrt((ex_x - center[0])**2 + (ex_y - center[1])**2) < radius * 0.85:
                cv2.circle(img, (ex_x, ex_y), np.random.randint(3, 7), (160, 230, 245), -1)
                
    if severity >= 3:
        # Cotton Wool Spots (soft grayish-white fluffy nerve fiber infarcts)
        num_cws = {3: 6, 4: 12}[severity]
        for _ in range(num_cws):
            cx = int(np.random.uniform(w*0.30, w*0.75))
            cy = int(np.random.uniform(h*0.25, h*0.75))
            if np.sqrt((cx - center[0])**2 + (cy - center[1])**2) < radius * 0.80:
                cw_overlay = img.copy()
                cv2.circle(cw_overlay, (cx, cy), np.random.randint(12, 22), (200, 215, 225), -1)
                cv2.addWeighted(cw_overlay, 0.40, img, 0.60, 0, img)
                
    if severity >= 4:
        # Neovascularization (frond-like disordered fine abnormal vessels near disc or arcades)
        for _ in range(16):
            start_x = disc_center[0] + np.random.randint(-15, 15)
            start_y = disc_center[1] + np.random.randint(-15, 15)
            end_x = start_x + np.random.randint(-40, 40)
            end_y = start_y + np.random.randint(-40, 40)
            cv2.line(img, (start_x, start_y), (end_x, end_y), (10, 15, 120), 2, cv2.LINE_AA)
            
        # Large preretinal / vitreous hemorrhage patch
        vh_overlay = img.copy()
        cv2.ellipse(vh_overlay, (int(w*0.65), int(h*0.35)), (45, 25), 30, 0, 360, (5, 5, 80), -1)
        cv2.addWeighted(vh_overlay, 0.75, img, 0.25, 0, img)
        
    # Re-enforce circular aperture mask with smooth anti-aliased edge
    edge_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(edge_mask, center, radius, 255, -1)
    edge_mask = cv2.GaussianBlur(edge_mask, (7, 7), 0)
    for c in range(3):
        img[:, :, c] = (img[:, :, c].astype(np.float32) * (edge_mask / 255.0)).astype(np.uint8)
        
    cv2.imwrite(filename, img)
    return filename

samples = [
    ('sample_no_dr.jpg', 0),
    ('sample_mild.jpg', 1),
    ('sample_moderate.jpg', 2),
    ('sample_severe.jpg', 3),
    ('sample_proliferative.jpg', 4)
]

sample_dir = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\static\samples"
os.makedirs(sample_dir, exist_ok=True)

for name, sev in samples:
    path = os.path.join(sample_dir, name)
    create_synthetic_fundus(path, sev)
    print(f"Generated {name} (Severity {sev})")
    
    # Generate heatmap and overlay
    heat_rel, over_rel = generate_gradcam_heatmap(path, sample_dir, sev, is_demo=True)
    print(f"Generated heatmaps for {name}")

print("All sample retinal fundus images and Grad-CAM visualizations generated successfully!")
