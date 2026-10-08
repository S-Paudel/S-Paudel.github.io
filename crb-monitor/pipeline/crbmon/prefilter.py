"""Stage 2: cheap "is there a palm crown in this photo?" check before the heavy detector.

Uses CLIP zero-shot classification on the small thumbnail (about 0.1–0.3 s per
image on a laptop CPU, versus seconds to minutes for SAM3). Photos of beetles,
grubs, coconuts, people and palm-free streets are dropped here.
"""
from __future__ import annotations

import numpy as np


class PalmPrefilter:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.positive = list(cfg["positive"])
        self.negative = list(cfg["negative"])
        self._model = None

    def _load(self):
        if self._model is None:
            import torch
            from transformers import CLIPModel, CLIPProcessor
            torch.set_grad_enabled(False)
            self._proc = CLIPProcessor.from_pretrained(self.cfg["model"])
            self._model = CLIPModel.from_pretrained(self.cfg["model"]).eval()

    def palm_probability(self, images: list[np.ndarray]) -> list[float]:
        """Probability mass on the 'palm' prompts for each RGB image."""
        self._load()
        import torch
        inputs = self._proc(text=self.positive + self.negative, images=images,
                            return_tensors="pt", padding=True)
        logits = self._model(**inputs).logits_per_image          # (n_images, n_prompts)
        probs = torch.softmax(logits, dim=-1)[:, : len(self.positive)].sum(dim=-1)
        return [float(p) for p in probs]

    def passes(self, score: float) -> bool:
        return score >= self.cfg["threshold"]
