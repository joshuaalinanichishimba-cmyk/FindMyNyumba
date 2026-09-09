/* ============================================================
   FindMyNyumba - student Payments plans
   Fills #student-plans with the live admin-managed Verified Access packages
   from GET /packages?audience=student. Each plan routes to the mobile-money
   checkout (Airtel / MTN). Prices and durations are whatever admins set in
   Package Management, so this stays in sync automatically.
============================================================= */
(function () {
  'use strict';

  function apiBase() {
    return (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
      ? 'http://127.0.0.1:8000/api/v1'
      : 'https://findmynyumba.onrender.com/api/v1';
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }
  function money(n) { return 'K' + Number(n || 0).toLocaleString(); }

  async function loadStudentPlans() {
    var box = document.getElementById('student-plans');
    if (!box) return;
    box.innerHTML = '<p class="text-[12.5px] text-slate-400">Loading plans...</p>';
    try {
      var res = await fetch(apiBase() + '/packages?audience=student');
      if (!res.ok) throw new Error('load failed');
      var raw = await res.json();
      var plans = Array.isArray(raw) ? raw : (raw.value || raw.packages || []);
      // only active student-facing plans
      plans = plans.filter(function (p) { return p.is_active !== false; });
      if (!plans.length) {
        box.innerHTML = '<p class="text-[12.5px] text-slate-400">No plans available right now.</p>';
        return;
      }
      box.innerHTML = plans.map(function (p) {
        var fee = Math.round(Number(p.service_fee != null ? p.service_fee : (p.price || 0)));
        var dur = Number(p.duration_days || 0);
        var feats = Array.isArray(p.features) ? p.features : [];
        var featHtml = feats.length
          ? '<ul class="mt-3 space-y-1.5">' + feats.slice(0, 4).map(function (f) {
              return '<li class="flex items-start gap-2 text-[12px] text-slate-500"><i class="fas fa-check text-[#16a34a] mt-0.5"></i>' + esc(f) + '</li>';
            }).join('') + '</ul>'
          : '';
        var href = 'pay-verified-access.html?tier=' + encodeURIComponent(p.code || '');
        return '' +
          '<div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex flex-col">' +
            '<p class="font-black text-slate-900">' + esc(p.name || 'Verified Access') + '</p>' +
            '<div class="mt-2"><span class="text-2xl font-black text-slate-900">' + money(fee) + '</span>' +
              (dur ? '<span class="text-[12px] text-slate-400 font-medium"> / ' + dur + ' days</span>' : '') + '</div>' +
            (p.description ? '<p class="text-[12px] text-slate-500 mt-2">' + esc(p.description) + '</p>' : '') +
            featHtml +
            '<a href="' + href + '" class="mt-4 inline-flex items-center justify-center gap-2 bg-[#ea580c] hover:bg-[#c2410c] text-white text-[13px] font-bold py-2.5 rounded-xl transition">' +
              '<i class="fas fa-mobile-screen-button"></i> Pay with mobile money</a>' +
          '</div>';
      }).join('');
    } catch (e) {
      box.innerHTML = '<p class="text-[12.5px] text-red-500">Could not load plans. Please refresh.</p>';
    }
  }

  // load when the payments tab is opened, and once on page load in case it's the default
  var origSwitch = window.switchTab;
  if (typeof origSwitch === 'function') {
    window.switchTab = function (name) {
      origSwitch.apply(this, arguments);
      if (name === 'payments') loadStudentPlans();
    };
  }
  document.addEventListener('DOMContentLoaded', function () {
    // if the payments section is visible on load, populate it
    var sec = document.getElementById('payments-section');
    if (sec && !sec.classList.contains('hidden')) loadStudentPlans();
    else loadStudentPlans(); // safe: fills the container whenever present
  });
})();
