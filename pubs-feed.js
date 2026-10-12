/* ===========================================================
   Live publications feed — pulls from OpenAlex (free, no key,
   https://openalex.org) and replaces the hand-written "Selected
   publications" list on load. If the fetch fails or hasn't been
   configured yet, the original static list stays exactly as-is.

   To point this at a different OpenAlex author profile, change
   authorIds below. Find an ID by searching openalex.org for your
   name — the profile URL looks like openalex.org/A5086706810.
   =========================================================== */
(function () {
  var authorIds = ["A5086706810"]; // Sulav Paudel — verified against Penn State / AgResearch / iDE affiliations
  var contactEmail = "sulav.paudel@agresearch.co.nz"; // sent as OpenAlex's "mailto" param for a faster, more reliable lane; leave "" to omit
  var CACHE_KEY = "sp_pubs_feed_v1";
  var CACHE_TTL_MS = 24 * 60 * 60 * 1000; // refresh at most once a day
  var INITIAL_SHOW = 10;

  var listEl = document.getElementById("pubList");
  var noteEl = document.getElementById("pubNote");
  if (!listEl || !authorIds.length) return; // nothing to do — static list stands

  function cacheGet() {
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed.fetchedAt || Date.now() - parsed.fetchedAt > CACHE_TTL_MS) return null;
      return parsed.works || null;
    } catch (e) {
      return null;
    }
  }

  function cacheSet(works) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ fetchedAt: Date.now(), works: works }));
    } catch (e) {
      /* storage unavailable — fine, just skip caching */
    }
  }

  function isSulav(name) {
    return /paudel/i.test(name || "");
  }

  function escapeHTML(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function formatAuthors(authorships) {
    if (!authorships || !authorships.length) return "";
    var names = authorships.map(function (a) {
      return (a.author && a.author.display_name) || "";
    }).filter(Boolean);
    var shown = names.slice(0, 6);
    var html = shown
      .map(function (n) {
        var safe = escapeHTML(n);
        return isSulav(n) ? "<strong>" + safe + "</strong>" : safe;
      })
      .join(", ");
    if (names.length > 6) html += " et al.";
    return html;
  }

  function workHTML(w) {
    var year = w.publication_year || "";
    var title = escapeHTML(w.title || w.display_name || "Untitled");
    var link = w.doi || (w.primary_location && w.primary_location.landing_page_url) || null;
    var venue = (w.primary_location && w.primary_location.source && w.primary_location.source.display_name) || "";
    var authors = formatAuthors(w.authorships);
    var titleHTML = link
      ? '<a href="' + escapeHTML(link) + '" target="_blank" rel="noopener">' + title + "</a>"
      : title;
    var metaParts = [];
    if (authors) metaParts.push(authors);
    if (venue) metaParts.push("<em>" + escapeHTML(venue) + "</em>");
    return (
      "<li>" +
      '<span class="pub-year mono">' + year + "</span>" +
      "<div>" +
      '<p class="pub-title">' + titleHTML + "</p>" +
      '<p class="pub-meta">' + metaParts.join(" — ") + "</p>" +
      "</div>" +
      "</li>"
    );
  }

  function render(works) {
    if (!works || !works.length) return; // leave static fallback in place

    works = works.slice().sort(function (a, b) {
      var ay = a.publication_year || 0, by = b.publication_year || 0;
      if (by !== ay) return by - ay;
      return new Date(b.publication_date || 0) - new Date(a.publication_date || 0);
    });

    listEl.innerHTML = "";
    var shown = works.slice(0, INITIAL_SHOW);
    var rest = works.slice(INITIAL_SHOW);
    shown.forEach(function (w) {
      listEl.insertAdjacentHTML("beforeend", workHTML(w));
    });

    // remove any previous "show all" button (e.g. on a re-render)
    var oldBtn = listEl.parentNode.querySelector(".pub-show-all");
    if (oldBtn) oldBtn.remove();

    if (rest.length) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pub-show-all";
      btn.textContent = "Show all " + works.length + " publications";
      btn.addEventListener("click", function () {
        rest.forEach(function (w) {
          listEl.insertAdjacentHTML("beforeend", workHTML(w));
        });
        btn.remove();
      });
      listEl.insertAdjacentElement("afterend", btn);
    }

    if (noteEl) {
      noteEl.innerHTML =
        "Live feed from " +
        '<a href="https://openalex.org/authors/' + authorIds[0] + '" target="_blank" rel="noopener">OpenAlex</a>' +
        " · " + works.length + " publications · full record on " +
        '<a href="https://scholar.google.com/citations?user=nRZD16YAAAAJ&hl=en" target="_blank" rel="noopener">Google Scholar</a>';
    }

    // Feed the "collaborating institution" map layer (see collab-map.js)
    // with real co-author institutions/countries pulled straight off
    // these works — no hand-maintained list to keep in sync.
    if (typeof window.SP_addCollabPins === "function") {
      window.SP_addCollabPins(collectCollaboratorCountries(works));
    }
  }

  function collectCollaboratorCountries(works) {
    var byCountry = {};
    works.forEach(function (w) {
      (w.authorships || []).forEach(function (a) {
        var name = (a.author && a.author.display_name) || "";
        if (!name || isSulav(name)) return; // only co-authors, not Sulav himself
        (a.institutions || []).forEach(function (inst) {
          var cc = inst.country_code;
          if (!cc) return;
          if (!byCountry[cc]) byCountry[cc] = { institutions: [], authors: [] };
          if (inst.display_name && byCountry[cc].institutions.indexOf(inst.display_name) === -1) {
            byCountry[cc].institutions.push(inst.display_name);
          }
          if (byCountry[cc].authors.indexOf(name) === -1) {
            byCountry[cc].authors.push(name);
          }
        });
      });
    });
    return byCountry;
  }

  function fetchWorks() {
    var filter = authorIds
      .map(function (id) {
        return "authorships.author.id:" + id;
      })
      .join("|");
    var url =
      "https://api.openalex.org/works?filter=" + encodeURIComponent(filter) +
      "&per-page=100&sort=publication_date:desc" +
      "&select=id,title,display_name,publication_year,publication_date,doi,authorships,primary_location" +
      (contactEmail ? "&mailto=" + encodeURIComponent(contactEmail) : "");

    return fetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error("OpenAlex request failed: " + r.status);
        return r.json();
      })
      .then(function (data) {
        return data.results || [];
      });
  }

  var cached = cacheGet();
  if (cached) {
    render(cached);
  } else {
    fetchWorks()
      .then(function (works) {
        if (works && works.length) {
          cacheSet(works);
          render(works);
        }
      })
      .catch(function () {
        /* network error, CORS issue, etc. — static list already in the page, nothing to do */
      });
  }
})();
