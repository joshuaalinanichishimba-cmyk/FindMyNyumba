/* ============================================================
   FindMyNyumba - Admin Listing Approvals (Verification Queue sub-tab)
   Adds a "User Identity | Listing Approvals" toggle to the Verification
   Queue tab. The Listing Approvals view lists pending listings, opens an
   inspector modal, and wires Approve / Reject(with reason) / Toggle
   Physical Inspection to the backend.

   Endpoints:
     GET   /admin/pending-listings
     PATCH /admin/listings/{id}/approve
     PATCH /admin/listings/{id}/reject   (body: { reason })
     PATCH /admin/listings/{id}/inspect-badge
   admin.html patches fetch to auto-inject the admin Bearer token.
============================================================= */
(function () {
  'use strict';

  function apiBase() { return (typeof API === 'string' && API) ? API : (window.API || 'https://findmynyumba.onrender.com/api/v1'); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]; }); }
  function toast(m, k) { if (typeof showToast === 'function') showToast(m, k || 'info'); }
  function money(n) { return 'ZMW ' + Number(n || 0).toLocaleString(); }
  function fmtDate(iso) { if (!iso) return '-'; try { return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }); } catch (e) { return String(iso).slice(0, 10); } }

  var REJECT_REASONS = [
    'Incomplete property details',
    'Unclear or blurry NRC / ownership document',
    'Mismatch in rental pricing',
    'Duplicate listing detected',
  ];

  var _listings = [];
  var _current = null;

  // ---- inject the sub-toggle into the Verification Queue tab ----
  window.initListingVerify = function () {
    var tab = document.getElementById('tab-verifications');
    if (!tab || document.getElementById('lv-subtabs')) return;
    var card = tab.querySelector('.card');
    if (!card) return;

    var bar = document.createElement('div');
    bar.id = 'lv-subtabs';
    bar.className = 'flex gap-2 px-5 pt-4';
    bar.innerHTML =
      '<button id="lv-tab-identity" type="button" class="px-4 py-2 rounded-full text-[13px] font-bold bg-[#ea580c] text-white">User Identity</button>' +
      '<button id="lv-tab-listings" type="button" class="px-4 py-2 rounded-full text-[13px] font-bold bg-white border border-slate-200 text-slate-600 hover:border-[#ea580c]">Listing Approvals</button>';
    card.insertBefore(bar, card.firstChild);

    // wrapper that holds the listings view (hidden by default; identity table stays as-is)
    var host = document.createElement('div');
    host.id = 'lv-listings-host';
    host.className = 'hidden';
    card.appendChild(host);

    document.getElementById('lv-tab-identity').addEventListener('click', function () { switchSub('identity'); });
    document.getElementById('lv-tab-listings').addEventListener('click', function () { switchSub('listings'); });
  };

  function switchSub(which) {
    var idTab = document.getElementById('lv-tab-identity');
    var lsTab = document.getElementById('lv-tab-listings');
    var host = document.getElementById('lv-listings-host');
    var identityTable = document.querySelector('#tab-verifications .overflow-x-auto');
    var on = 'px-4 py-2 rounded-full text-[13px] font-bold bg-[#ea580c] text-white';
    var off = 'px-4 py-2 rounded-full text-[13px] font-bold bg-white border border-slate-200 text-slate-600 hover:border-[#ea580c]';
    if (which === 'listings') {
      lsTab.className = on; idTab.className = off;
      if (identityTable) identityTable.style.display = 'none';
      host.classList.remove('hidden');
      loadListingQueue();
    } else {
      idTab.className = on; lsTab.className = off;
      if (identityTable) identityTable.style.display = '';
      host.classList.add('hidden');
    }
  }

  var _filter = 'pending';

  async function loadListingQueue() {
    var host = document.getElementById('lv-listings-host');
    host.innerHTML = '<p class="text-sm text-slate-400 px-5 py-8">Loading listings...</p>';
    try {
      // pending endpoint for the default queue; all-listings for the other filters
      var url = apiBase() + (_filter === 'pending' ? '/admin/pending-listings' : '/admin/all-listings');
      var res = await fetch(url);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var d = await res.json();
      _listings = Array.isArray(d) ? d : (d.listings || d.items || []);
      renderQueue(host);
    } catch (e) {
      host.innerHTML = '<p class="text-sm text-red-500 px-5 py-8">Could not load listings (' + esc(e.message) + ').</p>';
    }
  }

  function matchesFilter(l) {
    if (_filter === 'pending') return l.status === 'pending';
    if (_filter === 'active') return l.status === 'active';
    if (_filter === 'inspected') return !!l.is_physically_inspected;
    if (_filter === 'rejected') return l.status === 'rejected';
    return true;
  }

  function renderQueue(host) {
    var filters = [['pending', 'Pending'], ['active', 'Verified & Active'], ['inspected', 'Physically Inspected'], ['rejected', 'Rejected']].map(function (f) {
      var active = _filter === f[0];
      return '<button type="button" class="lv-filter px-3 py-1.5 rounded-full text-[12px] font-bold ' +
        (active ? 'bg-slate-900 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:border-[#ea580c]') +
        '" data-f="' + f[0] + '">' + f[1] + '</button>';
    }).join('');

    var rows = _listings.filter(matchesFilter);
    var body = rows.length ? rows.map(function (l) {
      var badge = l.is_physically_inspected ? '<span class="text-[10px] font-black px-2 py-0.5 rounded-full bg-green-100 text-green-700 ml-1"><i class="fas fa-shield-halved"></i></span>' : '';
      var statusPill = {
        pending: 'bg-amber-100 text-amber-700',
        active: 'bg-green-100 text-green-700',
        rejected: 'bg-red-100 text-red-700',
      }[l.status] || 'bg-slate-100 text-slate-500';
      return '<tr class="hover:bg-slate-50 cursor-pointer lv-row" data-id="' + l.id + '">' +
        '<td class="data-td"><span class="font-bold text-slate-900">' + esc(l.title || 'Listing') + '</span>' + badge + '</td>' +
        '<td class="data-td text-slate-500">' + esc(l.owner_name || l.landlord_name || ('Owner ' + (l.owner_id || ''))) + '</td>' +
        '<td class="data-td font-bold text-[#ea580c]">' + money(l.price) + '</td>' +
        '<td class="data-td text-slate-500 hidden md:table-cell">' + esc(l.location || l.nearest_institution || '-') + '</td>' +
        '<td class="data-td text-slate-400 text-[12px]">' + fmtDate(l.created_at) + '</td>' +
        '<td class="data-td"><span class="pill ' + statusPill + '">' + esc(l.status || 'pending') + '</span></td>' +
        '</tr>';
    }).join('') : '<tr><td colspan="6" class="data-td text-center text-slate-400 py-10">No listings in this view.</td></tr>';

    host.innerHTML =
      '<div class="flex gap-2 px-5 py-3 flex-wrap">' + filters + '</div>' +
      '<div class="overflow-x-auto"><table class="w-full"><thead><tr>' +
        '<th class="data-th">Title</th><th class="data-th">Landlord</th><th class="data-th">Rent</th>' +
        '<th class="data-th hidden md:table-cell">Campus / Zone</th><th class="data-th">Submitted</th><th class="data-th">Status</th>' +
      '</tr></thead><tbody>' + body + '</tbody></table></div>';

    host.querySelectorAll('.lv-filter').forEach(function (b) { b.addEventListener('click', function () { _filter = b.getAttribute('data-f'); loadListingQueue(); }); });
    host.querySelectorAll('.lv-row').forEach(function (r) { r.addEventListener('click', function () { openInspector(r.getAttribute('data-id')); }); });
  }

  // ---- inspector modal ----
  function openInspector(id) {
    _current = _listings.find(function (l) { return String(l.id) === String(id); });
    if (!_current) return;
    var l = _current;
    var cover = l.cover_url || l.image_url || (l.media && l.media[0] && (l.media[0].url || l.media[0]));
    var coverHtml = cover ? '<img src="' + esc(cover) + '" class="w-full h-48 object-cover rounded-xl mb-4">' : '<div class="w-full h-48 bg-slate-100 rounded-xl mb-4 flex items-center justify-center text-slate-300"><i class="fas fa-house text-3xl"></i></div>';
    var inspected = !!l.is_physically_inspected;

    var modal = document.getElementById('lv-modal') || (function () {
      var m = document.createElement('div');
      m.id = 'lv-modal';
      m.className = 'fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-900/50';
      m.addEventListener('click', function (e) { if (e.target === m) m.remove(); });
      document.body.appendChild(m);
      return m;
    })();

    modal.innerHTML =
      '<div class="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">' +
        '<div class="px-5 py-4 border-b border-slate-100 flex items-center justify-between">' +
          '<h3 class="font-black text-slate-900">Listing review</h3>' +
          '<button onclick="document.getElementById(\'lv-modal\').remove()" class="w-8 h-8 rounded-lg hover:bg-slate-100 text-slate-500"><i class="fas fa-times"></i></button>' +
        '</div>' +
        '<div class="p-5">' +
          coverHtml +
          '<h4 class="font-black text-slate-900 text-lg">' + esc(l.title || 'Listing') + '</h4>' +
          '<p class="text-[#ea580c] font-black">' + money(l.price) + '<span class="text-slate-400 text-xs font-medium">/mo</span></p>' +
          '<p class="text-slate-500 text-sm mt-1"><i class="fas fa-location-dot mr-1 text-[#ea580c]"></i>' + esc(l.location || '-') + '</p>' +
          (l.nearest_institution ? '<p class="text-slate-400 text-[12px] mt-1">Near ' + esc(l.nearest_institution) + (l.distance_to_campus ? ' &middot; ' + esc(l.distance_to_campus) : '') + '</p>' : '') +
          (l.rejection_reason ? '<div class="mt-3 p-3 rounded-lg bg-red-50 border border-red-100 text-[13px] text-red-700"><strong>Previous rejection:</strong> ' + esc(l.rejection_reason) + '</div>' : '') +
          '<div class="mt-5 flex flex-wrap gap-2">' +
            '<button id="lv-approve" class="bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold px-4 py-2 rounded-lg"><i class="fas fa-check mr-1"></i>Approve</button>' +
            '<button id="lv-reject" class="bg-red-50 hover:bg-red-100 text-red-600 text-sm font-bold px-4 py-2 rounded-lg"><i class="fas fa-xmark mr-1"></i>Reject</button>' +
            '<button id="lv-inspect" class="' + (inspected ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600') + ' text-sm font-bold px-4 py-2 rounded-lg"><i class="fas fa-shield-halved mr-1"></i>' + (inspected ? 'Inspected' : 'Mark inspected') + '</button>' +
          '</div>' +
          '<div id="lv-reject-box" class="hidden mt-4 p-4 rounded-xl bg-slate-50 border border-slate-100">' +
            '<label class="block text-[11px] font-bold text-slate-500 uppercase mb-2">Rejection reason</label>' +
            '<select id="lv-reason" class="fmn-input w-full mb-2 text-sm">' +
              REJECT_REASONS.map(function (r) { return '<option value="' + esc(r) + '">' + esc(r) + '</option>'; }).join('') +
              '<option value="__custom">Other (type below)</option>' +
            '</select>' +
            '<input id="lv-reason-custom" class="fmn-input w-full text-sm mb-3 hidden" placeholder="Custom reason...">' +
            '<button id="lv-reject-confirm" class="bg-red-600 hover:bg-red-700 text-white text-sm font-bold px-4 py-2 rounded-lg">Confirm rejection &amp; notify landlord</button>' +
          '</div>' +
        '</div>' +
      '</div>';

    document.getElementById('lv-approve').addEventListener('click', function () { doAction('approve'); });
    document.getElementById('lv-inspect').addEventListener('click', function () { doAction('inspect'); });
    document.getElementById('lv-reject').addEventListener('click', function () { document.getElementById('lv-reject-box').classList.toggle('hidden'); });
    document.getElementById('lv-reason').addEventListener('change', function () {
      document.getElementById('lv-reason-custom').classList.toggle('hidden', this.value !== '__custom');
    });
    document.getElementById('lv-reject-confirm').addEventListener('click', function () {
      var sel = document.getElementById('lv-reason').value;
      var reason = sel === '__custom' ? (document.getElementById('lv-reason-custom').value || '').trim() : sel;
      if (!reason) { toast('Please provide a rejection reason.', 'error'); return; }
      doAction('reject', reason);
    });
  }

  async function doAction(kind, reason) {
    if (!_current) return;
    var id = _current.id;
    var url, opts = { method: 'PATCH', headers: { 'Content-Type': 'application/json' } };
    if (kind === 'approve') url = apiBase() + '/admin/listings/' + id + '/approve';
    else if (kind === 'reject') { url = apiBase() + '/admin/listings/' + id + '/reject'; opts.body = JSON.stringify({ reason: reason }); }
    else if (kind === 'inspect') url = apiBase() + '/admin/listings/' + id + '/inspect-badge';
    else return;

    try {
      var res = await fetch(url, opts);
      if (!res.ok) { var e = await res.json().catch(function () { return {}; }); throw new Error(typeof e.detail === 'string' ? e.detail : 'HTTP ' + res.status); }
      if (kind === 'approve') toast('Listing approved and now live.', 'success');
      else if (kind === 'reject') toast('Listing rejected. Landlord notified.', 'success');
      else toast('Inspection badge updated.', 'success');
      var m = document.getElementById('lv-modal'); if (m) m.remove();
      loadListingQueue();
    } catch (err) {
      toast('Action failed: ' + err.message, 'error');
    }
  }
})();
