import os
import json
import time
import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from PIL import Image

# Set deterministic seeds
torch.manual_seed(42)
np.random.seed(42)

device = torch.device("cpu")
print(f"Using training device: {device}")

# 1. Dataset Definition
class IDRiDDataset(Dataset):
    def __init__(self, manifest_items, is_train=True):
        self.items = manifest_items
        self.is_train = is_train

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        item = self.items[idx]
        img_path = item["image_path"]
        
        # Read image
        img = Image.open(img_path).convert("RGB")
        img = img.resize((224, 224), Image.BILINEAR)
        arr = np.array(img, dtype=np.float32) / 255.0
        
        # Data augmentation for training
        if self.is_train:
            if np.random.rand() > 0.5:
                arr = np.fliplr(arr)
            if np.random.rand() > 0.5:
                arr = np.flipud(arr)
            if np.random.rand() > 0.5:
                # Slight brightness adjustment
                factor = np.random.uniform(0.9, 1.1)
                arr = np.clip(arr * factor, 0.0, 1.0)
                
        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        
        # [H, W, C] -> [C, H, W]
        tensor_img = torch.from_numpy(arr.transpose(2, 0, 1)).float()
        
        severity = torch.tensor(item["severity_grade"], dtype=torch.long)
        multi_label = torch.tensor(item["multi_label"], dtype=torch.float32)
        
        return tensor_img, severity, multi_label, item["stem"]

# 2. Model Architecture: Efficient Retinal CNN with Grad-CAM Hooks
class ResidualConvBlock(nn.Module):
    def __init__(self, in_c, out_c, stride=1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_c, out_c, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_c)
        self.conv2 = nn.Conv2d(out_c, out_c, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_c)
        
        self.shortcut = nn.Sequential()
        if stride != 1 or in_c != out_c:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_c, out_c, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_c)
            )

    def forward(self, x):
        res = self.shortcut(x)
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += res
        return F.relu(out)

