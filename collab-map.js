/* ===========================================================
   Collaborators & field sites map.

   Two layers:
   1. Field sites — static, from COLLAB_DATA (collab-data.js),
      rendered immediately.
   2. Collaborating institutions — live, derived automatically
      from your OpenAlex publication data. pubs-feed.js computes
      this (country code -> institutions/co-authors seen on your
      papers) and calls window.SP_addCollabPins(...) once it has
      it, whether that's from a fresh fetch or the daily cache.
      Nothing here needs editing when you publish a new paper
      with a new co-author country — it just shows up.

   Requires Leaflet (loaded before this file) and collab-data.js.
   =========================================================== */
(function () {
  var mapEl = document.getElementById("collabMap");
  if (!mapEl || typeof window.L === "undefined" || typeof window.COLLAB_DATA === "undefined") return;

  var colors = {
    base: "#D6F24C",
    collaborator: "#6FB8FF",
    fieldsite: "#E8A23D"
  };
  var labels = {
    base: "Home base",
    collaborator: "Collaborating institution (from publications)",
    fieldsite: "Field site"
  };

  // Approximate country centroids (ISO 3166-1 alpha-2 -> [lat, lng, name]),
  // used only to place the live "collaborating institution" pins that
  // come from OpenAlex country codes. Country-level, not street-level.
  var COUNTRY_CENTROIDS = {
    NZ: [-41.5, 172.8, "New Zealand"], AU: [-25.3, 133.8, "Australia"],
    US: [39.8, -98.6, "USA"], CA: [56.1, -106.3, "Canada"], MX: [23.6, -102.5, "Mexico"],
    GB: [54.0, -2.0, "United Kingdom"], IE: [53.4, -8.2, "Ireland"], FR: [46.6, 2.2, "France"],
    DE: [51.2, 10.4, "Germany"], NL: [52.2, 5.3, "Netherlands"], BE: [50.6, 4.5, "Belgium"],
    CH: [46.8, 8.2, "Switzerland"], AT: [47.5, 14.6, "Austria"], IT: [42.8, 12.8, "Italy"],
    ES: [40.3, -3.7, "Spain"], PT: [39.4, -8.2, "Portugal"], SE: [60.1, 18.6, "Sweden"],
    NO: [60.5, 8.5, "Norway"], DK: [56.3, 9.5, "Denmark"], FI: [64.9, 26.0, "Finland"],
    PL: [51.9, 19.1, "Poland"], GR: [39.1, 21.8, "Greece"], TR: [38.9, 35.2, "Turkey"],
    RU: [61.5, 105.3, "Russia"], UA: [48.4, 31.2, "Ukraine"],
    CN: [35.9, 104.2, "China"], JP: [36.2, 138.3, "Japan"], KR: [36.5, 127.8, "South Korea"],
    TW: [23.7, 121.0, "Taiwan"], HK: [22.3, 114.2, "Hong Kong"],
    IN: [22.0, 79.0, "India"], PK: [30.4, 69.3, "Pakistan"], BD: [23.8, 90.4, "Bangladesh"],
    NP: [28.2, 84.0, "Nepal"], BT: [27.5, 90.4, "Bhutan"], LK: [7.9, 80.8, "Sri Lanka"],
    ID: [-2.5, 118.0, "Indonesia"], MY: [4.2, 101.9, "Malaysia"], SG: [1.35, 103.8, "Singapore"],
    TH: [15.9, 101.0, "Thailand"], VN: [14.1, 108.3, "Vietnam"], PH: [12.9, 121.8, "Philippines"],
    KH: [12.6, 104.9, "Cambodia"], LA: [19.9, 102.5, "Laos"], MM: [21.9, 95.9, "Myanmar"],
    PG: [-6.3, 143.9, "Papua New Guinea"], VU: [-15.4, 166.9, "Vanuatu"], FJ: [-17.7, 178.1, "Fiji"],
    SB: [-9.6, 160.2, "Solomon Islands"], WS: [-13.8, -172.1, "Samoa"], TO: [-21.2, -175.2, "Tonga"],
    TL: [-8.9, 125.7, "Timor-Leste"],
    ZA: [-30.6, 22.9, "South Africa"], KE: [-0.02, 37.9, "Kenya"], TZ: [-6.4, 34.9, "Tanzania"],
    UG: [1.4, 32.3, "Uganda"], NG: [9.1, 8.7, "Nigeria"], GH: [7.9, -1.0, "Ghana"],
    ET: [9.1, 40.5, "Ethiopia"], EG: [26.8, 30.8, "Egypt"], MA: [31.8, -7.1, "Morocco"],
    BR: [-14.2, -51.9, "Brazil"], AR: [-38.4, -63.6, "Argentina"], CL: [-35.7, -71.5, "Chile"],
    CO: [4.6, -74.3, "Colombia"], PE: [-9.2, -75.0, "Peru"], EC: [-1.8, -78.2, "Ecuador"],
    VE: [6.4, -66.6, "Venezuela"], BO: [-16.3, -63.6, "Bolivia"], UY: [-32.5, -55.8, "Uruguay"],
    CR: [9.7, -83.8, "Costa Rica"], PA: [8.5, -80.8, "Panama"], GT: [15.8, -90.2, "Guatemala"],
    DO: [18.7, -70.2, "Dominican Republic"], JM: [18.1, -77.3, "Jamaica"], TT: [10.7, -61.2, "Trinidad and Tobago"],
    IL: [31.0, 34.8, "Israel"], SA: [23.9, 45.1, "Saudi Arabia"], AE: [23.4, 53.8, "UAE"],
    QA: [25.4, 51.2, "Qatar"]
  };

  var map = L.map(mapEl, {
    scrollWheelZoom: false,
    worldCopyJump: true,
    minZoom: 1,
    maxBounds: [[-85, -200], [85, 200]],
    maxBoundsViscosity: 0.8
  }).setView([8, 50], 2);

  // Scroll-to-zoom only turns on after a click on the map, so the
  // map never hijacks the page's normal scroll.
  map.on("click", function () {
    map.scrollWheelZoom.enable();
  });
  mapEl.addEventListener("mouseleave", function () {
    map.scrollWheelZoom.disable();
  });

  // Plain OpenStreetMap tiles, darkened with a CSS filter to match the
  // site theme — same approach already used on the CRB Surveillance page,
  // no API key or third-party basemap service required.
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    className: "collab-tiles",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
  }).addTo(map);

  var legendEl = document.getElementById("collabLegend");
  var listEl = document.getElementById("collabList");
  var fieldNames = [];
  var collabNames = [];

  function renderLegend() {
    if (!legendEl) return;
    var order = ["base", "fieldsite", "collaborator"];
    legendEl.innerHTML = order
      .map(function (k) {
        return (
          '<span class="collab-legend-item"><span class="dot" style="background:' +
          colors[k] + '"></span>' + labels[k] + "</span>"
        );
      })
      .join("");
  }

  function renderList() {
    if (!listEl) return;
    var parts = fieldNames.concat(collabNames);
    listEl.textContent = parts.join(" · ");
  }

  function escapeHTML(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // ---- Layer 1: field sites + home base (static) ----
  window.COLLAB_DATA.forEach(function (loc) {
    var color = colors[loc.kind] || colors.fieldsite;
    L.circleMarker([loc.lat, loc.lng], {
      radius: loc.kind === "base" ? 9 : 7,
      color: color,
      weight: 2,
      fillColor: color,
      fillOpacity: 0.55
    })
      .addTo(map)
      .bindPopup("<strong>" + escapeHTML(loc.name) + "</strong><br>" + (loc.note || ""));
    fieldNames.push(loc.name);
  });

  renderLegend();
  renderList();

  // ---- Layer 2: collaborating institutions (live, from publications) ----
  // aggByCountry: { "CO": { institutions: [...], authors: [...] }, ... }
  window.SP_addCollabPins = function (aggByCountry) {
    if (!aggByCountry) return;
    var color = colors.collaborator;

    Object.keys(aggByCountry).forEach(function (cc) {
      if (cc === "NZ") return; // already represented by the home-base pin
      var centroid = COUNTRY_CENTROIDS[cc];
      if (!centroid) return; // unknown code — skip rather than guess a location

      var data = aggByCountry[cc];
      var instList = (data.institutions || []).slice(0, 4).join(", ");
      var authorList = (data.authors || []).slice(0, 6).join(", ");
      var popup =
        "<strong>" + escapeHTML(centroid[2]) + "</strong><br>" +
        (instList ? escapeHTML(instList) + "<br>" : "") +
        (authorList ? "<em>" + escapeHTML(authorList) + "</em>" : "");

      L.circleMarker([centroid[0], centroid[1]], {
        radius: 7,
        color: color,
        weight: 2,
        fillColor: color,
        fillOpacity: 0.55
      })
        .addTo(map)
        .bindPopup(popup);

      collabNames.push(centroid[2]);
    });

    renderList();
  };
})();
