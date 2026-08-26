/* ============================================================
   FindMyNyumba - Admin Package Management
   Renders a table of service packages with inline editing of price (ZMW),
   duration (days, with +/- steppers), name, and active state. Saves via
   PUT /admin/packages/{id} (the existing admin endpoint).

   admin.html patches `fetch` to auto-inject the admin Bearer token on any
   /api/v1/ request, so plain fetch(API + '/admin/packages') is authenticated.

   Install (three small admin.html additions + this file):
   1. Sidebar nav link (near the revenue group):
        <div class="sb-link" id="nav-packages" onclick="showTab('packages')"><i class="fas fa-box-open w-5"></i> Packages</div>
   2. Tab section (with the other tab-section divs):
        <div class="tab-section" id="tab-packages"><div id="admin-packages-root" class="p-1"></div></div>
   3. In showTab(), add:  if (name === 'packages') loadAdminPackages();
      In TAB_META, add:   packages: ['Package Management', 'Adjust pricing, duration and availability']
   4. Before </body>:  <script src="fmn-admin-packages.js"></script>
============================================================= */
(function () {
  'use strict';

  function apiBase() {
    // reuse the page's API base if present, else derive
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
    if (typeof showToast === 'function') { showToast(msg, kind || 'info'); }
    else { console.log('[packages]', msg); }
  }

  var _pkgs = [];

  window.loadAdminPackages = async function () {
    var root = document.getElementById('admin-packages-root');
    if (!root) return;
    root.innerHTML = '<p class="text-sm text-slate-400 py-6">Loading packages...</p>';
    try {
      var res = await fetch(apiBase() + '/admin/packages');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();
      _pkgs = Array.isArray(data) ? data : (data.value || data.packages || []);
      render(root);
    } catch (e) {
      root.innerHTML = '<p class="text-sm text-red-500 py-6">Could not load packages (' + esc(e.message) + ').</p>';
    }
  };

  function render(root) {
    if (!_pkgs.length) {
      root.innerHTML = '<p class="text-sm text-slate-400 py-6">No packages found.</p>';
      return;
    }
    var rows = _pkgs.map(function (p) {
      var fee = Number(p.service_fee != null ? p.service_fee : (p.price || 0));
      var dur = Number(p.duration_days || 0);
      var active = !!p.is_active;
      var aud = esc(p.audience || 'student');
      var grant = esc(p.grant_type || 'student_access');
      return '' +
        '<tr class="border-b border-slate-100" data-id="' + p.id + '">' +
          '<td class="py-3 pr-3">' +
            '<input type="text" value="' + esc(p.name) + '" data-f="name" ' +
              'class="w-full min-w-[140px] px-2 py-1.5 border border-slate-200 rounded-lg text-sm font-semibold">' +
            '<div class="text-[10px] text-slate-400 mt-1">' + esc(p.code) + ' &middot; ' + aud + ' &middot; ' + grant + '</div>' +
          '</td>' +
          // price
          '<td class="py-3 px-2">' +
            '<div class="flex items-center gap-1">' +
              '<button type="button" class="pk-step w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 font-black text-slate-600" data-step="-10" data-f="fee">&minus;</button>' +
              '<input type="number" value="' + fee + '" data-f="fee" min="0" step="1" ' +
                'class="w-20 px-2 py-1.5 border border-slate-200 rounded-lg text-sm text-center font-bold">' +
              '<button type="button" class="pk-step w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 font-black text-slate-600" data-step="10" data-f="fee">+</button>' +
            '</div>' +
            '<div class="text-[10px] text-slate-400 mt-1 text-center">ZMW</div>' +
          '</td>' +
          // duration
          '<td class="py-3 px-2">' +
            '<div class="flex items-center gap-1">' +
              '<button type="button" class="pk-step w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 font-black text-slate-600" data-step="-1" data-f="dur">&minus;</button>' +
              '<input type="number" value="' + dur + '" data-f="dur" min="1" step="1" ' +
                'class="w-16 px-2 py-1.5 border border-slate-200 rounded-lg text-sm text-center font-bold">' +
              '<button type="button" class="pk-step w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 font-black text-slate-600" data-step="1" data-f="dur">+</button>' +
            '</div>' +
            '<div class="text-[10px] text-slate-400 mt-1 text-center">days</div>' +
          '</td>' +
          // active toggle
          '<td class="py-3 px-2 text-center">' +
            '<button type="button" class="pk-active px-3 py-1.5 rounded-full text-[11px] font-black ' +
              (active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-400') + '" data-f="active" data-on="' + (active ? '1' : '0') + '">' +
              (active ? 'Active' : 'Inactive') + '</button>' +
          '</td>' +
          // save
          '<td class="py-3 pl-2 text-right">' +
            '<button type="button" class="pk-save bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold px-4 py-2 rounded-lg">Save</button>' +
          '</td>' +
        '</tr>';
    }).join('');

    root.innerHTML =
      '<div class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-x-auto">' +
        '<table class="w-full text-sm">' +
          '<thead><tr class="text-left text-[11px] uppercase tracking-wide text-slate-400 border-b border-slate-100">' +
            '<th class="py-2 pr-3 font-black">Package</th>' +
            '<th class="py-2 px-2 font-black text-center">Price</th>' +
            '<th class="py-2 px-2 font-black text-center">Duration</th>' +
            '<th class="py-2 px-2 font-black text-center">Status</th>' +
            '<th class="py-2 pl-2 font-black text-right">Action</th>' +
          '</tr></thead>' +
          '<tbody>' + rows + '</tbody>' +
        '</table>' +
      '</div>' +
      '<p class="text-[11px] text-slate-400 mt-3">Price changes are logged to package price history. Duration applies to new purchases going forward.</p>';

    wire(root);
  }

  function wire(root) {
    // +/- steppers
    root.querySelectorAll('.pk-step').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var tr = btn.closest('tr');
        var f = btn.getAttribute('data-f');
        var step = parseInt(btn.getAttribute('data-step'), 10) || 0;
        var input = tr.querySelector('input[data-f="' + f + '"]');
        var v = Number(input.value) || 0;
        v += step;
        if (v < 0) v = 0;
        if (f === 'dur' && v < 1) v = 1;
        input.value = v;
      });
    });
    // active toggle
    root.querySelectorAll('.pk-active').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var on = btn.getAttribute('data-on') === '1';
        on = !on;
        btn.setAttribute('data-on', on ? '1' : '0');
        btn.textContent = on ? 'Active' : 'Inactive';
        btn.className = 'pk-active px-3 py-1.5 rounded-full text-[11px] font-black ' +
          (on ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-400');
      });
    });
    // save
    root.querySelectorAll('.pk-save').forEach(function (btn) {
      btn.addEventListener('click', function () { saveRow(btn.closest('tr'), btn); });
    });
  }

  async function saveRow(tr, btn) {
    var id = tr.getAttribute('data-id');
    var name = tr.querySelector('input[data-f="name"]').value.trim();
    var fee = Number(tr.querySelector('input[data-f="fee"]').value) || 0;
    var dur = Number(tr.querySelector('input[data-f="dur"]').value) || 0;
    var active = tr.querySelector('.pk-active').getAttribute('data-on') === '1';

    if (dur < 1) { toast('Duration must be at least 1 day.', 'error'); return; }

    var body = { name: name, service_fee: fee, duration_days: dur, is_active: active };

    var old = btn.textContent;
    btn.disabled = true; btn.textContent = 'Saving...';
    try {
      var res = await fetch(apiBase() + '/admin/packages/' + id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        var d = await res.json().catch(function () { return {}; });
        throw new Error(typeof d.detail === 'string' ? d.detail : ('HTTP ' + res.status));
      }
      toast('Saved "' + name + '".', 'success');
    } catch (e) {
      toast('Save failed: ' + e.message, 'error');
    } finally {
      btn.disabled = false; btn.textContent = old;
    }
  }
})();
