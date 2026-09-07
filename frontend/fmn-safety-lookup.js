/* ============================================================
   FindMyNyumba - safety verification lookup (safety.html)
   Calls GET /safety/verify-landlord?query=... and renders one of three
   states: verified (green), unverified (amber), blacklisted (red).
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

  var btn = document.getElementById('verify-btn');
  var input = document.getElementById('verify-input');
  var out = document.getElementById('verify-result');
  if (!btn || !input || !out) return;

  function show(html) { out.innerHTML = html; out.classList.remove('hidden'); }

  function render(state, data) {
    if (state === 'verified') {
      show(
        '<div class="rounded-xl bg-green-50 border border-green-200 p-4">' +
          '<p class="font-black text-green-800 text-sm"><i class="fas fa-circle-check mr-1"></i>Verified provider</p>' +
          (data.name ? '<p class="text-green-700 text-sm mt-1">' + esc(data.name) + '</p>' : '') +
          '<p class="text-green-600 text-[12px] mt-1">' + esc(data.message || '') + '</p>' +
        '</div>'
      );
    } else if (state === 'blacklisted') {
      show(
        '<div class="rounded-xl bg-red-50 border border-red-200 p-4">' +
          '<p class="font-black text-red-800 text-sm"><i class="fas fa-triangle-exclamation mr-1"></i>Blacklisted - do not pay</p>' +
          '<p class="text-red-600 text-[13px] mt-1">' + esc(data.message || '') + '</p>' +
        '</div>'
      );
    } else {
      show(
        '<div class="rounded-xl bg-amber-50 border border-amber-200 p-4">' +
          '<p class="font-black text-amber-800 text-sm"><i class="fas fa-circle-exclamation mr-1"></i>Not a verified provider</p>' +
          '<p class="text-amber-700 text-[13px] mt-1">' + esc(data.message || '') + '</p>' +
        '</div>'
      );
    }
  }

  async function run() {
    var q = (input.value || '').trim();
    if (q.length < 3) { show('<p class="text-slate-400 text-sm">Enter at least 3 characters.</p>'); return; }
    var original = btn.innerHTML;
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Checking...';
    try {
      var res = await fetch(apiBase() + '/safety/verify-landlord?query=' + encodeURIComponent(q));
      var d = await res.json();
      if (!res.ok) throw new Error(d.detail || 'Lookup failed.');
      render(d.state, d);
    } catch (e) {
      show('<div class="rounded-xl bg-slate-50 border border-slate-200 p-4"><p class="text-slate-500 text-sm">' + esc(e.message) + '</p></div>');
    } finally {
      btn.disabled = false; btn.innerHTML = original;
    }
  }

  btn.addEventListener('click', run);
  input.addEventListener('keydown', function (e) { if (e.key === 'Enter') run(); });
})();
