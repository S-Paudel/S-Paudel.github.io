# CRB Monitor

**Two pages:**
- **CRB Surveillance:** https://s-paudel.github.io/crb-surveillance.html
- **CRB Damage Monitor:** https://s-paudel.github.io/crb-monitor.html

Two tools for the coconut rhinoceros beetle (*Oryctes rhinoceros*, CRB) in **South
America, the Caribbean and the continental United States**:

1. **Surveillance dashboard** (daily; `crb-surveillance.html`). It tracks every GBIF and iNaturalist record of the
   beetle in the watch regions, plus Mexico & Central America, where the beetle is
   already established on the Pacific coast. Each record keeps the date it was
   **first seen**, is graded by evidence, and triggers alerts: a new record, a first
   record in a country, a first confirmed record, a jump of more than 100 km, an
   upgrade to confirmed, a monthly spike, or a withdrawn record. Alerts are e-mailed
   as GitHub issues. It grew out of Sulav Paudel's *Automated Pre-border
   surveillance.R* (B3 2026).
2. **Palm damage screening** (weekly; `crb-monitor.html`). Coconut palm photos on iNaturalist in the
   watch regions are screened for the beetle's V-shaped frond cuts with Aubrey Moore's
   SAM3 + elliptic Fourier detector. Photos are **never copied**: the page hot-links
   them and keeps only the link and the analysis.

## What's in this folder

```
crb-surveillance.html             (one level up) the surveillance page ("CRB Surveillance" in the site menu)
crb-monitor.html                  (one level up) the palm-damage page ("CRB Damage" in the site menu)
crb-monitor/
  assets/crb-surveillance.js      surveillance page script (also does a live check from the browser)
  assets/crb-monitor.js           palm-damage page script: results, iNaturalist browsing, links, viewer
  assets/crb-monitor.css          styles for both pages
  data/
    surveillance.json             every watch-list record: source link, country, dates, evidence, reviews, alerts
    results.json                  palm photos screened: links, location, dates, analysis, reviews
    rejected.json                 photos the palm check ruled out (so they are never re-checked)
    scan_log.json                 one entry per photo scan
    regions.json                  watch regions and countries (iNaturalist place ids, ISO codes, boxes)
  pipeline/
    config.toml                   ALL settings: regions, species, dates, filters, detector
    crbmon/                       Python package (python -m crbmon …)
    tests/                        detector tests (Aubrey's synthetic palms) + surveillance tests (real records)
  vendor/aubreymoore-CRB-2026-05-13/   unmodified snapshot of Aubrey's repository (commit 5734f35)
  CITATION.cff
  setup/                          the GitHub Actions workflows, to move into ../.github/workflows/:
    crb-surveillance.yml          daily surveillance + alert issues   (no keys needed)
    crb-scan.yml                  weekly palm-photo scan              (HF_TOKEN for the detector)
    crb-issue.yml                 handles "Send for analysis" and review issues from the page
```

## Surveillance: evidence grades

| Grade | Means |
|---|---|
| Confirmed | iNaturalist research grade (wild), or confirmed by a reviewer on the page |
| Needs checking | iNaturalist "needs ID" / casual, or a non-iNaturalist GBIF record (museum, survey, lab, DNA) |
| Captive / lab | iNaturalist captive or cultivated (pets, cultures, interceptions) |
| Not this species | marked as a mis-identification by a reviewer; excluded from counts and alerts |

Records already published when monitoring began are marked as such. The page treats
their iNaturalist upload date as the date they arrived, so "new since" still works for
the past.

## How a palm photo is screened, cheapest step first

| Stage | What it does | Cost |
|---|---|---|
| 1. Search filters | Only the chosen **regions** and **dates**. Only **open licences**. Only records **identified as coconut palm**. Only records **added since the last scan**. | free (done by iNaturalist) |
| 2. Skip known | Anything already in `results.json` or `rejected.json` is skipped | free |
| 3. Palm check | CLIP looks at the small thumbnail: "is a palm crown visible?" Drops nuts, flowers, trunks, people and palm-free scenes | ~0.2 s/photo on CPU |
| 4. Detector | Aubrey Moore's SAM3 + elliptic Fourier V-cut detector, then his cut-shape classifier | seconds–minutes on CPU, <1 s on GPU |
| 5. Human review | "Confirm damage / Not CRB damage" buttons on each photo | — |

GBIF, Mapillary and Flickr photo collectors are still in the code, switched off in
`config.toml` (`[sources.*] enabled = false`), for later.

## One-time setup

