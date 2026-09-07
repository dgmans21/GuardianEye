"""1D-CNN / GRU 분류기 학습 + 평가 (Confusion Matrix).

클래스 불균형(assault 274 / falldown 74 / intrusion 58)이 있어 CrossEntropyLoss에
class weight를 줘서 소수 클래스가 무시되지 않게 한다.
"""

import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sentinelpose.models.classifier import TemporalCNN, TemporalGRU

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)

SEED = 42
EPOCHS = 60
BATCH_SIZE = 16
LR = 1e-3


def stratified_split(y: np.ndarray, val_frac: float = 0.15, test_frac: float = 0.15, seed: int = SEED):
    rng = np.random.default_rng(seed)
    train_idx, val_idx, test_idx = [], [], []
    for c in np.unique(y):
        idx = np.where(y == c)[0]
        rng.shuffle(idx)
        n = len(idx)
        n_test = max(1, int(round(n * test_frac)))
        n_val = max(1, int(round(n * val_frac)))
        test_idx.extend(idx[:n_test])
        val_idx.extend(idx[n_test : n_test + n_val])
        train_idx.extend(idx[n_test + n_val :])
    return np.array(train_idx), np.array(val_idx), np.array(test_idx)


def make_loader(X, y, idx, batch_size=BATCH_SIZE, shuffle=True):
    ds = TensorDataset(torch.tensor(X[idx]), torch.tensor(y[idx]))
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle)


def train_one_model(model, name, train_loader, val_loader, class_weights, device, epochs=EPOCHS, lr=LR):
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    best_val_acc = 0.0
    best_state = None
    for epoch in range(1, epochs + 1):
        model.train()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            opt.step()

        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                pred = model(xb).argmax(1)
                correct += (pred == yb).sum().item()
                total += len(yb)
        val_acc = correct / total
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    print(f"[{name}] best val acc = {best_val_acc:.3f}")
    return model, best_val_acc


def evaluate(model, name, test_loader, classes, device):
    model.eval()
    preds, trues = [], []
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(device)
            pred = model(xb).argmax(1).cpu().numpy()
            preds.extend(pred.tolist())
            trues.extend(yb.numpy().tolist())
    preds, trues = np.array(preds), np.array(trues)
    acc = (preds == trues).mean()

    n = len(classes)
    cm = np.zeros((n, n), dtype=int)
    for t, p in zip(trues, preds):
        cm[t, p] += 1

    print(f"\n[{name}] test acc = {acc:.3f} (n={len(trues)})")
    print("confusion matrix (row=true, col=pred):", list(classes))
    for i, row in enumerate(cm):
        print(f"  {classes[i]:>10}: {row}")
    return acc, cm


def main():
    t0 = time.time()
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    data = np.load(ROOT / "data" / "dataset.npz")
    X, y, classes = data["X"], data["y"], data["classes"]

    train_idx, val_idx, test_idx = stratified_split(y)
    print(f"train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}")

    train_loader = make_loader(X, y, train_idx)
    val_loader = make_loader(X, y, val_idx, shuffle=False)
    test_loader = make_loader(X, y, test_idx, shuffle=False)

    class_counts = np.bincount(y[train_idx], minlength=len(classes))
    class_weights = torch.tensor(
        len(train_idx) / (len(classes) * class_counts), dtype=torch.float32
    ).to(device)
    print("class weights:", class_weights.cpu().numpy())

    in_channels = X.shape[1]

    results = {}
    for name, ModelCls in [("TemporalCNN", TemporalCNN), ("TemporalGRU", TemporalGRU)]:
        model = ModelCls(in_channels=in_channels, num_classes=len(classes))
        model, val_acc = train_one_model(model, name, train_loader, val_loader, class_weights, device)
        test_acc, cm = evaluate(model, name, test_loader, classes, device)
        results[name] = {"val_acc": val_acc, "test_acc": test_acc, "cm": cm}
        torch.save(model.state_dict(), OUT_DIR / f"{name.lower()}.pt")
        np.savetxt(OUT_DIR / f"{name.lower()}_confusion_matrix.csv", cm, fmt="%d", delimiter=",")

    print(f"\n총 소요 시간: {time.time() - t0:.1f}초")
    print("\n=== 요약 ===")
    for name, r in results.items():
        print(f"  {name}: val_acc={r['val_acc']:.3f} test_acc={r['test_acc']:.3f}")


if __name__ == "__main__":
    main()
