/* tos-toolkit docs — progressive enhancement only. Every page reads fully
 * without this file; it adds the theme toggle, the mobile contents drawer,
 * copy buttons, and keyboard-first search over /search.json. */
(function () {
  "use strict";

  var doc = document.documentElement;
  // Only now is it safe to hide the mobile nav behind a toggle: this class is
  // set by the script that also wires the toggle, so a failed load leaves the
  // nav visible instead of unreachable.
  doc.classList.remove("no-js");
  doc.classList.add("js", "nav-js");
  var root = document.body.getAttribute("data-root") || "./";

  /* ---------------------------------------------------------- theme -- */
  var toggle = document.querySelector(".theme-toggle");
  var darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

  function effectiveTheme() {
    return doc.getAttribute("data-theme") || (darkQuery.matches ? "dark" : "light");
  }
  function labelTheme() {
    var next = effectiveTheme() === "dark" ? "light" : "dark";
    toggle.setAttribute("aria-label", "Switch to " + next + " theme");
    toggle.title = "Switch to " + next + " theme";
  }
  if (toggle) {
    labelTheme();
    toggle.addEventListener("click", function () {
      var next = effectiveTheme() === "dark" ? "light" : "dark";
      doc.setAttribute("data-theme", next);
      try { localStorage.setItem("tos-theme", next); } catch (e) { /* private mode */ }
      labelTheme();
    });
    darkQuery.addEventListener("change", labelTheme);
  }

  /* --------------------------------------------------- contents drawer -- */
  var menu = document.querySelector(".menu-toggle");
  function setMenu(open) {
    doc.classList.toggle("nav-open", open);
    menu.setAttribute("aria-expanded", String(open));
  }
  if (menu) {
    menu.addEventListener("click", function () {
      var open = !doc.classList.contains("nav-open");
      setMenu(open);
      if (open) {
        var first = document.querySelector("#sidebar a");
        if (first) first.focus();
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && doc.classList.contains("nav-open")) {
        setMenu(false);
        menu.focus();
      }
    });
  }

  /* ----------------------------------------------------- copy buttons -- */
  var copyStatus = document.getElementById("q-status");
  document.querySelectorAll(".code:not(.code-figure)").forEach(function (block) {
    var pre = block.querySelector("pre");
    if (!pre || !navigator.clipboard) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy";
    btn.textContent = "Copy";
    btn.setAttribute("aria-label", "Copy code to clipboard");
    btn.addEventListener("click", function () {
      var text = pre.innerText;
      // For terminal transcripts, copy only the commands, not the prompts or output.
      if (block.getAttribute("data-lang") === "console") {
        text = text.split("\n").filter(function (l) { return /^\$ /.test(l); })
          .map(function (l) { return l.slice(2); }).join("\n") || text;
      }
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = "Copied";
        btn.setAttribute("data-done", "");
        if (copyStatus) copyStatus.textContent = "Copied to clipboard";
        setTimeout(function () { btn.textContent = "Copy"; btn.removeAttribute("data-done"); }, 1600);
      });
    });
    block.appendChild(btn);
  });

  /* ------------------------------------------------------------ search -- */
  var input = document.getElementById("q");
  var list = document.getElementById("q-results");
  var status = document.getElementById("q-status");
  if (!input || !list) return;

  var index = null;
  var loading = null;
  var results = [];
  var active = -1;

  function load() {
    if (!loading) {
      loading = fetch(root + "search.json")
        .then(function (r) { return r.json(); })
        .then(function (data) { index = data; return data; })
        .catch(function () { index = []; });
    }
    return loading;
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

  // Split on the raw text first, then escape each piece. Escaping first and
  // highlighting afterwards lets a query like "amp" match inside "&amp;".
  function markTerms(text, terms) {
    if (!terms.length) return escapeHtml(text);
    var re = new RegExp("(" + terms.map(escapeRe).join("|") + ")", "gi");
    var out = "";
    var last = 0;
    var m;
    while ((m = re.exec(text)) !== null) {
      out += escapeHtml(text.slice(last, m.index)) + "<mark>" + escapeHtml(m[0]) + "</mark>";
      last = m.index + m[0].length;
      if (m[0].length === 0) re.lastIndex++;
    }
    return out + escapeHtml(text.slice(last));
  }

  function snippet(text, terms) {
    var lower = text.toLowerCase();
    var at = -1;
    for (var i = 0; i < terms.length && at < 0; i++) at = lower.indexOf(terms[i]);
    if (at < 0) at = 0;
    var start = Math.max(0, at - 60);
    var cut = text.slice(start, start + 170);
    return (start > 0 ? "… " : "") + cut + (start + 170 < text.length ? " …" : "");
  }

  function score(entry, q, terms) {
    var h = entry.h.toLowerCase();
    var p = entry.p.toLowerCase();
    var x = entry.x.toLowerCase();
    var hay = h + " " + p + " " + x;
    for (var i = 0; i < terms.length; i++) if (hay.indexOf(terms[i]) < 0) return 0;
    var s = 1;
    if (entry.c && h === q) s += 1000;          // exact diagnostic code
    if (h === q) s += 200;
    if (h.indexOf(q) === 0) s += 60;
    else if (h.indexOf(q) >= 0) s += 30;
    if (p.indexOf(q) >= 0) s += 15;
    for (var j = 0; j < terms.length; j++) {
      if (h.indexOf(terms[j]) >= 0) s += 8;
      if (x.indexOf(terms[j]) >= 0) s += 2;
    }
    if (entry.c) s += 5;
    return s;
  }

  function open(isOpen) {
    list.hidden = !isOpen;
    input.setAttribute("aria-expanded", String(isOpen));
    if (!isOpen) { input.removeAttribute("aria-activedescendant"); active = -1; }
  }

  function setActive(i) {
    var items = list.querySelectorAll("[role=option]");
    if (!items.length) return;
    active = (i + items.length) % items.length;
    items.forEach(function (el, n) { el.setAttribute("aria-selected", String(n === active)); });
    input.setAttribute("aria-activedescendant", items[active].id);
    items[active].scrollIntoView({ block: "nearest" });
  }

  function go(entry) {
    open(false);
    window.location.href = root + entry.u;
  }

  function run() {
    var q = input.value.trim().toLowerCase();
    if (!q) { list.innerHTML = ""; open(false); status.textContent = ""; return; }
    var terms = q.split(/\s+/).filter(Boolean);
    results = (index || [])
      .map(function (e) { return { e: e, s: score(e, q, terms) }; })
      .filter(function (r) { return r.s > 0; })
      .sort(function (a, b) { return b.s - a.s; })
      .slice(0, 12)
      .map(function (r) { return r.e; });

    if (!results.length) {
      list.innerHTML = '<li class="r-empty" role="presentation">No matches for “' + escapeHtml(q) + "”</li>";
      status.textContent = "No results";
      open(true);
      return;
    }
    list.innerHTML = results.map(function (e, i) {
      var title = e.h || e.p;
      var where = e.c ? "Rule · " + e.p : (e.h ? e.p : "Page");
      return '<li role="option" id="q-opt-' + i + '" aria-selected="false">' +
        '<span class="r-where">' + escapeHtml(where) + "</span>" +
        '<span class="r-title">' + markTerms(title, terms) + "</span>" +
        (e.x ? '<span class="r-snip">' + markTerms(snippet(e.x, terms), terms) + "</span>" : "") +
        "</li>";
    }).join("");
    status.textContent = results.length + " result" + (results.length === 1 ? "" : "s") +
      ". Use up and down arrows to review, Enter to open.";
    open(true);
    setActive(0);
  }

  input.addEventListener("focus", function () {
    load().catch(function () {
      status.textContent = "Search index could not be loaded. Use the sidebar navigation.";
    });
  });
  input.addEventListener("input", function () {
    if (index) run(); else load().then(run);
  });
  input.addEventListener("keydown", function (e) {
    // The list may be closed (after Escape) while `active` still points at a
    // result. Never move through, or navigate to, an invisible row.
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (list.hidden) run(); else setActive(active + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (list.hidden) run(); else setActive(active - 1);
    } else if (e.key === "Enter") {
      if (!list.hidden && active >= 0 && results[active]) {
        e.preventDefault(); go(results[active]);
      }
    } else if (e.key === "Escape") {
      if (!list.hidden) { e.preventDefault(); e.stopPropagation(); open(false); }
      else if (input.value) { input.value = ""; }
      else { input.blur(); }
    }
  });
  list.addEventListener("mousedown", function (e) { e.preventDefault(); }); // keep focus in input
  list.addEventListener("click", function (e) {
    var li = e.target.closest("[role=option]");
    if (li) go(results[Number(li.id.slice(6))]);
  });
  input.addEventListener("blur", function () { setTimeout(function () { open(false); }, 0); });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
    var t = e.target;
    if (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    e.preventDefault();
    input.focus();
    input.select();
  });
})();
