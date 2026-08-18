// ===========================================================
// Blog / article listing data.
//
// This is the ONLY file you need to touch to add a new post to
// the Blogs page. Copy one of the objects below, fill in your
// own details, and add it to the BLOG_POSTS array (order doesn't
// matter — the page auto-sorts by date, newest first).
//
// Fields:
//   title    - headline, as it appears on the card
//   url      - full link to the article/page (opens in a new tab)
//   source   - publication or site name (e.g. "Entomology Today")
//   date     - "YYYY-MM-DD" format, used for sorting
//   kind     - a short category label; used to build the filter
//              buttons automatically. Reuse an existing kind to
//              group posts together, or invent a new one.
//   excerpt  - one or two sentences summarising the piece, in
//              your own words (don't paste text verbatim from the
//              original article — copyright).
// ===========================================================

const BLOG_POSTS = [
  {
    title: "Beyond Science: Barriers for Global South Researchers in International Agricultural Development",
    url: "https://entomologytoday.org/2024/11/25/beyond-science-barriers-global-south-researchers-international-agricultural-development/",
    source: "Entomology Today",
    date: "2024-11-25",
    kind: "Op-ed",
    excerpt: "A first-person account of the practical barriers — visas, travel, discrimination — that researchers from the Global South face in international agricultural science, drawn from fieldwork across Bangladesh, Indonesia and the Pacific."
  },

  // --- Example placeholders — replace or delete these ---
  {
    title: "Example: Add your next article here",
    url: "https://example.com",
    source: "Publication name",
    date: "2026-01-01",
    kind: "Article",
    excerpt: "Delete this placeholder once you've added a real post, or duplicate it as a starting template."
  }
];
