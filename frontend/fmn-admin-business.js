/* ============================================================
   FindMyNyumba - Admin Business Info editor
   Loads business/legal/contact settings from GET /site-settings and saves
   edits via PUT /admin/site-settings (admin-guarded). Renders into
   #business-info-root, which lives inside the Settings tab.

   admin.html patches fetch to auto-inject the admin Bearer token on /api/v1/
   requests, so plain fetch(API + '/admin/site-settings') is authenticated.

   Install:
   1. Card container in the Settings tab (after Platform Settings card):
        <div id="business-info-root"></div>
   2. In showTab(), where settings loaders run, add:  loadBusinessInfo();
   3. Before </body>:  <script src="fmn-admin-business.js"></script>
============================================================= */
(function () {
  'use strict';

  function apiBase() {
    if (typeof API === 'string' && API) return API;
    if (window.API) return window.API;
    return 'https://findmynyumba.onrender.com/api/v1';
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }
  function toast(msg, kind) {
    if (typeof showToast === 'function') showToast(msg, kind || 'info');
  }

  var FIELDS = [
    ['legal_name',         'Legal business name (PACRA)', 'e.g. FindMyNyumba Limited'],
    ['trading_name',       'Trading / brand name',        'FindMyNyumba'],
    ['pacra_number',       'PACRA registration number',   'optional'],
    ['support_email',      'Support email',               'support@findmynyumba.com'],
    ['support_phone',      'Support phone',               '+260 ...'],
    ['website_url',        'Website URL',                 'https://findmynyumba.com'],
    ['registered_address', 'Registered address',          'Lusaka, Zambia'],
    ['support_sla',        'Support SLA statement',       'Customer inquiries are addressed within 1 business day.'],
    ['facebook_url',       'Facebook URL',                'https://facebook.com/...'],
    ['instagram_url',      'Instagram URL',               'https://instagram.com/...'],
    ['tiktok_url',         'TikTok URL',                  'https://tiktok.com/@...'],
    ['whatsapp_url',       'WhatsApp link',               'https://wa.me/260...'],
  ];

  function cardShell() {
    var inputs = FIELDS.map(function (f) {
      var key = f[0], label = f[1], ph = f[2];
      var multiline = (key === 'registered_address' || key === 'support_sla');
      var field = multiline
        ? '<textarea id="biz-' + key + '" rows="2" class="fmn-input mb-4" placeholder="' + esc(ph) + '"></textarea>'
        : '<input id="biz-' + key + '" class="fmn-input mb-4" placeholder="' + esc(ph) + '">';
      return '<label class="block text-[12px] font-bold text-slate-600 mb-1.5">' + esc(label) + '</label>' + field;
    }).join('');

    return '' +
      '<div class="card p-6 mt-4">' +
        '<h3 class="font-extrabold text-slate-900 text-[15px] mb-1"><i class="fas fa-building mr-2 text-[#ea580c]"></i>Business Information</h3>' +
        '<p class="text-[12px] text-slate-400 font-medium mb-5">Shown on the public footer, contact page and legal policies. Update to your real PACRA-registered details.</p>' +
        '<div id="biz-success" class="hidden mb-4 text-sm font-semibold text-green-700 bg-green-50 rounded-lg px-3 py-2">Saved.</div>' +
        inputs +
        '<button class="btn btn-pri" onclick="saveBusinessInfo()"><i class="fas fa-floppy-disk mr-1"></i>Save Business Info</button>' +
      '</div>';
  }

  window.loadBusinessInfo = async function () {
    var root = document.getElementById('business-info-root');
    if (!root) return;
    if (!root.dataset.built) { root.innerHTML = cardShell(); root.dataset.built = '1'; }
    try {
      var res = await fetch(apiBase() + '/site-settings');
      if (!res.ok) return;
      var d = await res.json();
      FIELDS.forEach(function (f) {
        var el = document.getElementById('biz-' + f[0]);
        if (el) el.value = (d[f[0]] == null ? '' : d[f[0]]);
      });
    } catch (e) { /* leave placeholders */ }
  };

  window.saveBusinessInfo = async function () {
    var body = {};
    FIELDS.forEach(function (f) {
      var el = document.getElementById('biz-' + f[0]);
      if (el) body[f[0]] = el.value.trim();
    });
    try {
      var res = await fetch(apiBase() + '/admin/site-settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        var det = await res.json().catch(function () { return {}; });
        throw new Error(typeof det.detail === 'string' ? det.detail : 'HTTP ' + res.status);
      }
      var ok = document.getElementById('biz-success');
      if (ok) { ok.classList.remove('hidden'); setTimeout(function () { ok.classList.add('hidden'); }, 2500); }
      toast('Business info saved.', 'success');
    } catch (e) {
      toast('Save failed: ' + e.message, 'error');
    }
  };
})();
