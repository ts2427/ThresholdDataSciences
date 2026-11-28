/* Collapsed sections and tabs on analysis pages.
   2026-11-25: a link or URL pointing inside a closed <details> opens it (and any closed sections around it) and
   scrolls there; printing opens every section; choosing an entry in the phone menu closes the menu.
   2026-11-28: on a tabbed page each tab is a <section class="tab-panel"> with its own id. This script shows the tab
   bar, shows one section at a time, keeps the URL's hash in step (so a tab or any anchor in it can be linked,
   bookmarked and reached with the back button), and follows the WAI-ARIA tabs pattern: arrow keys, Home and End move
   between tabs, the selected tab has aria-selected="true" and is the only one in the tab order.
   Without JavaScript the page still works: every section shows in order under the table of contents, every section
   can be opened by hand, and the navigation links lead to visible headings. */
(function () {
  "use strict";

  var bar = document.querySelector('.tab-bar[role="tablist"]');
  var tabs = bar ? Array.prototype.slice.call(bar.querySelectorAll('[role="tab"]')) : [];
  var panels = tabs.map(function (t) { return document.getElementById(t.getAttribute("aria-controls")); });

  function openAround(el) {
    var d = el.closest("details");
    while (d) {
      d.open = true;
      d = d.parentElement ? d.parentElement.closest("details") : null;
    }
  }

  function panelOf(el) {
    return el && el.closest ? el.closest(".tab-panel") : null;
  }

  function select(panelId, focus) {
    if (!tabs.length) return;
    tabs.forEach(function (t, i) {
      var on = t.getAttribute("aria-controls") === panelId;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      panels[i].hidden = !on;
      if (on && focus) t.focus();
    });
  }

  function idFromHash() {
    try { return decodeURIComponent(location.hash.slice(1)); } catch (e) { return location.hash.slice(1); }
  }

  // Show what an id points at: its tab, and any closed sections around it. Returns the element, if any.
  function reveal(id) {
    var el = id ? document.getElementById(id) : null;
    if (!el) return null;
    var p = panelOf(el);
    if (p) select(p.id, false);
    if (el.closest("details:not([open])")) openAround(el);
    return el;
  }

  function fromHash() {
    var el = reveal(idFromHash());
    if (!el && tabs.length) select(panels[0].id, false);  // no hash, or an unknown one: the first tab
    if (el) el.scrollIntoView();
  }

  if (tabs.length) {
    bar.hidden = false;
    document.documentElement.classList.add("has-tabs");
    panels.forEach(function (p, i) {
      p.setAttribute("role", "tabpanel");
      p.setAttribute("aria-labelledby", tabs[i].id);  // not focusable itself: every panel holds links (WAI-ARIA tabs)
    });

    function activate(i, how) {
      var id = panels[i].id;
      select(id, true);
      if (how === "push") history.pushState(null, "", "#" + id);
      else history.replaceState(null, "", "#" + id);
      var top = bar.getBoundingClientRect().top;
      if (top < 0) bar.scrollIntoView();
    }

    bar.addEventListener("click", function (ev) {
      var t = ev.target.closest('[role="tab"]');
      if (t) activate(tabs.indexOf(t), "push");
    });
    bar.addEventListener("keydown", function (ev) {
      var i = tabs.indexOf(document.activeElement);
      if (i < 0) return;
      var n = tabs.length, j = null;
      if (ev.key === "ArrowRight") j = (i + 1) % n;
      else if (ev.key === "ArrowLeft") j = (i - 1 + n) % n;
      else if (ev.key === "Home") j = 0;
      else if (ev.key === "End") j = n - 1;
      if (j === null) return;
      ev.preventDefault();
      activate(j, "replace");
    });
    window.addEventListener("popstate", fromHash);  // back and forward
  }

  // Same-page links: show the target's tab and open its sections before the browser scrolls.
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest ? ev.target.closest('a[href^="#"]') : null;
    if (!a) return;
    reveal(a.getAttribute("href").slice(1));
    var menu = a.closest(".toc-mobile");
    if (menu) menu.open = false;
  });

  window.addEventListener("hashchange", fromHash);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fromHash);
  } else {
    fromHash();
  }

  // Print opens every collapsed section, and restores what was closed afterwards. On a tabbed page the selected tab
  // prints; without JavaScript every tab prints.
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
