/*
 * fmn-trust.js — FindMyNyumba Trust & Safety frontend kit
 * ---------------------------------------------------------------------------
 * Drop-in, dependency-free (uses Tailwind classes already on the site +
 * FontAwesome which is already loaded). Add ONE line to any page:
 *
 *     <script src="assets/fmn-trust.js" data-page="home"></script>
 *
 * data-page is one of:
 *     home | listings | property | dashboard_student | dashboard_landlord
 * (defaults to "all" if omitted).
 *
 * What it does
 * ------------
 * 1. Trust banner strip: fetches active banners for the page, rotates every
 *    5s, is dismissible, and stays dismissed for 24h (localStorage), then
 *    reappears. Fully responsive. Injects itself just below a fixed <nav>.
 * 2. Badge rendering: call FMNTrust.badgeForUser(id) / badgeForListing(id),
 *    or auto-hydrate any element with data-fmn-badge-user / -listing.
 *
 * Brand tokens reused: navy #0f172a, green #16a34a.
 */
(function () {
  "use strict";

  // ── API base: mirror the convention used across the site ──────────────────
  var local =
    location.hostname === "localhost" || location.hostname === "127.0.0.1";
  var API_BASE =
    (local ? "http://localhost:8000" : "https://findmynyumba.onrender.com") +
    "/api/v1";

  var script = document.currentScript;
  var PAGE = (script && script.getAttribute("data-page")) || "all";
  var ROTATE_MS = 5000;
  var DISMISS_HOURS = 24;
  var DISMISS_KEY = "fmn_trust_banner_dismissed_at";

  // ── Small helpers ─────────────────────────────────────────────────────────
  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return {
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
      }[c];
    });
  }
  function dismissedRecently() {
    try {
      var t = parseInt(localStorage.getItem(DISMISS_KEY) || "0", 10);
      return Date.now() - t < DISMISS_HOURS * 3600 * 1000;
    } catch (e) {
      return false;
    }
  }
  function markDismissed() {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch (e) {}
  }

  var DOT = { info: "#16a34a", success: "#16a34a", warning: "#16a34a" };

  // ── Trust banner strip ────────────────────────────────────────────────────
  function buildBanner(banners) {
    if (!banners || !banners.length || dismissedRecently()) return;

    var bar = el(
      "div",
      "fmn-trust-bar",
      ""
    );
    // Inline styles so the strip looks right even on pages without extra CSS.
    bar.style.cssText =
      "background:#0f172a;color:#fff;font-size:14px;line-height:1.3;" +
      "width:100%;z-index:40;";
    bar.setAttribute("role", "region");
    bar.setAttribute("aria-label", "Safety notice");

    var inner = el("div");
    inner.style.cssText =
      "max-width:1152px;margin:0 auto;display:flex;align-items:center;gap:12px;" +
      "padding:10px 16px;";

    var dot = el("span");
    dot.style.cssText =
      "flex:0 0 auto;width:9px;height:9px;border-radius:9999px;background:#16a34a;" +
      "box-shadow:0 0 0 4px rgba(22,163,74,.18);";

    var msg = el("span", "fmn-trust-msg");
    msg.style.cssText =
      "flex:1 1 auto;font-weight:600;letter-spacing:.1px;" +
      "transition:opacity .35s ease;";

    var report = el(
      "a",
      "fmn-trust-report",
      '<i class="fas fa-flag" style="margin-right:6px"></i>Report'
    );
    report.href = "safety.html#report";
    report.style.cssText =
      "flex:0 0 auto;color:#bbf7d0;font-weight:700;text-decoration:none;" +
      "font-size:13px;white-space:nowrap;";

    var close = el("button", null, '<i class="fas fa-times"></i>');
    close.setAttribute("aria-label", "Dismiss safety notice");
    close.style.cssText =
      "flex:0 0 auto;background:transparent;border:0;color:#94a3b8;cursor:pointer;" +
      "font-size:15px;padding:4px;line-height:1;";
    close.addEventListener("click", function () {
      markDismissed();
      bar.style.transition = "opacity .25s ease, max-height .25s ease";
      bar.style.overflow = "hidden";
      bar.style.opacity = "0";
      bar.style.maxHeight = "0";
      setTimeout(function () {
        if (bar.parentNode) bar.parentNode.removeChild(bar);
      }, 260);
      clearInterval(timer);
    });

    inner.appendChild(dot);
    inner.appendChild(msg);
    inner.appendChild(report);
    inner.appendChild(close);
    bar.appendChild(inner);

    // Place it directly under a fixed nav if present, else at top of body.
    var nav = document.querySelector("nav");
    var navFixed =
      nav && getComputedStyle(nav).position === "fixed";
    if (navFixed) {
      // Push the bar below the nav so it doesn't hide under it.
      bar.style.position = "relative";
      var navH = nav.getBoundingClientRect().height || 64;
      var spacer = el("div");
      spacer.style.height = navH + "px";
      spacer.className = "fmn-trust-spacer";
      document.body.insertBefore(spacer, document.body.firstChild);
      document.body.insertBefore(bar, spacer.nextSibling);
    } else {
      document.body.insertBefore(bar, document.body.firstChild);
    }

    // Rotation
    var i = 0;
    function show(n) {
      var b = banners[n % banners.length];
      var icon = b.icon ? escapeHtml(b.icon) + " " : "";
      msg.style.opacity = "0";
      setTimeout(function () {
        msg.innerHTML = icon + escapeHtml(b.message);
        dot.style.background = DOT[b.level] || "#16a34a";
        msg.style.opacity = "1";
      }, 180);
    }
    show(0);
    var timer = null;
    if (banners.length > 1) {
      timer = setInterval(function () {
        i += 1;
        show(i);
      }, ROTATE_MS);
      // Pause rotation on hover for readability.
      bar.addEventListener("mouseenter", function () {
        clearInterval(timer);
      });
      bar.addEventListener("mouseleave", function () {
        timer = setInterval(function () {
          i += 1;
          show(i);
        }, ROTATE_MS);
      });
    }
  }

  function loadBanners() {
    fetch(API_BASE + "/trust/banners?page=" + encodeURIComponent(PAGE))
      .then(function (r) {
        return r.ok ? r.json() : [];
      })
      .then(buildBanner)
      .catch(function () {
        /* network down: stay silent, never block the page */
      });
  }

  // ── Badges ────────────────────────────────────────────────────────────────
  var BADGE_STYLE = {
    green: { bg: "#dcfce7", fg: "#166534", icon: "fa-circle-check" },
    yellow: { bg: "#fef9c3", fg: "#854d0e", icon: "fa-clock" },
    red: { bg: "#fee2e2", fg: "#991b1b", icon: "fa-triangle-exclamation" },
  };

  function badgeHtml(badge) {
    var s = BADGE_STYLE[badge.level] || BADGE_STYLE.red;
    return (
      '<span class="fmn-badge" title="' +
      escapeHtml(badge.label) +
      '" style="display:inline-flex;align-items:center;gap:5px;' +
      "padding:3px 9px;border-radius:9999px;font-size:12px;font-weight:700;" +
      "background:" +
      s.bg +
      ";color:" +
      s.fg +
      ';white-space:nowrap;">' +
      '<i class="fas ' +
      s.icon +
      '"></i>' +
      escapeHtml(badge.label) +
      "</span>"
    );
  }

  function fetchBadge(kind, id) {
    return fetch(API_BASE + "/trust/badges/" + kind + "/" + id)
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .catch(function () {
        return null;
      });
  }

  function hydrateBadges() {
    document
      .querySelectorAll("[data-fmn-badge-user],[data-fmn-badge-listing]")
      .forEach(function (node) {
        var userId = node.getAttribute("data-fmn-badge-user");
        var listingId = node.getAttribute("data-fmn-badge-listing");
        var kind = userId ? "user" : "listing";
        var id = userId || listingId;
        if (!id) return;
        fetchBadge(kind, id).then(function (badge) {
          if (badge) node.innerHTML = badgeHtml(badge);
        });
      });
  }

  // Public API for pages that render cards dynamically.
  window.FMNTrust = {
    badgeHtml: badgeHtml,
    badgeForUser: function (id) {
      return fetchBadge("user", id);
    },
    badgeForListing: function (id) {
      return fetchBadge("listing", id);
    },
    hydrateBadges: hydrateBadges,
    apiBase: API_BASE,
  };

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    loadBanners();
    hydrateBadges();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
