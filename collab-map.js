/* ===========================================================
   Collaborators & field sites map — renders COLLAB_DATA (see
   collab-data.js) onto a Leaflet world map inside #collabMap.
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
    collaborator: "Collaborating institution",
    fieldsite: "Field site"
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

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>',
    maxZoom: 10,
    subdomains: "abcd"
  }).addTo(map);

  var listNames = [];
  var kindsUsed = {};

  window.COLLAB_DATA.forEach(function (loc) {
    var color = colors[loc.kind] || colors.collaborator;
    kindsUsed[loc.kind] = true;

    var marker = L.circleMarker([loc.lat, loc.lng], {
      radius: loc.kind === "base" ? 9 : 7,
      color: color,
      weight: loc.uncertain ? 1.5 : 2,
      dashArray: loc.uncertain ? "3,3" : null,
      fillColor: color,
      fillOpacity: 0.55
    }).addTo(map);

    var uncertainTag = loc.uncertain ? " <em>(approximate)</em>" : "";
    marker.bindPopup(
      "<strong>" + loc.name + "</strong>" + uncertainTag + "<br>" + (loc.note || "")
    );

    listNames.push(loc.name + (loc.uncertain ? " *" : ""));
  });

  var legendEl = document.getElementById("collabLegend");
  if (legendEl) {
    var order = ["base", "collaborator", "fieldsite"];
    legendEl.innerHTML = order
      .filter(function (k) {
        return kindsUsed[k];
      })
      .map(function (k) {
        return (
          '<span class="collab-legend-item"><span class="dot" style="background:' +
          colors[k] + '"></span>' + labels[k] + "</span>"
        );
      })
      .join("");
  }

  var listEl = document.getElementById("collabList");
  if (listEl) {
    listEl.textContent = listNames.join(" · ") +
      (window.COLLAB_DATA.some(function (l) { return l.uncertain; }) ? "  (* approximate location)" : "");
  }
})();