See `setup/README.md` for step-by-step instructions. In short:

1. Move the three workflow files from `setup/` into `.github/workflows/`, then commit and push.
2. Under **Settings → Actions → General**, set workflow permissions to *Read and write*.
3. Optional: add the `HF_TOKEN` secret (Hugging Face, with SAM3 access) to turn on
   automatic damage analysis. The surveillance dashboard needs no keys.

## Changing what is watched

Edit `pipeline/config.toml` and commit the change. The next run uses it.

- `[surveillance] species`: watch-list species. Add more, e.g. `"Rhynchophorus ferrugineus"`.
- `[surveillance] regions`: watch regions (group keys from `data/regions.json`)
- `[surveillance] jump_km`, `spike_min_records`: alert sensitivity
- `[filters] regions`: regions for palm-photo screening, as group keys or ISO codes such as `"PR"` or `"BR"`
- `[filters] observed_from` / `observed_to`: photo date window
- `[filters] max_new_per_source`: photos collected per region per scan
- `[prefilter] threshold`: raise it to send fewer, more palm-like photos to the detector
- `[detector] max_per_run_cpu`: how many photos the free GitHub runner analyses per scan

## Running the detector on a GPU (recommended for large batches)

GitHub's free runners have no GPU, so they analyse about 10 photos per scan. Everything
else waits in the queue ("Waiting for analysis" on the page). To clear the queue on a
machine with an NVIDIA GPU, such as Aubrey's workstation or Google Colab:

```bash
git clone https://github.com/S-Paudel/S-Paudel.github.io && cd S-Paudel.github.io/crb-monitor/pipeline
pip install -r requirements.txt
huggingface-cli login            # once, with the token from step 1
python -m crbmon analyze         # works through the queue (up to 1,000 per run)
python -m crbmon stats
cd ../.. && git add crb-monitor/data && git commit -m "CRB monitor: GPU analysis" && git push
```

Other commands:

```bash
python -m crbmon surveil                                   # surveillance check (what the daily job runs)
python -m crbmon review inat:405688598 rejected --by "Sulav Paudel" --note "Strategus"   # surveillance review
python -m crbmon scan --regions caribbean PR --no-analyze  # collect + palm check only
python -m crbmon link https://www.inaturalist.org/observations/123456789
python -m crbmon review inaturalist:123:456 confirmed --by "Aubrey Moore"
python -m pytest -q tests                                  # all tests (no GPU or network needed)
```

## Status of the detector settings

The SAM3 + EFD steps follow Aubrey's `realworld2.ipynb` and `efd_find_cuts.py`.
Two settings were tuned on Aubrey's synthetic palms (`sim_palm.py`), because no
labelled real photos were available here:

- EFD order **40**. With Aubrey's cut classifier, it found 0 / 2.0 / 3.8 / 6.3 cuts
  on palms with 0 / 2 / 4 / 8 true cuts. Order 14 found 0 / 0.8 / 1.8 / 2.9.
- Minimum cut size = **0.05 % of the palm's area**, which equals Aubrey's 50 px on
  the synthetic palm. This makes results consistent across image sizes.

Please calibrate both against Aubrey's real roadside photos before using the counts
quantitatively. Treat "possible damage" as a screening flag, not a diagnosis.

## Licences and responsible use

- Photos are shown from their original location, with the photographer's credit and
  licence. By default the monitor only uses openly licensed photos.
- Surveillance records stay the property of their publishers and observers. The
  dashboard links to each one.
- The original sources' terms apply: [iNaturalist](https://www.inaturalist.org/pages/terms),
  [GBIF](https://www.gbif.org/terms).
- SAM3 is used under Meta's SAM licence. CLIP is used under its MIT licence.

## Credits

- **Damage-detection method and code:** Aubrey Moore, University of Guam.
  https://github.com/aubreymoore/CRB-2026-05-13. A snapshot is kept in
  `vendor/aubreymoore-CRB-2026-05-13` (see its `SNAPSHOT.md`). That repository has
  no licence file, so it is included as part of our collaboration and copyright
  stays with the author.
- **Surveillance concept** (from *Automated Pre-border surveillance.R*), **monitor, data
  pipeline and web page:** Sulav Paudel.

Cite as:

> Moore, A. (2026). *CRB-2026-05-13* [Computer software]. GitHub. https://github.com/aubreymoore/CRB-2026-05-13
>
> Paudel, S., & Moore, A. (2026). *CRB Monitor* [Web application]. https://s-paudel.github.io/crb-monitor.html
