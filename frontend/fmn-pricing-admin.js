/* ============================================================
   FindMyNyumba - Service Fees admin panel (Pricing Stage 1)
   Reads/writes the /admin/packages endpoints. CEO/admin only.
   Service fees ONLY. Never touches listings.price (accommodation rent).

   Install: place in frontend/ and add ONE line before </body> in admin.html:
     <script src="fmn-pricing-admin.js"></script>

   Self contained: injects its own CSS, nav link, tab section and modals,
   and hooks loadPricing() into the existing showTab().
============================================================= */
(function () {
  'use strict';

  /* ---------------- styles ---------------- */
  var CSS = [
    "#tab-pricing,.fmnp-overlay{font-family:'Plus Jakarta Sans',system-ui,-apple-system,sans-serif}",
    ".fmnp-head{background:#fff;border:1px solid #eef2f7;border-radius:16px;padding:18px 20px;margin-bottom:20px;box-shadow:0 1px 2px rgba(15,23,42,.04)}",
    ".fmnp-head-row{display:flex;flex-wrap:wrap;align-items:center;gap:12px}",
    ".fmnp-h3{font-size:15px;font-weight:800;color:#0f172a;margin:0}",
    ".fmnp-sub{font-size:12px;color:#94a3b8;font-weight:500;margin:2px 0 0}",
    ".fmnp-note{display:flex;align-items:flex-start;gap:10px;margin-top:14px;background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:12px 16px}",
    ".fmnp-note i{color:#ea580c;margin-top:2px}",
    ".fmnp-note p{font-size:12px;color:#475569;line-height:1.55;margin:0}",
    ".fmnp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}",
    ".fmnp-card{background:#fff;border:1px solid #eef2f7;border-radius:16px;padding:20px;display:flex;flex-direction:column;box-shadow:0 1px 2px rgba(15,23,42,.04)}",
    ".fmnp-card-top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}",
    ".fmnp-name{font-size:15px;font-weight:800;color:#0f172a;margin:0}",
    ".fmnp-code{display:inline-block;margin-top:4px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8}",
    ".fmnp-fee-row{margin-top:12px;display:flex;align-items:baseline;gap:6px}",
    ".fmnp-fee{font-size:28px;font-weight:800;color:#0f172a;line-height:1;font-variant-numeric:tabular-nums}",
    ".fmnp-per{font-size:12px;font-weight:600;color:#94a3b8}",
    ".fmnp-desc{margin-top:8px;font-size:12.5px;color:#64748b}",
    ".fmnp-feats{list-style:none;padding:0;margin:12px 0 0;display:flex;flex-direction:column;gap:6px}",
    ".fmnp-feats li{display:flex;align-items:flex-start;gap:8px;font-size:12.5px;color:#475569}",
    ".fmnp-feats i{color:#16a34a;margin-top:2px;font-size:11px}",
    ".fmnp-empty-feats{margin-top:12px;font-size:12px;color:#94a3b8;font-style:italic}",
    ".fmnp-actions{margin-top:16px;padding-top:16px;border-top:1px solid #f1f5f9;display:flex;gap:8px}",
    ".fmnp-pill{display:inline-flex;align-items:center;gap:5px;font-size:10px;font-weight:800;padding:3px 9px;border-radius:99px}",
    ".fmnp-pill-on{background:#ecfdf5;color:#16a34a}",
    ".fmnp-pill-off{background:#f1f5f9;color:#64748b}",
    ".fmnp-dot{width:6px;height:6px;border-radius:50%;background:#16a34a}",
    ".fmnp-btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;font-weight:700;border-radius:11px;cursor:pointer;border:none;font-size:12.5px;padding:9px 14px;font-family:inherit;transition:all .15s}",
    ".fmnp-btn i{font-size:12px}",
    ".fmnp-btn-pri{background:#ea580c;color:#fff;flex:1}",
    ".fmnp-btn-pri:hover{background:#c2410c}",
    ".fmnp-btn-ghost{background:#fff;color:#334155;border:1.5px solid #e5e7eb}",
    ".fmnp-btn-ghost:hover{background:#f8fafc;border-color:#cbd5e1}",
    ".fmnp-state{grid-column:1/-1;padding:40px 20px;text-align:center;font-size:13.5px;color:#94a3b8}",
    ".fmnp-state.err{color:#ef4444}",
    ".fmnp-overlay{position:fixed;inset:0;background:rgba(15,23,42,.5);display:none;align-items:center;justify-content:center;padding:16px;z-index:9999}",
    ".fmnp-overlay.open{display:flex}",
    ".fmnp-modal{background:#fff;border-radius:16px;padding:24px;width:100%;max-width:560px;max-height:92vh;overflow:auto;box-shadow:0 25px 50px -12px rgba(0,0,0,.35)}",
    ".fmnp-modal.wide{max-width:720px}",
    ".fmnp-modal-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px}",
    ".fmnp-modal-title{font-size:18px;font-weight:800;color:#0f172a;margin:0}",
    ".fmnp-x{width:36px;height:36px;border-radius:10px;border:none;background:transparent;color:#64748b;cursor:pointer;font-size:15px}",
    ".fmnp-x:hover{background:#f1f5f9}",
    ".fmnp-modal-sub{font-size:12px;color:#94a3b8;font-weight:500;margin:0 0 16px}",
    ".fmnp-label{display:block;font-size:12px;font-weight:700;color:#475569;margin:0 0 6px}",
    ".fmnp-label .muted{font-weight:500;color:#94a3b8}",
    ".fmnp-in{width:100%;padding:9px 13px;border:1.5px solid #e5e7eb;border-radius:11px;font-size:13.5px;font-family:inherit;outline:none;background:#fff;margin-bottom:16px}",
    ".fmnp-in:focus{border-color:#ea580c;box-shadow:0 0 0 3px rgba(234,88,12,.12)}",
    "textarea.fmnp-in{resize:vertical}",
    ".fmnp-row2{display:grid;grid-template-columns:1fr 1fr;gap:12px}",
    ".fmnp-help{font-size:11px;color:#94a3b8;margin:-12px 0 16px}",
    ".fmnp-toggle{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border:1px solid #eef2f7;border-radius:12px;margin-bottom:16px;cursor:pointer}",
    ".fmnp-toggle:hover{background:#f8fafc}",
    ".fmnp-toggle-t{font-size:13.5px;font-weight:700;color:#0f172a;display:block}",
    ".fmnp-toggle-d{font-size:11px;color:#94a3b8;display:block}",
    ".fmnp-toggle input{width:20px;height:20px;accent-color:#ea580c;flex-shrink:0}",
    ".fmnp-err{display:none;margin-bottom:16px;font-size:13px;font-weight:600;color:#dc2626;background:#fef2f2;border:1px solid #fecaca;border-radius:11px;padding:11px 15px}",
    ".fmnp-err.show{display:block}",
    ".fmnp-modal-actions{display:flex;gap:12px;justify-content:flex-end;margin-top:4px}",
    ".fmnp-htable{width:100%;border-collapse:collapse;font-size:12.5px}",
    ".fmnp-htable th{text-align:left;padding:8px 12px 8px 0;font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8;border-bottom:1px solid #f1f5f9}",
    ".fmnp-htable td{padding:8px 12px 8px 0;border-bottom:1px solid #f8fafc;color:#475569}",
    ".fmnp-htable td.new{font-weight:700;color:#0f172a}",
    ".fmnp-tabnum{font-variant-numeric:tabular-nums}",
    ".fmnp-spin{animation:fmnp-sp .8s linear infinite;display:inline-block}",
    "@keyframes fmnp-sp{to{transform:rotate(360deg)}}"
  ].join("");

  function injectCss() {
    if (document.getElementById('fmnp-style')) return;
    var s = document.createElement('style');
    s.id = 'fmnp-style';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  /* ---------------- helpers ---------------- */
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }
  function money(fee, cur) {
    if (fee == null || isNaN(fee)) return '\u2014';
    var n = Number(fee).toLocaleString();
    return (cur || 'ZMW') === 'ZMW' ? 'K' + n : (esc(cur) + ' ' + n);
  }
  function fmtWhen(iso) {
    if (!iso) return '\u2014';
    try { return new Date(iso).toLocaleString(); } catch (e) { return iso; }
  }
  function apiBase() {
    if (typeof API !== 'undefined' && API) return API;
    var host = window.location.hostname;
    var local = (host === 'localhost' || host === '127.0.0.1' || host === '');
    return (local ? 'http://127.0.0.1:8000' : 'https://findmynyumba.onrender.com') + '/api/v1';
  }

  var _packages = [];

  /* ---------------- injection ---------------- */
  function inject() {
    var role = (window.ADMIN_ROLE || sessionStorage.getItem('adminRole') || '').toLowerCase();
    if (!role) return false;                              // wait for /auth/me
    if (role !== 'ceo' && role !== 'admin') return true;  // matches settings.pricing guard
    if (document.getElementById('nav-pricing')) return true;

    injectCss();

    var afterEl = document.getElementById('nav-escrow') || document.getElementById('nav-transactions');
    if (afterEl) {
      var nav = document.createElement('div');
      nav.className = 'sb-link';
      nav.id = 'nav-pricing';
      nav.setAttribute('onclick', "showTab('pricing')");
      nav.innerHTML = '<i class="fas fa-tags"></i>Service Fees';
      afterEl.parentNode.insertBefore(nav, afterEl.nextSibling);
    }

    var main = document.querySelector('main');
    if (main && !document.getElementById('tab-pricing')) {
      var sec = document.createElement('section');
      sec.id = 'tab-pricing';
      sec.className = 'tab-section';
      sec.innerHTML =
        '<div class="fmnp-head">' +
          '<div class="fmnp-head-row">' +
            '<div style="margin-right:auto">' +
              '<h3 class="fmnp-h3">FindMyNyumba Service Fees</h3>' +
              '<p class="fmnp-sub">Connect and Assist packages that students pay for FindMyNyumba services.</p>' +
            '</div>' +
            '<button class="fmnp-btn fmnp-btn-ghost" onclick="loadPricing()"><i class="fas fa-rotate"></i>Refresh</button>' +
          '</div>' +
          '<div class="fmnp-note"><i class="fas fa-circle-info"></i>' +
            '<p>These are FindMyNyumba service fees only. They are completely separate from accommodation rent, which each landlord sets on their own listing. Editing a fee here never changes any rent.</p>' +
          '</div>' +
        '</div>' +
        '<div id="pricing-body" class="fmnp-grid"></div>';
      main.appendChild(sec);
    }

    if (typeof TAB_META !== 'undefined') {
      TAB_META.pricing = ['Service Fees', 'FindMyNyumba service packages and pricing'];
    }
    if (typeof window.showTab === 'function' && !window._showTabPricingWrapped) {
      var _orig = window.showTab;
      window.showTab = function (name) { _orig(name); if (name === 'pricing') loadPricing(); };
      window._showTabPricingWrapped = true;
    }
    return true;
  }

  function boot(tries) {
    if (inject()) return;
    if (tries > 0) setTimeout(function () { boot(tries - 1); }, 200);
  }

  /* ---------------- data ---------------- */
  window.loadPricing = async function () {
    var body = document.getElementById('pricing-body');
    if (!body) return;
    body.innerHTML = '<div class="fmnp-state"><i class="fas fa-circle-notch fmnp-spin"></i> &nbsp;Loading service fees...</div>';
    try {
      var r = await fetch(apiBase() + '/admin/packages');
      if (r.status === 401 || r.status === 403) {
        body.innerHTML = '<div class="fmnp-state">You do not have permission to view service fees.</div>';
        return;
      }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      _packages = await r.json();
      renderPricing();
    } catch (e) {
      body.innerHTML = '<div class="fmnp-state err"><i class="fas fa-triangle-exclamation"></i> &nbsp;Could not load service fees.</div>';
    }
  };

  function renderPricing() {
    var body = document.getElementById('pricing-body');
    if (!body) return;
    if (!_packages.length) {
      body.innerHTML = '<div class="fmnp-state">No service packages yet.</div>';
      return;
    }
    body.innerHTML = _packages.map(function (p) {
      var active = p.is_active !== false;
      var pill = active
        ? '<span class="fmnp-pill fmnp-pill-on"><span class="fmnp-dot"></span>Active</span>'
        : '<span class="fmnp-pill fmnp-pill-off">Inactive</span>';
      var feats = (p.features || []).length
        ? '<ul class="fmnp-feats">' + p.features.map(function (f) {
            return '<li><i class="fas fa-check"></i>' + esc(f) + '</li>';
          }).join('') + '</ul>'
        : '<p class="fmnp-empty-feats">No features listed.</p>';
      return '' +
        '<div class="fmnp-card">' +
          '<div class="fmnp-card-top">' +
            '<div><h4 class="fmnp-name">' + esc(p.name) + '</h4><span class="fmnp-code">' + esc(p.code) + '</span></div>' +
            pill +
          '</div>' +
          '<div class="fmnp-fee-row">' +
            '<span class="fmnp-fee">' + money(p.service_fee, p.currency) + '</span>' +
            '<span class="fmnp-per">/ ' + (p.duration_days || 0) + ' days</span>' +
          '</div>' +
          (p.description ? '<p class="fmnp-desc">' + esc(p.description) + '</p>' : '') +
          feats +
          '<div class="fmnp-actions">' +
            '<button class="fmnp-btn fmnp-btn-pri" onclick="openEditPackage(' + p.id + ')"><i class="fas fa-pen"></i>Edit fee</button>' +
            '<button class="fmnp-btn fmnp-btn-ghost" onclick="openPackageHistory(' + p.id + ')"><i class="fas fa-clock-rotate-left"></i>History</button>' +
          '</div>' +
        '</div>';
    }).join('');
  }

  /* ---------------- edit ---------------- */
  window.openEditPackage = function (id) {
    var p = _packages.find(function (x) { return x.id === id; });
    if (!p) return;
    document.getElementById('pkg-edit-title').textContent = 'Edit ' + (p.name || 'package');
    document.getElementById('pkg-edit-id').value = p.id;
    document.getElementById('pkg-f-name').value = p.name || '';
    document.getElementById('pkg-f-fee').value = p.service_fee != null ? p.service_fee : '';
    document.getElementById('pkg-f-currency').value = p.currency || 'ZMW';
    document.getElementById('pkg-f-duration').value = p.duration_days != null ? p.duration_days : '';
    document.getElementById('pkg-f-features').value = (p.features || []).join('\n');
    document.getElementById('pkg-f-desc').value = p.description || '';
    document.getElementById('pkg-f-active').checked = p.is_active !== false;
    document.getElementById('pkg-f-reason').value = '';
    document.getElementById('pkg-edit-err').classList.remove('show');
    document.getElementById('pkg-edit-oldfee').textContent = money(p.service_fee, p.currency);
    document.getElementById('pkg-edit-modal').classList.add('open');
  };
  window.closeEditPackage = function () {
    document.getElementById('pkg-edit-modal').classList.remove('open');
  };

  window.savePackage = async function () {
    var err = document.getElementById('pkg-edit-err');
    var btn = document.getElementById('pkg-save-btn');
    err.classList.remove('show');
    function fail(msg) { err.textContent = msg; err.classList.add('show'); }

    var id = document.getElementById('pkg-edit-id').value;
    var feeRaw = document.getElementById('pkg-f-fee').value.trim();
    var durRaw = document.getElementById('pkg-f-duration').value.trim();
    var nameV = document.getElementById('pkg-f-name').value.trim();
    var fee = feeRaw === '' ? null : Number(feeRaw);
    var dur = durRaw === '' ? null : parseInt(durRaw, 10);

    if (!nameV) { fail('Package name is required.'); return; }
    if (fee != null && (isNaN(fee) || fee < 0)) { fail('Enter a valid fee (0 or more).'); return; }
    if (dur != null && (isNaN(dur) || dur < 1)) { fail('Duration must be at least 1 day.'); return; }

    var features = document.getElementById('pkg-f-features').value
      .split('\n').map(function (s) { return s.trim(); }).filter(Boolean);

    var payload = {
      name: nameV,
      currency: document.getElementById('pkg-f-currency').value.trim().toUpperCase() || 'ZMW',
      description: document.getElementById('pkg-f-desc').value.trim(),
      features: features,
      is_active: document.getElementById('pkg-f-active').checked,
      reason: document.getElementById('pkg-f-reason').value.trim() || null
    };
    if (fee != null) payload.service_fee = fee;
    if (dur != null) payload.duration_days = dur;

    btn.disabled = true; btn.textContent = 'Saving...';
    try {
      var r = await fetch(apiBase() + '/admin/packages/' + id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      var d = await r.json().catch(function () { return {}; });
      if (!r.ok) throw new Error(d.detail || ('HTTP ' + r.status));
      var idx = _packages.findIndex(function (x) { return String(x.id) === String(id); });
      if (idx > -1) _packages[idx] = d;
      renderPricing();
      closeEditPackage();
      if (typeof showToast === 'function') showToast('Service fee updated.');
    } catch (e) {
      fail(e.message || 'Could not save. Try again.');
    } finally {
      btn.disabled = false; btn.textContent = 'Save changes';
    }
  };

  /* ---------------- history ---------------- */
  window.openPackageHistory = async function (id) {
    var p = _packages.find(function (x) { return x.id === id; });
    document.getElementById('pkg-history-title').textContent =
      'Price history: ' + (p ? p.name : 'package');
    var bodyEl = document.getElementById('pkg-history-body');
    bodyEl.innerHTML = '<div class="fmnp-state"><i class="fas fa-circle-notch fmnp-spin"></i> &nbsp;Loading...</div>';
    document.getElementById('pkg-history-modal').classList.add('open');
    try {
      var r = await fetch(apiBase() + '/admin/packages/' + id + '/history');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      var rows = await r.json();
      if (!rows.length) {
        bodyEl.innerHTML = '<div class="fmnp-state">No price changes recorded yet.</div>';
        return;
      }
      bodyEl.innerHTML =
        '<table class="fmnp-htable"><thead><tr>' +
          '<th>When</th><th>Old</th><th>New</th><th>By</th><th>Reason</th>' +
        '</tr></thead><tbody>' +
        rows.map(function (h) {
          return '<tr>' +
            '<td style="white-space:nowrap">' + esc(fmtWhen(h.changed_at)) + '</td>' +
            '<td class="fmnp-tabnum">' + money(h.old_fee, h.currency) + '</td>' +
            '<td class="new fmnp-tabnum">' + money(h.new_fee, h.currency) + '</td>' +
            '<td>' + esc(h.changed_by_name || '\u2014') + '</td>' +
            '<td>' + esc(h.reason || '\u2014') + '</td>' +
          '</tr>';
        }).join('') +
        '</tbody></table>';
    } catch (e) {
      bodyEl.innerHTML = '<div class="fmnp-state err">Could not load history.</div>';
    }
  };
  window.closePackageHistory = function () {
    document.getElementById('pkg-history-modal').classList.remove('open');
  };

  /* ---------------- modals ---------------- */
  function buildModals() {
    if (document.getElementById('pkg-edit-modal')) return;
    injectCss();
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div id="pkg-edit-modal" class="fmnp-overlay" onclick="if(event.target===this)closeEditPackage()">' +
        '<div class="fmnp-modal">' +
          '<div class="fmnp-modal-top">' +
            '<h3 id="pkg-edit-title" class="fmnp-modal-title">Edit package</h3>' +
            '<button class="fmnp-x" onclick="closeEditPackage()"><i class="fas fa-xmark"></i></button>' +
          '</div>' +
          '<p class="fmnp-modal-sub">This is a FindMyNyumba service fee. It does not affect any accommodation rent.</p>' +
          '<input type="hidden" id="pkg-edit-id">' +
          '<div id="pkg-edit-err" class="fmnp-err"></div>' +
          '<label class="fmnp-label">Package name</label>' +
          '<input id="pkg-f-name" class="fmnp-in">' +
          '<div class="fmnp-row2">' +
            '<div><label class="fmnp-label">Service fee</label>' +
              '<input id="pkg-f-fee" type="number" min="0" step="1" class="fmnp-in" style="margin-bottom:4px">' +
              '<p class="fmnp-help">Current: <b id="pkg-edit-oldfee"></b></p></div>' +
            '<div><label class="fmnp-label">Currency</label>' +
              '<input id="pkg-f-currency" class="fmnp-in" value="ZMW"></div>' +
          '</div>' +
          '<label class="fmnp-label">Duration (days)</label>' +
          '<input id="pkg-f-duration" type="number" min="1" step="1" class="fmnp-in">' +
          '<label class="fmnp-label">Features (one per line)</label>' +
          '<textarea id="pkg-f-features" rows="4" class="fmnp-in" placeholder="One feature per line"></textarea>' +
          '<label class="fmnp-label">Description</label>' +
          '<textarea id="pkg-f-desc" rows="2" class="fmnp-in"></textarea>' +
          '<label class="fmnp-toggle">' +
            '<span><span class="fmnp-toggle-t">Active</span>' +
            '<span class="fmnp-toggle-d">Inactive packages are hidden from the payment page and cannot be purchased.</span></span>' +
            '<input type="checkbox" id="pkg-f-active"></label>' +
          '<label class="fmnp-label">Reason for change <span class="muted">(saved to history only when the fee changes)</span></label>' +
          '<input id="pkg-f-reason" class="fmnp-in" placeholder="e.g. seasonal adjustment">' +
          '<div class="fmnp-modal-actions">' +
            '<button class="fmnp-btn fmnp-btn-ghost" onclick="closeEditPackage()">Cancel</button>' +
            '<button id="pkg-save-btn" class="fmnp-btn fmnp-btn-pri" style="flex:none;padding:9px 18px" onclick="savePackage()">Save changes</button>' +
          '</div>' +
        '</div>' +
      '</div>' +
      '<div id="pkg-history-modal" class="fmnp-overlay" onclick="if(event.target===this)closePackageHistory()">' +
        '<div class="fmnp-modal wide">' +
          '<div class="fmnp-modal-top">' +
            '<h3 id="pkg-history-title" class="fmnp-modal-title">Price history</h3>' +
            '<button class="fmnp-x" onclick="closePackageHistory()"><i class="fas fa-xmark"></i></button>' +
          '</div>' +
          '<div id="pkg-history-body" style="margin-top:12px"></div>' +
        '</div>' +
      '</div>';
    while (wrap.firstChild) document.body.appendChild(wrap.firstChild);
  }

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var em = document.getElementById('pkg-edit-modal');
    if (em && em.classList.contains('open')) closeEditPackage();
    var hm = document.getElementById('pkg-history-modal');
    if (hm && hm.classList.contains('open')) closePackageHistory();
  });

  /* ---------------- start ---------------- */
  function start() { buildModals(); boot(30); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
