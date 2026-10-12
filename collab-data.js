/* ===========================================================
   Collaborators & field sites — data for the world map on the
   Professional page.

   Built from Sulav's own published content: the co-author lists
   and institutions in the "Selected publications" / "Career" /
   "Consultancy" sections of professional.html, plus the fieldwork
   countries listed in the facts box on the Home page. Locations
   are pinned at city or country level, not street-level.

   kind: "base" (home institution), "collaborator" (a named
   co-author's institution, drawn from a published paper), or
   "fieldsite" (a country from the fieldwork list with no single
   named collaborator attached to it).

   uncertain: true marks a pin where the exact city is inferred
   rather than confirmed (currently: Colombia and Mexico, inferred
   from co-author surnames/affiliations on two papers) — check
   these two before relying on them, and edit freely below.

   To add, move or correct a pin, only this file needs editing.
   =========================================================== */
var COLLAB_DATA = [
  {
    id: "nz",
    name: "Lincoln, New Zealand",
    lat: -43.6425, lng: 172.4680,
    kind: "base",
    note: "Home base — Bioeconomy Science Institute (formerly AgResearch). Frequent co-authors: T.A. Jackson, S. Mansfield, C. van Koten, S.D.G. Marshall, N.K. Richards."
  },
  {
    id: "usa",
    name: "Pennsylvania, USA",
    lat: 40.7982, lng: -77.8599,
    kind: "collaborator",
    note: "Penn State University — Ph.D. &amp; M.Sc. (Entomology); also AIARD Future Leader Fellowship, Borlaug Fellowship, and 2018 ICPP conference (Boston)."
  },
  {
    id: "nepal",
    name: "Nepal",
    lat: 27.7172, lng: 85.3240,
    kind: "collaborator",
    note: "International Development Enterprises (iDE) &amp; Tribhuvan University — B.Sc., and nearly a decade leading agricultural development programmes."
  },
  {
    id: "png",
    name: "Port Moresby, Papua New Guinea",
    lat: -9.4438, lng: 147.1803,
    kind: "collaborator",
    note: "Coconut rhinoceros beetle surveillance work with J. Pakoawia and M. Ero — field notes from Papua New Guinea."
  },
  {
    id: "timor-leste",
    name: "Timor-Leste",
    lat: -8.5569, lng: 125.5603,
    kind: "collaborator",
    note: "Confirmation of coconut rhinoceros beetle presence — co-authored with G. Soares and A. Ximenes."
  },
  {
    id: "vanuatu",
    name: "Efate / Santo, Vanuatu",
    lat: -17.7333, lng: 168.3273,
    kind: "collaborator",
    note: "Coconut rhinoceros beetle outbreak and biocontrol work with S. Boulekouran, plus repeat field trips to Santo."
  },
  {
    id: "bhutan",
    name: "Bhutan",
    lat: 27.4712, lng: 89.6339,
    kind: "collaborator",
    note: "Scoping study with Bhutan's Ministry of Agriculture and Forestry on agricultural input and extension expansion."
  },
  {
    id: "cambodia",
    name: "Cambodia",
    lat: 11.5564, lng: 104.9282,
    kind: "fieldsite",
    note: "iDE Cambodia — Integrated Pest Management programme design and training; also Horticulture Innovation Lab meeting, Siem Reap."
  },
  {
    id: "india",
    name: "India",
    lat: 28.6139, lng: 77.2090,
    kind: "collaborator",
    note: "CABI-led climate change and smallholder research; invited presentation at Tamil Nadu Agricultural University."
  },
  {
    id: "uk",
    name: "United Kingdom",
    lat: 51.5979, lng: -1.1222,
    kind: "collaborator",
    note: "CABI (Centre for Agriculture and Biosciences International) — invited presentation on insect–plant interactions and climate."
  },
  {
    id: "germany",
    name: "Germany",
    lat: 47.9990, lng: 7.8421,
    kind: "collaborator",
    note: "University of Freiburg — invited presentation comparing IPM in developed vs. developing countries."
  },
  {
    id: "russia",
    name: "Russia",
    lat: 55.7558, lng: 37.6173,
    kind: "fieldsite",
    note: "Moscow State Agro-Engineering University — research scholar, agricultural transformation post-Soviet Union."
  },
  {
    id: "indonesia",
    name: "Bali, Indonesia",
    lat: -8.3405, lng: 115.0920,
    kind: "fieldsite",
    note: "Bio-protection Research Alliance for Asia-Pacific — invited presentation on pest monitoring under climate change."
  },
  {
    id: "bangladesh",
    name: "Bangladesh",
    lat: 23.8103, lng: 90.4125,
    kind: "fieldsite",
    note: "Fieldwork."
  },
  {
    id: "samoa",
    name: "Samoa",
    lat: -13.8333, lng: -171.7667,
    kind: "fieldsite",
    note: "Fieldwork — Pacific biosecurity and invasive species surveillance."
  },
  {
    id: "costa-rica",
    name: "Costa Rica",
    lat: 9.9281, lng: -84.0907,
    kind: "fieldsite",
    note: "Fieldwork."
  },
  {
    id: "colombia",
    name: "Colombia",
    lat: 4.7110, lng: -74.0721,
    kind: "collaborator",
    uncertain: true,
    note: "Inferred from co-author L.F. Villamizar on the 2021 biological control review — exact city not confirmed."
  },
  {
    id: "mexico",
    name: "Mexico",
    lat: 19.4326, lng: -99.1332,
    kind: "collaborator",
    uncertain: true,
    note: "Inferred from co-author M. Nájera-Rincón on the 2022 Western hemisphere detection paper — exact city not confirmed."
  }
];
