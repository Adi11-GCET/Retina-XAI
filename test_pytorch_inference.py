import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from PIL import Image
import cv2

from train_model import RetinaXAIModel

model_path = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\model\retina_idrid_model.pth"
checkpoint = torch.load(model_path, map_location="cpu")

model = RetinaXAIModel(num_classes=5, num_lesions=4)
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()
print("PyTorch model loaded successfully from checkpoint!")

test_img_path = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\data\preprocessed\images\IDRiD_55.jpg"
img = Image.open(test_img_path).convert("RGB").resize((224, 224))
arr = np.array(img, dtype=np.float32) / 255.0
mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
arr = (arr - mean) / std

input_tensor = torch.from_numpy(arr.transpose(2, 0, 1)).unsqueeze(0).float()
input_tensor.requires_grad = True

# Forward pass with Grad-CAM
features = model.forward_features(input_tensor)
pooled = model.pool(features).flatten(1)
dr_logits = model.dr_classifier(pooled)
lesion_logits = model.lesion_detector(pooled)

probs = F.softmax(dr_logits, dim=1).detach().numpy()[0]
pred_class = int(np.argmax(probs))

print(f"Predicted Class: {pred_class} | Confidence: {probs[pred_class]*100:.1f}%")
print(f"Softmax Probabilities: {[round(p*100, 1) for p in probs]}")

# Compute real Grad-CAM gradients
dr_logits[0, pred_class].backward()
grads = model.gradients[0]
activations = features[0]
weights = torch.mean(grads, dim=(1, 2), keepdim=True)
cam = torch.sum(weights * activations, dim=0)
cam = F.relu(cam)
cam = cam / (torch.max(cam) + 1e-8)
cam = cam.detach().numpy()

print("Computed Grad-CAM map shape:", cam.shape, "| Min/Max:", round(float(np.min(cam)), 3), round(float(np.max(cam)), 3))
print("Test completed successfully!")
