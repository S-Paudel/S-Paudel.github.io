"""Stage 3: CRB V-cut detector.

Method and original code: Aubrey Moore, https://github.com/aubreymoore/CRB-2026-05-13
(snapshot in crb-monitor/vendor/aubreymoore-CRB-2026-05-13, commit 5734f35).

  1. SAM3 segments every "coconut palm tree" in the image   (realworld2.ipynb: run_sam3_semantic_predictor)
  2. The largest outer contour of each palm mask is kept     (realworld2.ipynb: build_db)
  3. That outline is smoothed with elliptic Fourier descriptors, aligned on the centroid
                                                             (realworld2.ipynb: reconstruct_aligned_mask)
  4. Smoothed-minus-real = notches bitten out of the crown; morphological opening removes slivers
                                                             (calc_defect_contours, efd_find_cuts.py)
  5. Palms touching the image edge are flagged               (configsql.toml: tree_edge_proximity_sql)
  6. Each notch is scored by Aubrey's Hu-moment random forest (shape_interest_classifier.ipynb)

Steps 2–6 are plain functions so they can be tested without a GPU (see tests/).
Outputs are polygons in 0–1 image coordinates so the web page can draw them over
the hot-linked original photo at any size.
"""
from __future__ import annotations

import gc
import pickle
from pathlib import Path

import cv2
import numpy as np
from pyefd import elliptic_fourier_descriptors, reconstruct_contour

DETECTOR_NAME = "sam3+efd (Moore 2026)"


# --------------------------------------------------------------------------
# Geometry (Aubrey Moore's EFD method)
# --------------------------------------------------------------------------
def largest_contour(binary_mask: np.ndarray) -> np.ndarray | None:
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    c = max(contours, key=cv2.contourArea).reshape(-1, 2).astype(np.int32)
    if len(c) < 10:
        return None
    if not np.array_equal(c[0], c[-1]):
        c = np.vstack([c, c[0]])
    return c


def reconstruct_aligned_mask(shape: tuple[int, int], contour: np.ndarray, order: int) -> np.ndarray:
    """EFD-smoothed version of the palm outline, centred on the original's centroid."""
    contour = contour.reshape(-1, 2)
    m = cv2.moments(contour)
    cx, cy = (m["m10"] / m["m00"], m["m01"] / m["m00"]) if m["m00"] else contour.mean(axis=0)
    coeffs = elliptic_fourier_descriptors(contour, order=order, normalize=False)
    pts = reconstruct_contour(coeffs, locus=(cx, cy), num_points=contour.shape[0])
    recon = np.round(pts).astype(np.int32).reshape(-1, 1, 2)
    mr = cv2.moments(recon)
    rx, ry = (mr["m10"] / mr["m00"], mr["m01"] / mr["m00"]) if mr["m00"] else recon.reshape(-1, 2).mean(axis=0)
    recon = recon + np.array([int(cx - rx), int(cy - ry)], dtype=np.int32)
    mask = np.zeros(shape, np.uint8)
    cv2.drawContours(mask, [recon], -1, 255, -1)
    return mask


