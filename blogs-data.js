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
    title: "When the Flood Tests Government Trust",
    url: "blogs/flood-government-trust.html",
    source: "Personal essay",
    date: "2026-08-28",
    kind: "Reflection",
    excerpt: "On Nepal's unusual moment of public trust in its government after the August 2026 floods, and what I think the reconstruction years ahead will demand to keep it."
  },
  {
    title: "Beyond Science: Barriers for Global South Researchers in International Agricultural Development",
    url: "https://entomologytoday.org/2024/11/25/beyond-science-barriers-global-south-researchers-international-agricultural-development/",
    source: "Entomology Today",
    date: "2024-11-25",
    kind: "Op-ed",
    excerpt: "A first-person account of the practical barriers, including visas, travel restrictions, and discrimination, that researchers from the Global South face in international agricultural science."
  },
  {
    title: "A Tiny Island and a Giant Beetle: A Fight to Save Coconut Palms in Vanuatu",
    url: "https://academic.oup.com/ae/article-abstract/70/1/32/7633249?login=false",
    source: "American Entomologist",
    date: "2024-03-21",
    kind: "Article",
    excerpt: "An account of Vanuatu's battle against the invasive coconut rhinoceros beetle, highlighting biosecurity challenges, local responses, and the importance of coconut palms to livelihoods and culture."
  },
  {
    title: "Nepal Digital Agriculture Ecosystem Assessment",
    url: "https://www.digitaldevelopment.org/library/nepal-digital-agriculture-ecosystem-assessment/",
    source: "Digital Development",
    date: "2020-02-08",
    kind: "Report",
    excerpt: "Assessment of Nepal's digital agriculture ecosystem, exploring how digital technologies can strengthen agricultural input systems, improve service delivery, and support rural development."
  },
  {
    title: "Student Travels to Washington to Share Passion for International Agriculture",
    url: "https://www.psu.edu/news/academics/story/student-travels-washington-share-passion-international-agriculture",
    source: "Penn State News",
    date: "2019-07-23",
    kind: "Profile",
    excerpt: "Profile highlighting international agriculture leadership experiences, global food security interests, and research on climate change, pest management, and agricultural development."
  },
  {
    title: "Global Gallery Gives Snapshot of Faculty, Graduate Research in World Agriculture",
    url: "https://www.psu.edu/news/academics/story/global-gallery-gives-snapshot-faculty-graduate-research-world-agriculture",
    source: "Penn State News",
    date: "2018-03-19",
    kind: "Feature",
    excerpt: "Coverage of Penn State's Global Gallery symposium showcasing international agricultural research, interdisciplinary collaboration, and graduate student engagement in global development."
  }
];
