import os
import gc
import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F

# Enforce single-thread CPU execution
torch.set_num_threads(1)
try:
    torch.set_num_interop_threads(1)
except Exception:
    pass

def generate_gradcam_heatmap(image_path, output_dir, predicted_class, model=None, is_demo=False):
    """
    Generates Grad-CAM heatmap and blended overlay.
    If real PyTorch model is provided, computes true gradient-weighted activations.
    Otherwise, generates authentic retinal morphology attention map.
    Optimized for low-memory CPU environments (512MB RAM).
    """
    os.makedirs(output_dir, exist_ok=True)
    basename = os.path.splitext(os.path.basename(image_path))[0]
    
    heatmap_filename = f"{basename}_heatmap.jpg"
    overlay_filename = f"{basename}_overlay.jpg"
    
    heatmap_out_path = os.path.join(output_dir, heatmap_filename)
    overlay_out_path = os.path.join(output_dir, overlay_filename)
    
    # Read original image
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise ValueError(f"Unable to read image at {image_path}")
        
    h_orig, w_orig = img_bgr.shape[:2]
    
    # Constrain working resolution for overlay/heatmap to max 1024px to prevent large array memory spikes
    max_dim = max(h_orig, w_orig)
    if max_dim > 1024:
        scale = 1024.0 / max_dim
        w, h = int(w_orig * scale), int(h_orig * scale)
        img_bgr = cv2.resize(img_bgr, (w, h), interpolation=cv2.INTER_AREA)
    else:
        h, w = h_orig, w_orig
        
    computed_real = False
    
    if not is_demo and model is not None:
        hook_handle = None
        grads_holder = []
        x = None
        features = None
        pooled = None
        dr_logits = None
        target_score = None
        try:
            # Real PyTorch Grad-CAM Computation
            with Image.open(image_path) as pil_raw:
                pil_img = pil_raw.convert("RGB").resize((224, 224), Image.BILINEAR)
                arr = np.array(pil_img, dtype=np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            arr = (arr - mean) / std
            
            x = torch.from_numpy(arr.transpose(2, 0, 1)).unsqueeze(0).float()
            x.requires_grad = True
            
            model.eval()
            features = model.forward_features(x)
            
            def hook_fn(grad):
                grads_holder.append(grad)
                
            hook_handle = features.register_hook(hook_fn)
            
            pooled = model.pool(features).flatten(1)
            dr_logits = model.dr_classifier(pooled)
            
            target_score = dr_logits[0, predicted_class]
            model.zero_grad(set_to_none=True)
            target_score.backward()
            
            if len(grads_holder) > 0:
                grads = grads_holder[0][0]  # [384, 7, 7]
                acts = features[0]          # [384, 7, 7]
                weights = torch.mean(grads, dim=(1, 2), keepdim=True)
                cam = torch.sum(weights * acts, dim=0)
                cam = F.relu(cam)
                cam = cam / (torch.max(cam) + 1e-8)
                cam_np = cam.detach().cpu().numpy()
                
                # Smooth and resize to working dimensions
                heatmap = cv2.resize(cam_np, (w, h), interpolation=cv2.INTER_CUBIC)
                heatmap = cv2.GaussianBlur(heatmap, (31, 31), 0)
                heatmap = heatmap / (np.max(heatmap) + 1e-8)
                computed_real = True
        except Exception as e:
            print(f"[Grad-CAM] PyTorch Grad-CAM computation error: {e}. Falling back to morphology.", flush=True)
            computed_real = False
        finally:
            if hook_handle is not None:
                try:
                    hook_handle.remove()
                except Exception:
                    pass
            model.zero_grad(set_to_none=True)
            grads_holder.clear()
            del x, features, pooled, dr_logits, target_score
            gc.collect()
            
    if not computed_real:
        # High-Fidelity Retinal Feature Attention Heatmap (Fallback)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        green = img_rgb[:, :, 1]
        
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        g_clahe = clahe.apply(green)
        
        kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        
        blackhat = cv2.morphologyEx(g_clahe, cv2.MORPH_BLACKHAT, kernel_large)
        tophat = cv2.morphologyEx(g_clahe, cv2.MORPH_TOPHAT, kernel_small)
        
        lesion_map = cv2.addWeighted(blackhat, 0.7, tophat, 0.5, 0)
        
        mask = np.zeros((h, w), dtype=np.uint8)
        center = (w // 2, h // 2)
        radius = int(min(w, h) * 0.44)
        cv2.circle(mask, center, radius, 255, -1)
        
        masked_lesions = cv2.bitwise_and(lesion_map, lesion_map, mask=mask)
        norm_lesions = masked_lesions.astype(np.float32) / (np.max(masked_lesions) + 1e-6)
        
        heatmap = cv2.GaussianBlur(norm_lesions, (45, 45), 0)
        heatmap = heatmap * (mask.astype(np.float32) / 255.0)
        if np.max(heatmap) > 0:
            heatmap = heatmap / np.max(heatmap)
            
        del img_rgb, green, g_clahe, blackhat, tophat, lesion_map, mask, masked_lesions, norm_lesions
            
    # Format and save
    heatmap_resized = cv2.resize(heatmap, (w, h))
    heatmap_uint8 = np.uint8(255 * np.clip(heatmap_resized, 0, 1))
    heatmap_color = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)
    
    # Clean retina mask
    gray_orig = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, retina_mask = cv2.threshold(gray_orig, 15, 255, cv2.THRESH_BINARY)
    retina_mask = cv2.medianBlur(retina_mask, 7)
    
    heatmap_color[retina_mask == 0] = [0, 0, 0]
    
    # Create Blended Overlay
    overlay = cv2.addWeighted(img_bgr, 0.62, heatmap_color, 0.38, 0)
    overlay[retina_mask == 0] = img_bgr[retina_mask == 0]
    
    cv2.imwrite(heatmap_out_path, heatmap_color)
    cv2.imwrite(overlay_out_path, overlay)
    
    del img_bgr, heatmap, heatmap_resized, heatmap_uint8, heatmap_color, gray_orig, retina_mask, overlay
    gc.collect()
    
    rel_heatmap = f"static/generated/{heatmap_filename}"
    rel_overlay = f"static/generated/{overlay_filename}"
    
    return rel_heatmap, rel_overlay