def find_cuts(contour: np.ndarray, shape: tuple[int, int], order: int = 14, min_pixels: float = 50,
              open_kernel: int = 3) -> list[np.ndarray]:
    """Candidate V-cuts: regions inside the smoothed outline but outside the real palm."""
    palm = np.zeros(shape, np.uint8)
    cv2.drawContours(palm, [contour.reshape(-1, 1, 2)], -1, 255, -1)
    smooth = reconstruct_aligned_mask(shape, contour, order)
    diff = cv2.bitwise_and(smooth, cv2.bitwise_not(palm))
    if open_kernel > 1:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (open_kernel, open_kernel))
        diff = cv2.morphologyEx(diff, cv2.MORPH_OPEN, k)
    cuts, _ = cv2.findContours(diff, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [c for c in cuts if cv2.contourArea(c) > min_pixels]


def touches_edge(contour: np.ndarray, w: int, h: int, margin: float) -> bool:
    """Same rule as Aubrey's tree_edge_proximity_sql: left, right or top edge."""
    x, y, bw, bh = cv2.boundingRect(contour.reshape(-1, 1, 2))
    return x / w < margin or 1 - (x + bw) / w < margin or y / h < margin


def hu_features(contour: np.ndarray) -> np.ndarray:
    """Log-transformed Hu moments, exactly as in shape_interest_classifier.ipynb."""
    hu = cv2.HuMoments(cv2.moments(contour)).flatten()
    return np.array([-np.sign(v) * np.log10(abs(v)) if v != 0 else 0.0 for v in hu])


def normalise(contour: np.ndarray, w: int, h: int, epsilon_px: float = 1.5) -> list[list[float]]:
    c = cv2.approxPolyDP(contour.reshape(-1, 1, 2).astype(np.int32), epsilon_px, True).reshape(-1, 2)
    return [[round(float(x) / w, 4), round(float(y) / h, 4)] for x, y in c]


class CutClassifier:
    def __init__(self, path: Path):
        with open(path, "rb") as f:   # trusted file: Aubrey Moore's trained model, vendored in this repo
            assets = pickle.load(f)
        self.model, self.scaler = assets["model"], assets["scaler"]

    def probability(self, contours: list[np.ndarray]) -> list[float]:
        if not contours:
            return []
        X = self.scaler.transform(np.array([hu_features(c) for c in contours]))
        return [float(p) for p in self.model.predict_proba(X)[:, list(self.model.classes_).index(1)]]


def analyse_masks(masks: list[np.ndarray], confidences: list[float], w: int, h: int, cfg: dict,
                  classifier: CutClassifier | None = None) -> dict:
    """Steps 2–6 for one image. `masks` are uint8 0/255 arrays of shape (h, w)."""
    palms, n_cuts = [], 0
    for mask, conf in zip(masks, confidences):
        contour = largest_contour(mask)
        if contour is None:
            continue
        edge = touches_edge(contour, w, h, cfg.get("edge_margin", 0.01))
        # notch size scales with the palm, not the photo: minimum cut area is a fraction of palm area
        palm_area = cv2.contourArea(contour.reshape(-1, 1, 2))
        min_px = max(cfg.get("min_cut_pixels_floor", 12), cfg.get("min_cut_fraction", 0.0005) * palm_area)
        cuts = find_cuts(contour, (h, w), cfg.get("efd_order", 14), min_px, cfg.get("open_kernel", 3))
        probs = classifier.probability(cuts) if classifier else [None] * len(cuts)
        cut_out = []
        for c, p in zip(cuts, probs):
            m = cv2.moments(c)
            keep = p is None or p >= cfg.get("cut_probability", 0.5)
            cut_out.append({"poly": normalise(c, w, h, 1.0), "p": None if p is None else round(p, 3),
                            "cx": round(m["m10"] / m["m00"] / w, 4) if m["m00"] else None,
                            "cy": round(m["m01"] / m["m00"] / h, 4) if m["m00"] else None,
                            "counted": bool(keep and not edge)})
        counted = sum(c["counted"] for c in cut_out)
        n_cuts += counted
        palms.append({"conf": round(float(conf), 3), "touches_edge": edge, "n_cuts": counted,
                      "area": round(palm_area / (w * h), 4),
                      "poly": normalise(contour, w, h, max(1.5, 0.003 * max(w, h))), "cuts": cut_out})
    if not palms:
        verdict = "no_palm_found"
    elif n_cuts >= cfg.get("min_cuts_for_damage", 1):
        verdict = "candidate_damage"
    else:
        verdict = "no_damage_detected"
    return {"detector": DETECTOR_NAME, "width": w, "height": h, "n_palms": len(palms),
            "n_cuts": n_cuts, "verdict": verdict, "palms": palms,
            # without Aubrey's classifier the gaps between fronds are counted too (many false cuts)
            "cut_filter": "hu-moment classifier" if classifier else "none"}


# --------------------------------------------------------------------------
# SAM3 segmentation (needs ultralytics + the gated sam3.pt checkpoint)
# --------------------------------------------------------------------------
class Sam3Detector:
    def __init__(self, cfg: dict, base: Path):
        import torch
        self.cfg = cfg
        self.torch = torch
        self.gpu = torch.cuda.is_available() if cfg.get("device", "auto") == "auto" else cfg["device"] != "cpu"
        weights = (base / cfg["weights"]).resolve()
        if not weights.exists():
            from huggingface_hub import hf_hub_download
            print(f"  downloading {cfg['hf_filename']} from {cfg['hf_repo']} (needs HF_TOKEN + accepted licence)…")
            weights = Path(hf_hub_download(cfg["hf_repo"], cfg["hf_filename"], local_dir=str(weights.parent)))
        from ultralytics.models.sam import SAM3SemanticPredictor
        self.predictor = SAM3SemanticPredictor(overrides=dict(
            conf=cfg.get("conf", 0.25), task="segment", mode="predict", model=str(weights),
            half=self.gpu, save=False, verbose=False, imgsz=cfg.get("imgsz", 1008), batch=1,
            device="0" if self.gpu else "cpu"))
        self.classifier = None
        if cfg.get("use_cut_classifier"):
            try:
                self.classifier = CutClassifier((base / cfg["cut_classifier"]).resolve())
            except Exception as e:  # sklearn version mismatch etc. — run without it
                print(f"  cut classifier not loaded ({e}); counting all cuts")

    @property
    def max_per_run(self) -> int:
        return self.cfg["max_per_run_gpu" if self.gpu else "max_per_run_cpu"]

    def analyse(self, rgb: np.ndarray) -> dict:
        h, w = rgb.shape[:2]
        self.predictor.set_image(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        results = self.predictor(text=list(self.cfg.get("prompts", ["coconut palm tree"])))
        res = results[0].cpu()
        masks, confs = [], []
        if res.masks is not None and len(res.masks.data):
            data = (res.masks.data.numpy() > 0.5).astype(np.uint8) * 255
            confs = res.boxes.conf.numpy().tolist() if res.boxes is not None else [1.0] * len(data)
            for m in data:
                if m.shape != (h, w):
                    m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
                masks.append(m)
        del results, res
        gc.collect()
        if self.gpu:
            self.torch.cuda.empty_cache()   # Aubrey's work-around for GPU out-of-memory errors
        return analyse_masks(masks, confs, w, h, self.cfg, self.classifier)
