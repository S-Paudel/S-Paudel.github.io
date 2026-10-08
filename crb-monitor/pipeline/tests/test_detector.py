"""Checks the EFD cut-finding steps on Aubrey Moore's synthetic palms (no GPU or SAM3 needed).

Run from crb-monitor/pipeline:   python -m pytest -q tests
"""
import random
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
VENDOR = HERE.parent.parent / "vendor" / "aubreymoore-CRB-2026-05-13"
sys.path.insert(0, str(VENDOR))
sys.path.insert(0, str(HERE.parent))

from sim_palm import generate_palm_with_cuts  # noqa: E402  (Aubrey Moore's palm simulator)

from crbmon.detector import CutClassifier, analyse_masks, find_cuts  # noqa: E402

CFG = {"efd_order": 40, "min_cut_fraction": 0.0005, "min_cut_pixels_floor": 12, "open_kernel": 3,
       "edge_margin": 0.0, "cut_probability": 0.5, "min_cuts_for_damage": 1}


def palm(n_cuts, seed):
    random.seed(seed)
    contour, mask = generate_palm_with_cuts(n_cuts)
    return contour, mask


CLASSIFIER = VENDOR / "shape_interest_model.pkl"


def test_more_cuts_means_more_detections():
    """Raw EFD notches include the gaps between fronds; Aubrey's classifier removes those."""
    try:
        clf = CutClassifier(CLASSIFIER)
    except Exception as e:
        pytest.skip(f"classifier not loadable with this scikit-learn: {e}")

    def counted(n, seed):
        cuts = find_cuts(palm(n, seed)[0], (800, 800), 40, 50, 3)
        return sum(p >= 0.5 for p in clf.probability(cuts))

    found = {n: np.mean([counted(n, s) for s in range(10)]) for n in (0, 2, 4, 8)}
    print("mean V-cuts found for 0/2/4/8 true cuts:", found)
    assert found[0] <= 0.2
    assert found[0] < found[2] < found[4] < found[8]


def test_analyse_masks_output_shape():
    _, mask = palm(6, 1)
    out = analyse_masks([mask], [0.9], 800, 800, CFG)
    assert out["n_palms"] == 1
    assert out["verdict"] in {"candidate_damage", "no_damage_detected"}
    p = out["palms"][0]
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in p["poly"])
    assert {"poly", "p", "cx", "cy", "counted"} <= set(p["cuts"][0])


def test_uncut_palm_is_not_flagged():
    try:
        clf = CutClassifier(CLASSIFIER)
    except Exception as e:
        pytest.skip(f"classifier not loadable with this scikit-learn: {e}")
    verdicts = [analyse_masks([palm(0, s)[1]], [0.9], 800, 800, CFG, clf)["verdict"] for s in range(10)]
    hits = [analyse_masks([palm(4, s)[1]], [0.9], 800, 800, CFG, clf)["verdict"] for s in range(10)]
    print("uncut:", verdicts.count("candidate_damage"), "/10 flagged; 4 cuts:", hits.count("candidate_damage"), "/10 flagged")
    assert verdicts.count("candidate_damage") <= 1
    assert hits.count("candidate_damage") >= 8


def test_no_palm():
    out = analyse_masks([], [], 640, 480, CFG)
    assert out["verdict"] == "no_palm_found"


def test_aubreys_cut_classifier_loads():
    path = VENDOR / "shape_interest_model.pkl"
    try:
        clf = CutClassifier(path)
    except Exception as e:
        pytest.skip(f"classifier not loadable with this scikit-learn: {e}")
    contour, _ = palm(6, 2)
    probs = clf.probability(find_cuts(contour, (800, 800)))
    assert probs and all(0 <= p <= 1 for p in probs)
