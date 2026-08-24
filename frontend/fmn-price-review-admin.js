/* ============================================================
   FindMyNyumba - Price Review moderation queue (Stage 2)
   Trust & Safety queue for student price reviews.
   Reads/writes /admin/price-reviews. Gated to trust_safety/admin/ceo/moderator.

   Install: place in frontend/ and add ONE line before </body> in admin.html:
     <script src="fmn-price-review-admin.js"></script>

   Self contained: injects its own CSS, nav link, tab section and modal,
   and hooks loadPriceReviews() into the existing showTab().
============================================================= */
(function () {
  'use strict';

  var ALLOWED = ['trust_safety', 'admin', 'ceo', 'moderator'];

  function apiBase() {
    if (typeof API !== 'undefined' && API) return API;
    var host = window.location.hostname;
    var local = (host === 'localhost' || host === '127.0.0.1' || host === '');
    return (local ? 'http://127.0.0.1:8000' : 'https://findmynyumba.onrender.com') + '/api/v1';
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }
  function money(v, cur) {
    if (v == null || isNaN(v)) return '\u2014';
    var n = Number(v).toLocaleString();
    return (cur || 'ZMW') === 'ZMW' ? 'K' + n : (esc(cur) + ' ' + n);
  }
  function when(iso) { if (!iso) return '\u2014'; try { return new Date(iso).toLocaleString(); } catch (e) { return iso; } }

  var TYPE_LABEL = {
    too_high: 'Too high', too_low: 'Too low',
    confirmed_accurate: 'Confirmed accurate', paid_different: 'Paid different'
  };
  var TYPE_TONE = {
    too_high: 'hi', too_low: 'lo', confirmed_accurate: 'ok', paid_different: 'df'
  };

  function injectCss() {
    if (document.getElementById('fmnpr-style')) return;
    var css = [
      "#tab-pricereview,.fmnpr-overlay{font-family:'Plus Jakarta Sans',system-ui,-apple-system,sans-serif}",
      ".fmnpr-head{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-bottom:18px}",
      ".fmnpr-tabs{display:inline-flex;background:#f1f5f9;border-radius:11px;padding:3px}",
      ".fmnpr-tab{border:none;background:transparent;font-family:inherit;font-size:12.5px;font-weight:700;color:#64748b;padding:7px 14px;border-radius:9px;cursor:pointer}",
      ".fmnpr-tab.sel{background:#fff;color:#0f172a;box-shadow:0 1px 2px rgba(15,23,42,.08)}",
      ".fmnpr-count{display:inline-block;min-width:18px;padding:0 5px;margin-left:6px;font-size:10px;line-height:16px;text-align:center;border-radius:99px;background:#e2e8f0;color:#475569}",
      ".fmnpr-tab.sel .fmnpr-count{background:#ea580c;color:#fff}",
      ".fmnpr-card{background:#fff;border:1px solid #eef2f7;border-radius:14px;padding:16px 18px;margin-bottom:12px;box-shadow:0 1px 2px rgba(15,23,42,.04)}",
      ".fmnpr-row{display:flex;flex-wrap:wrap;align-items:flex-start;gap:14px}",
      ".fmnpr-main{flex:1;min-width:220px}",
      ".fmnpr-l1{display:flex;align-items:center;gap:9px;flex-wrap:wrap}",
      ".fmnpr-lid{font-size:13.5px;font-weight:800;color:#0f172a}",
      ".fmnpr-lid a{color:#ea580c;text-decoration:none}",
      ".fmnpr-lid a:hover{text-decoration:underline}",
      ".fmnpr-badge{font-size:10px;font-weight:800;padding:3px 9px;border-radius:99px;text-transform:uppercase;letter-spacing:.03em}",
      ".fmnpr-badge.hi{background:#fef2f2;color:#dc2626}",
      ".fmnpr-badge.lo{background:#eff6ff;color:#2563eb}",
      ".fmnpr-badge.ok{background:#ecfdf5;color:#16a34a}",
      ".fmnpr-badge.df{background:#fff7ed;color:#ea580c}",
      ".fmnpr-prices{display:flex;gap:22px;margin:10px 0 8px}",
      ".fmnpr-pl{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8;font-weight:700}",
      ".fmnpr-pv{font-size:17px;font-weight:800;color:#0f172a;font-variant-numeric:tabular-nums}",
      ".fmnpr-pv.rep{color:#ea580c}",
      ".fmnpr-delta{font-size:11px;font-weight:700;margin-left:2px}",
      ".fmnpr-delta.up{color:#dc2626}.fmnpr-delta.down{color:#2563eb}",
      ".fmnpr-note{font-size:12.5px;color:#475569;background:#f8fafc;border-radius:9px;padding:9px 12px;margin-top:6px}",
      ".fmnpr-meta{font-size:11px;color:#94a3b8;margin-top:8px}",
      ".fmnpr-acts{display:flex;flex-direction:column;gap:8px;min-width:130px}",
      ".fmnpr-btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;font-weight:700;border-radius:10px;cursor:pointer;border:none;font-size:12.5px;padding:9px 14px;font-family:inherit}",
      ".fmnpr-accept{background:#16a34a;color:#fff}.fmnpr-accept:hover{background:#15803d}",
      ".fmnpr-dismiss{background:#fff;color:#dc2626;border:1.5px solid #fecaca}.fmnpr-dismiss:hover{background:#fef2f2}",
      ".fmnpr-view{background:#fff;color:#334155;border:1.5px solid #e5e7eb}.fmnpr-view:hover{background:#f8fafc}",
      ".fmnpr-badge-status{font-size:10px;font-weight:800;padding:3px 9px;border-radius:99px}",
      ".fmnpr-badge-status.accepted{background:#ecfdf5;color:#16a34a}",
      ".fmnpr-badge-status.dismissed{background:#f1f5f9;color:#64748b}",
      ".fmnpr-state{padding:48px 20px;text-align:center;font-size:13.5px;color:#94a3b8}",
      ".fmnpr-state.err{color:#ef4444}",
      ".fmnpr-spin{animation:fmnpr-sp .8s linear infinite;display:inline-block}",
      "@keyframes fmnpr-sp{to{transform:rotate(360deg)}}",
      ".fmnpr-overlay{position:fixed;inset:0;background:rgba(15,23,42,.5);display:none;align-items:center;justify-content:center;padding:16px;z-index:9999}",
      ".fmnpr-overlay.open{display:flex}",
      ".fmnpr-modal{background:#fff;border-radius:16px;padding:22px;width:100%;max-width:440px;box-shadow:0 25px 50px -12px rgba(0,0,0,.35)}",
      ".fmnpr-modal h3{font-size:16px;font-weight:800;color:#0f172a;margin:0 0 4px}",
      ".fmnpr-modal p{font-size:12.5px;color:#64748b;margin:0 0 14px}",
      ".fmnpr-modal textarea{width:100%;padding:9px 12px;border:1.5px solid #e5e7eb;border-radius:10px;font-family:inherit;font-size:13px;resize:vertical;outline:none;margin-bottom:16px}",
      ".fmnpr-modal textarea:focus{border-color:#ea580c;box-shadow:0 0 0 3px rgba(234,88,12,.12)}",
      ".fmnpr-modal-acts{display:flex;gap:10px;justify-content:flex-end}"
    ].join("");
    var s = document.createElement('style');
    s.id = 'fmnpr-style';
    s.textContent = css;
    document.head.appendChild(s);
  }

  var _reviews = [];
  var _filter = 'pending';

  function inject() {
    var role = (window.ADMIN_ROLE || sessionStorage.getItem('adminRole') || '').toLowerCase();
    if (!role) return false;
    if (ALLOWED.indexOf(role) === -1) return true;
    if (document.getElementById('nav-pricereview')) return true;

    injectCss();

    var afterEl = document.getElementById('nav-trust') || document.getElementById('nav-fraud');
    if (afterEl) {
      var nav = document.createElement('div');
      nav.className = 'sb-link';
      nav.id = 'nav-pricereview';
      nav.setAttribute('onclick', "showTab('pricereview')");
      nav.innerHTML = '<i class="fas fa-scale-balanced"></i>Price Reviews';
      afterEl.parentNode.insertBefore(nav, afterEl.nextSibling);
    }

    var main = document.querySelector('main');
    if (main && !document.getElementById('tab-pricereview')) {
      var sec = document.createElement('section');
      sec.id = 'tab-pricereview';
      sec.className = 'tab-section';
      sec.innerHTML =
        '<div class="fmnpr-head">' +
          '<div class="fmnpr-tabs">' +
            '<button class="fmnpr-tab sel" data-f="pending" onclick="prFilter(\'pending\')">Pending</button>' +
            '<button class="fmnpr-tab" data-f="accepted" onclick="prFilter(\'accepted\')">Accepted</button>' +
            '<button class="fmnpr-tab" data-f="dismissed" onclick="prFilter(\'dismissed\')">Dismissed</button>' +
          '</div>' +
          '<button class="fmnpr-btn fmnpr-view" style="margin-left:auto" onclick="loadPriceReviews()"><i class="fas fa-rotate"></i>Refresh</button>' +
        '</div>' +
        '<div id="pricereview-body"></div>';
      main.appendChild(sec);
    }

    if (typeof TAB_META !== 'undefined') {
      TAB_META.pricereview = ['Price Reviews', 'Student reports on listing rent accuracy'];
    }
    if (typeof window.showTab === 'function' && !window._showTabPrWrapped) {
      var _orig = window.showTab;
      window.showTab = function (name) { _orig(name); if (name === 'pricereview') loadPriceReviews(); };
      window._showTabPrWrapped = true;
    }
    return true;
  }

  function boot(tries) { if (inject()) return; if (tries > 0) setTimeout(function () { boot(tries - 1); }, 200); }

  window.prFilter = function (f) {
    _filter = f;
    document.querySelectorAll('#tab-pricereview .fmnpr-tab').forEach(function (b) {
      b.classList.toggle('sel', b.dataset.f === f);
    });
    loadPriceReviews();
  };

  window.loadPriceReviews = async function () {
    var body = document.getElementById('pricereview-body');
    if (!body) return;
    body.innerHTML = '<div class="fmnpr-state"><i class="fas fa-circle-notch fmnpr-spin"></i> &nbsp;Loading price reviews...</div>';
    try {
      var r = await fetch(apiBase() + '/admin/price-reviews?status=' + encodeURIComponent(_filter));
      if (r.status === 401 || r.status === 403) {
        body.innerHTML = '<div class="fmnpr-state">You do not have permission to moderate price reviews.</div>';
        return;
      }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      _reviews = await r.json();
      renderReviews();
    } catch (e) {
      body.innerHTML = '<div class="fmnpr-state err"><i class="fas fa-triangle-exclamation"></i> &nbsp;Could not load price reviews.</div>';
    }
  };

  function renderReviews() {
    var body = document.getElementById('pricereview-body');
    if (!body) return;
    if (!_reviews.length) {
      var msg = _filter === 'pending' ? 'No pending price reviews. All caught up.' : 'Nothing here.';
      body.innerHTML = '<div class="fmnpr-state">' + msg + '</div>';
      return;
    }
    body.innerHTML = _reviews.map(function (r) {
      var tone = TYPE_TONE[r.review_type] || 'df';
      var badge = '<span class="fmnpr-badge ' + tone + '">' + esc(TYPE_LABEL[r.review_type] || r.review_type) + '</span>';

      var listed = r.listed_price_at_review;
      var rep = r.reported_price;
      var delta = '';
      if (listed != null && rep != null && listed > 0) {
        var pct = Math.round(((rep - listed) / listed) * 100);
        if (pct !== 0) {
          delta = '<span class="fmnpr-delta ' + (pct > 0 ? 'up' : 'down') + '">' +
                  (pct > 0 ? '+' : '') + pct + '%</span>';
        }
      }

      var pricesHtml =
        '<div class="fmnpr-prices">' +
          '<div><div class="fmnpr-pl">Listed</div><div class="fmnpr-pv">' + money(listed, r.currency) + '</div></div>' +
          (rep != null
            ? '<div><div class="fmnpr-pl">Reported</div><div class="fmnpr-pv rep">' + money(rep, r.currency) + delta + '</div></div>'
            : '') +
        '</div>';

      var actions;
      if (r.status === 'pending') {
        actions =
          '<button class="fmnpr-btn fmnpr-accept" onclick="prModerate(' + r.id + ',\'accept\')"><i class="fas fa-check"></i>Accept</button>' +
          '<button class="fmnpr-btn fmnpr-dismiss" onclick="prModerate(' + r.id + ',\'dismiss\')"><i class="fas fa-xmark"></i>Dismiss</button>';
      } else {
        actions = '<span class="fmnpr-badge-status ' + esc(r.status) + '">' + esc(r.status) + '</span>' +
                  (r.moderated_by_name ? '<div class="fmnpr-meta">by ' + esc(r.moderated_by_name) + '</div>' : '');
      }

      return '' +
        '<div class="fmnpr-card"><div class="fmnpr-row">' +
          '<div class="fmnpr-main">' +
            '<div class="fmnpr-l1">' +
              '<span class="fmnpr-lid">Listing <a href="listing.html?id=' + r.listing_id + '" target="_blank">#' + r.listing_id + '</a></span>' +
              badge +
            '</div>' +
            pricesHtml +
            (r.note ? '<div class="fmnpr-note">' + esc(r.note) + '</div>' : '') +
            '<div class="fmnpr-meta">Submitted ' + esc(when(r.created_at)) +
              (r.user_id ? ' \u00b7 user #' + r.user_id : '') + '</div>' +
          '</div>' +
          '<div class="fmnpr-acts">' + actions + '</div>' +
        '</div></div>';
    }).join('');
  }

  /* ---- moderate with optional note ---- */
  var _pending = { id: null, decision: null };
  window.prModerate = function (id, decision) {
    _pending = { id: id, decision: decision };
    document.getElementById('prm-title').textContent =
      decision === 'accept' ? 'Accept this price review?' : 'Dismiss this price review?';
    document.getElementById('prm-desc').textContent =
      decision === 'accept'
        ? 'It will count toward this listing\u2019s price confidence.'
        : 'It will be excluded and will not affect the listing.';
    document.getElementById('prm-note').value = '';
    var go = document.getElementById('prm-go');
    go.textContent = decision === 'accept' ? 'Accept' : 'Dismiss';
    go.className = 'fmnpr-btn ' + (decision === 'accept' ? 'fmnpr-accept' : 'fmnpr-dismiss');
    document.getElementById('prm-modal').classList.add('open');
  };
  window.prCloseModal = function () { document.getElementById('prm-modal').classList.remove('open'); };

  window.prConfirm = async function () {
    var go = document.getElementById('prm-go');
    var note = document.getElementById('prm-note').value.trim();
    go.disabled = true; go.textContent = 'Working...';
    try {
      var r = await fetch(apiBase() + '/admin/price-reviews/' + _pending.id + '/' + _pending.decision, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: note || null })
      });
      var d = await r.json().catch(function () { return {}; });
      if (!r.ok) throw new Error(d.detail || ('HTTP ' + r.status));
      prCloseModal();
      if (typeof showToast === 'function') {
        showToast(_pending.decision === 'accept'
          ? 'Accepted' + (d.listing_confidence ? ' \u00b7 confidence now ' + d.listing_confidence : '')
          : 'Dismissed');
      }
      loadPriceReviews();
    } catch (e) {
      if (typeof showToast === 'function') showToast(e.message || 'Could not save.');
      go.disabled = false;
      go.textContent = _pending.decision === 'accept' ? 'Accept' : 'Dismiss';
    }
  };

  function buildModal() {
    if (document.getElementById('prm-modal')) return;
    injectCss();
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div id="prm-modal" class="fmnpr-overlay" onclick="if(event.target===this)prCloseModal()">' +
        '<div class="fmnpr-modal">' +
          '<h3 id="prm-title">Moderate</h3>' +
          '<p id="prm-desc"></p>' +
          '<textarea id="prm-note" rows="3" placeholder="Optional note (internal)"></textarea>' +
          '<div class="fmnpr-modal-acts">' +
            '<button class="fmnpr-btn fmnpr-view" onclick="prCloseModal()">Cancel</button>' +
            '<button id="prm-go" class="fmnpr-btn fmnpr-accept" onclick="prConfirm()">Confirm</button>' +
          '</div>' +
        '</div>' +
      '</div>';
    while (wrap.firstChild) document.body.appendChild(wrap.firstChild);
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var m = document.getElementById('prm-modal');
      if (m && m.classList.contains('open')) prCloseModal();
    }
  });

  function start() { buildModal(); boot(30); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
