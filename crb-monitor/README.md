# CRB Damage Monitor

**Live page:** https://s-paudel.github.io/crb-monitor.html

This tool screens public palm photos for the V-shaped frond cuts left by the coconut
rhinoceros beetle (*Oryctes rhinoceros*, CRB). It searches iNaturalist, GBIF,
Mapillary and Flickr, and also accepts pasted links. Photos are **never copied**.
The page hot-links them from their source and keeps only the link and the analysis.
Every record is dated by when it was **first seen**, so you can always ask
"what new damage has turned up since …?".

The damage-detection method is by **Aubrey Moore** (University of Guam).
See [Credits](#credits).

## What's in this folder

```
crb-monitor.html                  (one level up) the web page, linked from the site menu
crb-monitor/
  assets/crb-monitor.js, .css     page code: tabs, live source search, map, viewer
  data/
    results.json                  everything screened: links, location, dates, analysis, reviews
    rejected.json                 photos the palm check ruled out (so they are never re-checked)
    scan_log.json                 one entry per scan
    regions.json                  preset search areas (shared by page and pipeline)
  pipeline/
    config.toml                   ALL settings: regions, dates, sources, filters, detector
    crbmon/                       Python package (python -m crbmon …)
    tests/                        detector tests on Aubrey's synthetic palms
  vendor/aubreymoore-CRB-2026-05-13/   unmodified snapshot of Aubrey's repository (commit 5734f35)
  CITATION.cff
  setup/                          the two GitHub Actions workflows, to move into ../.github/workflows/:
    crb-scan.yml                  weekly scan (+ "Run workflow" button)
    crb-issue.yml                 handles "Send for analysis" and review issues from the page
```

## How a photo is screened, cheapest step first

| Stage | What it does | Cost |
|---|---|---|
| 1. Search filters | Only the chosen **regions** and **dates**. Only **open licences**. iNaturalist/GBIF limited to records **identified as coconut palm**. iNaturalist/Flickr ask only for records **added since the last scan**. | free (done by the source) |
| 2. Skip known | Anything already in `results.json` or `rejected.json` is skipped | free |
| 3. Thinning | Mapillary keeps one image per ~150 m per day | free |
| 4. Palm check | CLIP looks at the small thumbnail: "is a palm crown visible?" Drops beetles, grubs, coconuts, people and palm-free streets | ~0.2 s/photo on CPU |
| 5. Detector | Aubrey Moore's SAM3 + elliptic Fourier V-cut detector, then his cut-shape classifier | seconds–minutes on CPU, <1 s on GPU |
| 6. Human review | "Confirm damage / Not CRB damage" buttons on each photo | — |

iNaturalist sightings of the beetle itself are recorded on the map as **beetle
sightings**. They are not run through the detector.

## One-time setup (about 15 minutes)

0. **Put the two workflow files in place.** Move `setup/crb-scan.yml` and
   `setup/crb-issue.yml` into the repository's `.github/workflows/` folder (see
   `setup/README.md`). Nothing runs automatically until you do this.

Steps 1–3 are optional. Without them, the monitor still searches iNaturalist and GBIF.

1. **Hugging Face access to SAM3** (turns on automatic analysis).
   Sign in at https://huggingface.co/facebook/sam3, accept the licence and wait
   for approval. Then create a *read* token at https://huggingface.co/settings/tokens.
2. **Mapillary token.** Go to https://www.mapillary.com/dashboard/developers, then
   *Register application*, and copy the **client token**.
3. **Flickr key.** Get one at https://www.flickr.com/services/apps/create (non-commercial).
4. Add these on GitHub under **Settings → Secrets and variables → Actions →
   New repository secret**: `HF_TOKEN`, `MAPILLARY_TOKEN`, `FLICKR_API_KEY`.
5. Check that **Settings → Actions → General → Workflow permissions** is set to
   *Read and write*.
6. Under **Actions → "CRB monitor — scan" → Run workflow**, run the first scan now
   instead of waiting for Monday.

To *browse* Mapillary and Flickr on the page itself, paste the same Mapillary
token or Flickr key into the box on that tab. It is saved only in your browser.

## Changing what is searched

Edit `pipeline/config.toml` and commit the change. The next scan uses it. The usual settings:

- `filters.regions`: which preset areas to search (`data/regions.json` lists them; add your own)
- `filters.observed_from` / `observed_to`: photo date window
- `filters.max_new_per_source`: cap per source per region per scan
- `prefilter.threshold`: raise it to send fewer, more palm-like photos to the detector
- `detector.max_per_run_cpu`: how many photos the free GitHub runner analyses per scan

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
python -m crbmon scan --regions guam palau --no-analyze   # collect + palm check only
python -m crbmon link https://www.inaturalist.org/observations/123456789
python -m crbmon review inaturalist:123:456 confirmed --by "Aubrey Moore"
python -m pytest -q tests                                  # detector tests (no GPU needed)
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
- Mapillary imagery is CC BY-SA 4.0.
- The original sources' terms apply: [iNaturalist](https://www.inaturalist.org/pages/terms),
  [GBIF](https://www.gbif.org/terms), [Mapillary](https://www.mapillary.com/terms),
  [Flickr API](https://www.flickr.com/help/terms/api).
- SAM3 is used under Meta's SAM licence. CLIP is used under its MIT licence.

## Credits

- **Damage-detection method and code:** Aubrey Moore, University of Guam.
  https://github.com/aubreymoore/CRB-2026-05-13. A snapshot is kept in
  `vendor/aubreymoore-CRB-2026-05-13` (see its `SNAPSHOT.md`). That repository has
  no licence file, so it is included as part of our collaboration and copyright
  stays with the author.
- **Monitor, data pipeline and web page:** Sulav Paudel.

Cite as:

> Moore, A. (2026). *CRB-2026-05-13* [Computer software]. GitHub. https://github.com/aubreymoore/CRB-2026-05-13
>
> Paudel, S., & Moore, A. (2026). *CRB Damage Monitor* [Web application]. https://s-paudel.github.io/crb-monitor.html
