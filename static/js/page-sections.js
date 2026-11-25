/* Collapsed sections on analysis pages (2026-11-25).
   A link or URL pointing inside a closed <details> opens it (and any closed sections around it) and scrolls there;
   printing opens every section; choosing an entry in the phone menu closes the menu. Without JavaScript the page
   still works: every section can be opened by hand, and the navigation links still lead to visible headings. */
(function () {
  "use strict";

  function openAround(el) {
    var d = el.closest("details");
    while (d) {
      d.open = true;
      d = d.parentElement ? d.parentElement.closest("details") : null;
    }
  }

  function reveal(id, scroll) {
    if (!id) return;
    var el = document.getElementById(id);
    if (!el || !el.closest("details:not([open])")) return;
    openAround(el);
    if (scroll) el.scrollIntoView();
  }

  function fromHash() {
    var id = "";
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { id = location.hash.slice(1); }
    reveal(id, true);
  }

  // Same-page links: open the target before the browser scrolls (no hashchange fires when the hash is unchanged).
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest ? ev.target.closest('a[href^="#"]') : null;
    if (!a) return;
    var id = a.getAttribute("href").slice(1);
    reveal(id, false);
    var menu = a.closest(".toc-mobile");
    if (menu) menu.open = false;
  });

  window.addEventListener("hashchange", fromHash);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fromHash);
  } else {
    fromHash();
  }

  // Print opens everything, and restores what was closed afterwards.
  var opened = [];
  window.addEventListener("beforeprint", function () {
    opened = Array.prototype.slice.call(document.querySelectorAll("details:not([open])"));
    opened.forEach(function (d) { d.open = true; });
  });
  window.addEventListener("afterprint", function () {
    opened.forEach(function (d) { d.open = false; });
    opened = [];
  });
})();