class RetinaXAIModel(nn.Module):
    def __init__(self, num_classes=5, num_lesions=4):
        super().__init__()
        # Feature extractor
        self.initial = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=7, stride=2, padding=3, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        ) # Output: 56x56
        
        self.stage1 = ResidualConvBlock(32, 64, stride=2)   # 28x28
        self.stage2 = ResidualConvBlock(64, 128, stride=2)  # 14x14
        self.stage3 = ResidualConvBlock(128, 256, stride=2) # 7x7
        
        # Target layer for Grad-CAM activations
        self.last_conv = nn.Sequential(
            nn.Conv2d(256, 384, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(384),
            nn.ReLU(inplace=True)
        )
        
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        
        # Output heads
        self.dr_classifier = nn.Sequential(
            nn.Dropout(0.35),
            nn.Linear(384, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, num_classes)
        )
        
        self.lesion_detector = nn.Sequential(
            nn.Dropout(0.2),
            nn.Linear(384, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, num_lesions)
        )
        
        # Grad-CAM storage
        self.gradients = None
        self.activations = None

    def activations_hook(self, grad):
        self.gradients = grad

    def forward_features(self, x):
        out = self.initial(x)
        out = self.stage1(out)
        out = self.stage2(out)
        out = self.stage3(out)
        features = self.last_conv(out)
        return features

    def forward(self, x):
        features = self.forward_features(x)
        
        # Hook for Grad-CAM
        if x.requires_grad:
            self.activations = features
            h = features.register_hook(self.activations_hook)
            
        pooled = self.pool(features).flatten(1)
        dr_logits = self.dr_classifier(pooled)
        lesion_logits = self.lesion_detector(pooled)
        
        return dr_logits, lesion_logits

def train():
    manifest_path = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\data\preprocessed\dataset_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        all_items = json.load(f)
        
    train_items = [item for item in all_items if item["split"] == "train"]
    test_items = [item for item in all_items if item["split"] == "test"]
    
    print(f"Training on {len(train_items)} images, Validating on {len(test_items)} images.")
    
    train_dataset = IDRiDDataset(train_items, is_train=True)
    val_dataset = IDRiDDataset(test_items, is_train=False)
    
    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_dataset, batch_size=8, shuffle=False)
    
    model = RetinaXAIModel(num_classes=5, num_lesions=4).to(device)
    
    # Class weights for DR severity CrossEntropyLoss
    ce_loss_fn = nn.CrossEntropyLoss()
    bce_loss_fn = nn.BCEWithLogitsLoss()
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=4e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=15)
    
    epochs = 15
    best_val_acc = 0.0
    history = []
    
    print("\nStarting model training...")
    start_time = time.time()
    
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        train_dr_correct = 0
        total_train = 0
        
        for images, severities, lesions, _ in train_loader:
            images, severities, lesions = images.to(device), severities.to(device), lesions.to(device)
            
            optimizer.zero_grad()
            dr_logits, lesion_logits = model(images)
            
            loss_dr = ce_loss_fn(dr_logits, severities)
            loss_lesions = bce_loss_fn(lesion_logits, lesions)
            loss = loss_dr + 0.6 * loss_lesions
            
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * images.size(0)
            preds = torch.argmax(dr_logits, dim=1)
            train_dr_correct += (preds == severities).sum().item()
            total_train += images.size(0)
            
        scheduler.step()
        
        # Validation
        model.eval()
        val_loss = 0.0
        val_dr_correct = 0
        total_val = 0
        
        with torch.no_grad():
            for images, severities, lesions, _ in val_loader:
                images, severities, lesions = images.to(device), severities.to(device), lesions.to(device)
                dr_logits, lesion_logits = model(images)
                
                loss_dr = ce_loss_fn(dr_logits, severities)
                loss_lesions = bce_loss_fn(lesion_logits, lesions)
                loss = loss_dr + 0.6 * loss_lesions
                
                val_loss += loss.item() * images.size(0)
                preds = torch.argmax(dr_logits, dim=1)
                val_dr_correct += (preds == severities).sum().item()
                total_val += images.size(0)
                
        train_loss /= total_train
        val_loss /= total_val
        train_acc = (train_dr_correct / total_train) * 100.0
        val_acc = (val_dr_correct / total_val) * 100.0
        
        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_acc": round(train_acc, 1),
            "val_loss": round(val_loss, 4),
            "val_acc": round(val_acc, 1)
        })
        
        print(f"Epoch {epoch:02d}/{epochs} | Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.1f}% | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.1f}%")
        
        # Save best model
        if val_acc >= best_val_acc or epoch == epochs:
            best_val_acc = val_acc
            out_model_path = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\model\retina_idrid_model.pth"
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "val_acc": val_acc,
                "classes": [
                    "No Diabetic Retinopathy",
                    "Mild Diabetic Retinopathy",
                    "Moderate Diabetic Retinopathy",
                    "Severe Diabetic Retinopathy",
                    "Proliferative Diabetic Retinopathy"
                ],
                "lesion_classes": ["Microaneurysms", "Haemorrhages", "Hard Exudates", "Soft Exudates"]
            }, out_model_path)
            
    total_time = round(time.time() - start_time, 2)
    print(f"\nTraining completed in {total_time} seconds! Best Validation Accuracy: {best_val_acc:.1f}%")
    
    # Save training metadata
    meta_path = r"C:\Users\Aditiya Gupta\.gemini\antigravity\scratch\retina-xai\model\model_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({
            "dataset": "IDRiD (Indian Diabetic Retinopathy Image Dataset)",
            "total_images": len(all_items),
            "train_count": len(train_items),
            "val_count": len(test_items),
            "best_val_accuracy": best_val_acc,
            "epochs": epochs,
            "history": history
        }, f, indent=2)
    print(f"Model saved to {out_model_path}")
    print(f"Metadata saved to {meta_path}")

if __name__ == "__main__":
    train()
