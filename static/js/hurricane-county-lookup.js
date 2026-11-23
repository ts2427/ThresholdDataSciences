/* County lookup for "When the Network Goes Dark" (version 2).
   Reads /static/data/hurricane-county-lookup.json (generated from the published county-report panel) from this
   site only; no other server is contacted. One small chart per storm: % of the county's cell sites out in each FCC
   report, by days since the storm's 34-knot winds first reached a study-state county. Points are reports; a line joins
   two points only when no report of that storm falls between them. */
(function () {
  "use strict";
  var root = document.querySelector(".county-lookup");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var select = root.querySelector("select");
  var status = root.querySelector(".county-lookup-status");
  var panels = root.querySelector(".county-lookup-panels");
  var tableBox = root.querySelector(".county-lookup-table");
  var data = null;

  function el(name, attrs, text) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function fmt(x, d) { return Number(x).toFixed(d); }

  function chart(storm, pts, ymax) {
    var W = 300, H = 150, L = 34, R = 10, T = 12, B = 26;
    var days = storm.report_days;
    var x0 = Math.min(0, days[0]), x1 = Math.max(days[days.length - 1], x0 + 1);
    function X(v) { return L + (W - L - R) * (v - x0) / (x1 - x0); }
    function Y(v) { return T + (H - T - B) * (1 - v / ymax); }
    var peak = pts.reduce(function (a, p) { return p[1] > a[1] ? p : a; }, pts[0]);
    var last = pts[pts.length - 1];
    var label = storm.name + ": " + pts.length + " report" + (pts.length > 1 ? "s" : "") + "; highest " +
      fmt(peak[1], 1) + "% of sites out on day " + fmt(peak[0], 1) + "; last report day " + fmt(last[0], 1) +
      ", " + fmt(last[1], 1) + "% out.";
    var svg = el("svg", {viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": label, "class": "chart-svg"});
    [0, ymax / 2, ymax].forEach(function (t) {
      svg.appendChild(el("line", {x1: L, x2: W - R, y1: Y(t), y2: Y(t), stroke: "#C9D1D8", "stroke-width": 1}));
      svg.appendChild(el("text", {x: L - 4, y: Y(t) + 3, "text-anchor": "end", "font-size": 10, fill: "#51626F"},
                         fmt(t, 0) + "%"));
    });
    if (x0 < 0) svg.appendChild(el("line", {x1: X(0), x2: X(0), y1: T, y2: H - B, stroke: "#C9D1D8",
                                            "stroke-dasharray": "3 3"}));
    svg.appendChild(el("text", {x: L, y: H - 8, "font-size": 10, fill: "#51626F"}, "day " + fmt(x0, 0)));
    svg.appendChild(el("text", {x: W - R, y: H - 8, "font-size": 10, fill: "#51626F", "text-anchor": "end"},
                       "day " + fmt(x1, 0)));
    for (var i = 1; i < pts.length; i++) {
      var a = pts[i - 1][0], b = pts[i][0];
      var between = days.some(function (d) { return d > a && d < b; });
      if (!between) svg.appendChild(el("line", {x1: X(a), y1: Y(pts[i - 1][1]), x2: X(b), y2: Y(pts[i][1]),
                                                 stroke: "#0F2338", "stroke-width": 2}));
    }
    pts.forEach(function (p) {
      svg.appendChild(el("circle", {cx: X(p[0]), cy: Y(p[1]), r: 3, fill: "#0F2338"}));
    });
    return svg;
  }

  function show(fips) {
    panels.textContent = ""; tableBox.textContent = ""; status.textContent = "";
    if (!fips) return;
    var c = data.counties.filter(function (x) { return x.fips === fips; })[0];
    var storms = data.storms.filter(function (s) { return c.series[s.key]; });
    var all = []; storms.forEach(function (s) { all = all.concat(c.series[s.key]); });
    var ymax = Math.max(10, Math.ceil(Math.max.apply(null, all.map(function (p) { return p[1]; })) / 10) * 10);
    storms.forEach(function (s) {
      var fig = document.createElement("figure");
      fig.className = "county-lookup-panel";
      var cap = document.createElement("figcaption");
      cap.textContent = s.name + " (" + s.period + ")";
      fig.appendChild(cap);
      fig.appendChild(chart(s, c.series[s.key], ymax));
      panels.appendChild(fig);
    });
    var t = document.createElement("table");
    var head = ["Storm", "Report date", "Days since 34-kt winds arrived", "Sites out", "Sites served", "% out"];
    var thead = t.createTHead().insertRow();
    head.forEach(function (h) { var th = document.createElement("th"); th.scope = "col"; th.textContent = h; thead.appendChild(th); });
    var tb = t.createTBody();
    storms.forEach(function (s) {
      c.series[s.key].forEach(function (p) {
        var row = tb.insertRow();
        [s.name, p[4], fmt(p[0], 1), p[2], p[3], fmt(p[1], 1)].forEach(function (v) { row.insertCell().textContent = v; });
      });
    });
    tableBox.appendChild(t);
    status.textContent = c.county + ", " + c.abbr + ": " + storms.length + " storm" + (storms.length > 1 ? "s" : "") +
      ", " + all.length + " report" + (all.length > 1 ? "s" : "") + ".";
  }

  fetch(root.getAttribute("data-src")).then(function (r) { return r.json(); }).then(function (d) {
    data = d;
    select.textContent = "";
    var blank = document.createElement("option");
    blank.value = ""; blank.textContent = "Choose a county (" + d.counties.length + ")";
    select.appendChild(blank);
    var groups = {};
    d.counties.forEach(function (c) {
      if (!groups[c.state]) {
        groups[c.state] = document.createElement("optgroup");
        groups[c.state].label = c.state;
        select.appendChild(groups[c.state]);
      }
      var o = document.createElement("option");
      o.value = c.fips; o.textContent = c.county + ", " + c.abbr;
      groups[c.state].appendChild(o);
    });
    select.disabled = false;
    select.addEventListener("change", function () { show(select.value); });
  }).catch(function () {
    status.textContent = "The county data could not be loaded. It is also in the published county-report panel (CSV).";
  });
})();
