/* ============================================================
   FindMyNyumba - Listing detail gate (teaser)
   Logged-out visitors see the photos + title, but the details are blurred
   behind a "sign in to view" overlay. Any logged-in account unlocks it.

   SOFT gate (signup nudge), not security: contact info is separately
   protected server-side (masked phone until paid), so this never weakens
   real protection - it only encourages sign-up.

   Install: add ONE line before </body> in listing.html:
     <script src="fmn-listing-gate.js"></script>
============================================================= */
(function () {
  'use strict';

  function getToken() {
    try { return localStorage.getItem('token') || sessionStorage.getItem('token'); }
    catch (e) { return null; }
  }

  // logged in -> do nothing at all
  if (getToken()) return;

  function injectCss() {
    if (document.getElementById('fmnlg-style')) return;
    var css = [
      ".fmnlg-blur{filter:blur(6px);pointer-events:none;user-select:none;transition:filter .2s}",
      ".fmnlg-overlay{position:fixed;left:0;right:0;bottom:0;top:0;display:flex;align-items:center;justify-content:center;z-index:9998;padding:20px;pointer-events:none}",
      ".fmnlg-card{pointer-events:auto;background:#fff;border-radius:18px;box-shadow:0 25px 60px -12px rgba(0,0,0,.35);max-width:380px;width:100%;padding:28px 26px;text-align:center;border:1px solid #f1f5f9}",
      ".fmnlg-ic{width:56px;height:56px;border-radius:50%;background:#fff7ed;display:flex;align-items:center;justify-content:center;margin:0 auto 14px}",
      ".fmnlg-ic i{color:#ea580c;font-size:22px}",
      ".fmnlg-card h3{font-size:18px;font-weight:800;color:#0f172a;margin:0 0 6px}",
      ".fmnlg-card p{font-size:13px;color:#64748b;line-height:1.55;margin:0 0 18px}",
      ".fmnlg-btns{display:flex;flex-direction:column;gap:9px}",
      ".fmnlg-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font-weight:700;border-radius:12px;font-size:13.5px;padding:12px 16px;cursor:pointer;text-decoration:none;font-family:inherit;border:none}",
      ".fmnlg-primary{background:#ea580c;color:#fff}.fmnlg-primary:hover{background:#c2410c}",
      ".fmnlg-ghost{background:#fff;color:#334155;border:1.5px solid #e2e8f0}.fmnlg-ghost:hover{background:#f8fafc}",
      ".fmnlg-note{margin-top:14px;font-size:11px;color:#94a3b8}"
    ].join("");
    var s = document.createElement('style');
    s.id = 'fmnlg-style';
    s.textContent = css;
    document.head.appendChild(s);
  }

  function apply(tries) {
    // the main grid is the first grid container after the nav
    var grid = document.querySelector('.grid.lg\\:grid-cols-12') ||
               document.querySelector('[class*="lg:grid-cols-12"]');
    if (!grid) { if (tries > 0) setTimeout(function () { apply(tries - 1); }, 250); return; }
    if (document.getElementById('fmnlg-overlay-wrap')) return;

    injectCss();

    // blur every direct column of the grid...
    Array.prototype.forEach.call(grid.children, function (col) {
      col.classList.add('fmnlg-blur');
    });

    // ...then un-blur the teaser: the photo gallery and the title stay sharp.
    var keepSharp = [];
    var gallery = document.getElementById('gallery-stage');
    var title = document.getElementById('prop-title');
    var summaryImg = document.getElementById('summary-image');
    [gallery, title, summaryImg].forEach(function (el) {
      if (!el) return;
      // walk up: if this element sits inside a blurred column, lift just this element
      el.classList.remove('fmnlg-blur');
      el.style.filter = 'none';
      el.style.pointerEvents = 'auto';
      keepSharp.push(el);
    });
    // the center gallery lives in its own column; keep that whole column sharp
    if (gallery) {
      var col = gallery.closest('[class*="col-span-6"]');
      if (col) { col.classList.remove('fmnlg-blur'); col.style.filter = 'none'; }
      // but blur the sections BELOW the gallery inside that column
      if (col) {
        Array.prototype.forEach.call(col.children, function (child, i) {
          // first child is the gallery card; blur the rest (description etc.)
          if (i > 0) child.classList.add('fmnlg-blur');
        });
      }
    }

    // overlay card
    var wrap = document.createElement('div');
    wrap.id = 'fmnlg-overlay-wrap';
    wrap.className = 'fmnlg-overlay';
    wrap.innerHTML =
      '<div class="fmnlg-card">' +
        '<div class="fmnlg-ic"><i class="fas fa-lock"></i></div>' +
        '<h3>Sign in to view full details</h3>' +
        '<p>Create a free account to see the full listing - location, availability, highlights and more.</p>' +
        '<div class="fmnlg-btns">' +
          '<a href="login.html" class="fmnlg-btn fmnlg-primary">Sign in</a>' +
          '<a href="login.html" class="fmnlg-btn fmnlg-ghost">Create free account</a>' +
        '</div>' +
        '<p class="fmnlg-note">Browsing is always free. You only pay for Verified Access to contact a landlord.</p>' +
      '</div>';
    document.body.appendChild(wrap);
  }

  function start() { apply(40); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
