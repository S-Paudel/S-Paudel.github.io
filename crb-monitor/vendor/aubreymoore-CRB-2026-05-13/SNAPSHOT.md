# Snapshot of Aubrey Moore's CRB damage-detection code

**Author:** Aubrey Moore (University of Guam), https://github.com/aubreymoore
**Source:** https://github.com/aubreymoore/CRB-2026-05-13
**Commit:** `5734f3506c4028ce9891dd5656bc80ef43b03fd6` (8 October 2026)
**Copied on:** 8 October 2026, for the CRB Damage Monitor at https://s-paudel.github.io/crb-monitor.html

This folder is an unmodified copy of the repository above at that commit.
It is kept here so the CRB Damage Monitor keeps working and stays reproducible
even if the original repository changes or moves. All credit for this code,
the SAM3 + elliptic-Fourier-descriptor (EFD) approach to finding V-shaped frond
cuts, the synthetic palm generator (`sim_palm.py`), and the trained cut-shape
classifier (`shape_interest_model.pkl`) belongs to Aubrey Moore.

The original repository does not include a licence file. Copyright remains
with the author. It is included here as part of an active collaboration
between Aubrey Moore and Sulav Paudel. Please contact the author before reusing
it elsewhere.

## How the monitor uses this code

`crb-monitor/pipeline/crbmon/detector.py` re-implements, with attribution, the
steps from `realworld2.ipynb` and `efd_find_cuts.py`:

1. SAM3 text-prompted segmentation of "coconut palm tree" (`run_sam3_semantic_predictor`)
2. Largest external contour per palm mask (`build_db`)
3. EFD reconstruction aligned to the contour centroid (`reconstruct_aligned_mask`)
4. Reconstructed-minus-original difference mask, cleaned by morphological
   opening, giving candidate V-cuts (`calc_defect_contours`, `efd_find_cuts`)
5. Palms that touch the image edge are flagged (`tree_edge_proximity_sql`)
6. Optional: candidate cuts scored by the Hu-moment random-forest classifier
   (`shape_interest_model.pkl`, `shape_interest_classifier.ipynb`)

## How to cite

> Moore, A. (2026). *CRB-2026-05-13* [Computer software]. GitHub.
> https://github.com/aubreymoore/CRB-2026-05-13 (commit 5734f35)
