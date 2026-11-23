/* Interactive county map for "When the Network Goes Dark" (version 2).
   Uses D3 7.9.0 and topojson-client 3.1.0 served from this site (static/js/vendor/), and two data files from this
   site: county shapes (hurricane-counties.topo.json, Census 2022 cartographic boundaries) and each storm's reports
   (hurricane-map.json, generated from the published county-report panel). No other server is contacted.
   Counties are shaded by % of cell sites out in the chosen report; counties not in that report are white ("not
   reported", never zero). Controls: storm select, report slider, optional play button. The table under the map is
   the keyboard and screen-reader alternative to hovering. */
(function () {
  "use strict";
  var root = document.querySelector(".storm-map");
  if (!root || !window.d3 || !window.topojson) return;
  var INK = "#0F2338", PAPER = "#FFFFFF", RULE = "#C9D1D8", MUTED = "#51626F";
  var NR_BG = "#F7F8F9", NR_LINE = "#8A969F";  // "not in this report": very light grey with fine hatching
  // Two fixed scales, set once from the panel's overall distribution (never per storm); data-scale picks one.
  var SCALES = {
    cap50: {kind: "linear", cap: 50, zero: 0.12, from: 0.24,
            legend: [[0, "0%"], [10, "10%"], [20, "20%"], [30, "30%"], [40, "40%"], [50, "50%+"]]},
    steps: {kind: "steps", zero: 0.12, bins: [[5, 0.26], [15, 0.44], [30, 0.62], [50, 0.80], [Infinity, 1.0]],
            legend: [[0, "0%"], [2, "under 5%"], [10, "5–15%"], [20, "15–30%"], [40, "30–50%"], [60, "50%+"]]}
  };
  var SCALE = SCALES[root.getAttribute("data-scale")] || SCALES.cap50;
  var W = 720, H = 470;
  var stormSel = root.querySelector("#storm-map-storm");
  var slider = root.querySelector("#storm-map-day");
  var play = root.querySelector(".storm-map-play");
  var status = root.querySelector(".storm-map-status");
  var tip = root.querySelector(".storm-map-tip");
  var tableBox = root.querySelector(".storm-map-table");
  var data, storm, paths, names = {}, timer = null;

  function fmt(x, d) { return Number(x).toFixed(d); }
  function n0(x) { return Number(x).toLocaleString("en-US"); }
  function shade(v) {  // opacity of Ink over white: 0% gets a faint but visible tint, distinct from "not reported"
    if (v <= 0) return SCALE.zero;
    if (SCALE.kind === "linear") return SCALE.from + (1 - SCALE.from) * Math.min(1, v / SCALE.cap);
    for (var i = 0; i < SCALE.bins.length; i++) if (v < SCALE.bins[i][0]) return SCALE.bins[i][1];
    return 1;
  }

  function draw(topo) {
    var counties = topojson.feature(topo, topo.objects.counties);
    var states = topojson.feature(topo, topo.objects.states);
    var proj = d3.geoAlbers().rotate([88, 0]).parallels([29.5, 45.5]).fitExtent([[6, 6], [W - 6, H - 6]], counties);
    var path = d3.geoPath(proj);
    var svg = d3.select(root.querySelector(".storm-map-svg")).append("svg")
      .attr("viewBox", "0 0 " + W + " " + H).attr("class", "chart-svg").attr("role", "img")
      .attr("aria-labelledby", "storm-map-title storm-map-desc");
    svg.append("title").attr("id", "storm-map-title").text("Share of cell sites out by county, one FCC report at a time");
    svg.append("desc").attr("id", "storm-map-desc").text("A map of the ten study states. Counties are shaded darker " +
      "where a larger share of cell sites was out in the chosen report; counties not in the report are hatched light " +
      "grey, and counties in the report with no sites out have a faint tint. The " +
      "status line above the map and the table below give the same information as text.");
    var pat = svg.append("defs").append("pattern").attr("id", "storm-map-nr").attr("patternUnits", "userSpaceOnUse")
      .attr("width", 4).attr("height", 4).attr("patternTransform", "rotate(45)");
    pat.append("rect").attr("width", 4).attr("height", 4).attr("fill", NR_BG);
    pat.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 4).attr("stroke", NR_LINE).attr("stroke-width", 0.9);
    counties.features.forEach(function (f) { names[f.id] = f.properties.name + ", " + f.properties.state; });
    paths = svg.append("g").selectAll("path").data(counties.features).join("path")
      .attr("d", path).attr("stroke", PAPER).attr("stroke-width", 0.4)
      .on("pointerenter pointermove pointerdown", function (ev, f) { showTip(ev, f); })
      .on("pointerleave", function () { tip.hidden = true; });
    svg.append("path").datum(states).attr("d", path).attr("fill", "none").attr("stroke", MUTED).attr("stroke-width", 0.9)
      .attr("pointer-events", "none");
    var lg = document.createElement("div");  // HTML legend: keeps its text size on a phone
    lg.className = "storm-map-legend";
    var cap = document.createElement("span"); cap.textContent = "% of sites out:"; lg.appendChild(cap);
    SCALE.legend.forEach(function (t) {
      var item = document.createElement("span"), sw = document.createElement("span");
      sw.className = "storm-map-swatch"; sw.style.background = "rgba(15, 35, 56, " + shade(t[0]).toFixed(3) + ")";
      item.appendChild(sw); item.appendChild(document.createTextNode(t[1])); lg.appendChild(item);
    });
    var nr = document.createElement("span"), nsw = document.createElement("span");
    nsw.className = "storm-map-swatch storm-map-swatch-none";
    nr.appendChild(nsw); nr.appendChild(document.createTextNode("not in this report")); lg.appendChild(nr);
    root.querySelector(".storm-map-figure").appendChild(lg);
  }

  function report() { return storm.reports[+slider.value]; }

  function render() {
    var r = report(), c = r.counties;
    paths.attr("fill", function (f) { return c[f.id] ? INK : "url(#storm-map-nr)"; })
      .attr("fill-opacity", function (f) { return c[f.id] ? shade(c[f.id][0]) : 1; })
      .attr("stroke", function (f) { return c[f.id] ? PAPER : RULE; });
    var keys = Object.keys(c), out = 0, served = 0;
    keys.forEach(function (k) { out += c[k][1]; served += c[k][2]; });
    var label = r.date + " (day " + fmt(r.day, 1) + " since 34-kt winds arrived)";
    slider.setAttribute("aria-valuetext", "Report " + (+slider.value + 1) + " of " + storm.reports.length + ": " + label);
    status.textContent = storm.name + ", report " + (+slider.value + 1) + " of " + storm.reports.length + ", " + label +
      ": " + n0(out) + " of " + n0(served) + " cell sites out (" + fmt(served ? 100 * out / served : 0, 1) +
      "%) in the " + keys.length + " counties in this report.";
    table(c);
  }

  function table(c) {
    var t = document.createElement("table");
    var head = ["County", "% of sites out", "Sites out", "Sites served", "Damage %", "Transport %", "Power %"];
    var tr = t.createTHead().insertRow();
    head.forEach(function (h) { var th = document.createElement("th"); th.scope = "col"; th.textContent = h; tr.appendChild(th); });
    var tb = t.createTBody();
    Object.keys(c).sort(function (a, b) { return c[b][0] - c[a][0] || (names[a] || a).localeCompare(names[b] || b); })
      .forEach(function (k) {
        var v = c[k], row = tb.insertRow(), cz = v[3] || ["", "", ""];
        [names[k] || k, fmt(v[0], 1), v[1], v[2], cz[0], cz[1], cz[2]].forEach(function (x) { row.insertCell().textContent = x; });
      });
    tableBox.textContent = "";
    tableBox.appendChild(t);
  }

  function showTip(ev, f) {
    var v = report().counties[f.id], lines = [names[f.id] || f.id];
    if (!v) lines.push("not in this report");
    else {
      lines.push(fmt(v[0], 1) + "% of cell sites out (" + n0(v[1]) + " of " + n0(v[2]) + ")");
      if (v[3]) lines.push("of sites out: damage " + v[3][0] + "%, transport " + v[3][1] + "%, power " + v[3][2] + "%");
      else if (v[1] > 0) lines.push("causes not given in this report");
    }
    tip.textContent = "";
    lines.forEach(function (l, i) { var d = document.createElement(i ? "div" : "strong"); d.textContent = l; tip.appendChild(d); });
    var box = root.querySelector(".storm-map-figure").getBoundingClientRect();
    var x = ev.clientX - box.left + 12, y = ev.clientY - box.top + 12;
    tip.style.left = Math.min(x, box.width - 230) + "px";
    tip.style.top = y + "px";
    tip.hidden = false;
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null; play.setAttribute("aria-pressed", "false"); play.textContent = "Play";
  }

  function chooseStorm() {
    stop();
    storm = data.storms.filter(function (s) { return s.key === stormSel.value; })[0];
    slider.max = storm.reports.length - 1; slider.value = 0;
    render();
  }

  Promise.all([fetch(root.getAttribute("data-topo")).then(function (r) { return r.json(); }),
               fetch(root.getAttribute("data-src")).then(function (r) { return r.json(); })])
    .then(function (res) {
      data = res[1];
      draw(res[0]);
      stormSel.textContent = "";
      data.storms.forEach(function (s) {
        var o = document.createElement("option");
        o.value = s.key; o.textContent = s.name + " (" + s.period + ", " + s.reports[0].date.slice(0, 4) + ")";
        stormSel.appendChild(o);
      });
      [stormSel, slider, play].forEach(function (e) { e.disabled = false; });
      stormSel.addEventListener("change", chooseStorm);
      slider.addEventListener("input", function () { stop(); render(); });
      play.addEventListener("click", function () {
        if (timer) { stop(); return; }
        if (+slider.value >= +slider.max) slider.value = 0;
        play.setAttribute("aria-pressed", "true"); play.textContent = "Pause";
        timer = setInterval(function () {
          if (+slider.value >= +slider.max) { stop(); return; }
          slider.value = +slider.value + 1; render();
        }, 1200);
      });
      chooseStorm();
    })
    .catch(function () {
      status.textContent = "The map data could not be loaded. The same data is in the published county-report panel (CSV).";
    });
})();
