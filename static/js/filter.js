// Category filter for the Threshold Effects archive.
// Injected entirely by JS: with JS disabled the full archive simply renders,
// which is the graceful degradation the design requires.
(function () {
  var slot = document.getElementById("filter-slot");
  if (!slot || !slot.dataset.categories) return;
  var cats = slot.dataset.categories.split("|").filter(Boolean);
  if (cats.length < 2) return;

  var rows = document.querySelectorAll(".issue-row[data-category]");
  var bar = document.createElement("div");
  bar.className = "filter-bar";
  bar.setAttribute("role", "group");
  bar.setAttribute("aria-label", "Filter issues by category");

  function makeButton(label, value) {
    var b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.setAttribute("aria-pressed", value === "" ? "true" : "false");
    b.addEventListener("click", function () {
      bar.querySelectorAll("button").forEach(function (o) {
        o.setAttribute("aria-pressed", "false");
      });
      b.setAttribute("aria-pressed", "true");
      rows.forEach(function (r) {
        r.hidden = value !== "" && r.dataset.category !== value;
      });
    });
    return b;
  }

  bar.appendChild(makeButton("All", ""));
  cats.forEach(function (c) { bar.appendChild(makeButton(c, c)); });
  slot.appendChild(bar);
})();
