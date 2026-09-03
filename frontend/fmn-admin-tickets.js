/* ============================================================
   FindMyNyumba - Admin Support Tickets panel
   Renders submitted support tickets into #tickets-panel with status
   filters and inline resolve controls. Fetches GET /admin/support/tickets
   and updates via PATCH /admin/support/tickets/{id}. admin.html patches
   fetch to auto-inject the admin Bearer token.
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
  function toast(m, k) { if (typeof showToast === 'function') showToast(m, k || 'info'); }

  function fmtDate(iso) {
    if (!iso) return '';
    try { return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }); }
    catch (e) { return iso.slice(0, 10); }
  }
  function statusPill(s) {
    var m = {
      new: ['bg-amber-100 text-amber-700', 'New'],
      in_progress: ['bg-blue-100 text-blue-700', 'In progress'],
      resolved: ['bg-green-100 text-green-700', 'Resolved'],
      closed: ['bg-slate-100 text-slate-500', 'Closed'],
    }[s] || ['bg-slate-100 text-slate-500', s];
    return '<span class="text-[10px] font-black px-2.5 py-1 rounded-full ' + m[0] + '">' + esc(m[1]) + '</span>';
  }
  function catLabel(c) {
    return { connect: 'Verified Access', assist: 'Assisted Move', payment: 'Payment', general: 'General' }[c] || (c || '-');
  }

  var _tickets = [];
  var _filter = 'all';

  window.loadAdminTickets = function () {
  // loadSupport() also rewrites #tab-support innerHTML on tab open; defer so our
  // panel injects AFTER that, then again shortly after in case of slow render.
  setTimeout(_renderAdminTickets, 60);
  setTimeout(_renderAdminTickets, 400);
};
async function _renderAdminTickets() {
    var tab = document.getElementById('tab-support');
    if (!tab) return;
    var root = document.getElementById('tickets-panel');
    if (!root) {
      root = document.createElement('div');
      root.id = 'tickets-panel';
      root.className = 'mb-5';
      tab.insertBefore(root, tab.firstChild);
    } else if (root.parentNode !== tab) {
      tab.insertBefore(root, tab.firstChild);
    }
    root.innerHTML = '<div class="card p-5"><p class="text-sm text-slate-400"><i class="fas fa-circle-notch fa-spin mr-2"></i>Loading support tickets...</p></div>';
    try {
      var res = await fetch(apiBase() + '/admin/support/tickets');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var d = await res.json();
      _tickets = d.tickets || [];
      render(root);
    } catch (e) {
      root.innerHTML = '<div class="card p-5"><p class="text-sm text-red-500">Could not load support tickets (' + esc(e.message) + ').</p></div>';
    }
  };

  function render(root) {
    var counts = { all: _tickets.length, new: 0, in_progress: 0, resolved: 0 };
    _tickets.forEach(function (t) { if (counts[t.status] != null) counts[t.status]++; });

    var filters = [['all', 'All'], ['new', 'New'], ['in_progress', 'In progress'], ['resolved', 'Resolved']].map(function (f) {
      var active = _filter === f[0];
      return '<button type="button" class="tk-filter px-3 py-1.5 rounded-full text-[12px] font-bold ' +
        (active ? 'bg-[#ea580c] text-white' : 'bg-white border border-slate-200 text-slate-600 hover:border-[#ea580c]') +
        '" data-f="' + f[0] + '">' + f[1] + (counts[f[0]] != null ? ' (' + counts[f[0]] + ')' : '') + '</button>';
    }).join('');

    var rows = _tickets.filter(function (t) { return _filter === 'all' || t.status === _filter; });

    var body = rows.length ? rows.map(function (t) {
      return '' +
        '<div class="border-b border-slate-100 last:border-0" data-id="' + t.id + '">' +
          '<div class="flex items-center gap-3 px-4 py-3 cursor-pointer tk-row hover:bg-slate-50">' +
            '<div class="flex-1 min-w-0">' +
              '<div class="flex items-center gap-2 flex-wrap">' +
                '<span class="font-black text-slate-900 text-sm">' + esc(t.subject) + '</span>' +
                statusPill(t.status) +
              '</div>' +
              '<p class="text-[11px] text-slate-400 mt-0.5">' + esc(t.ticket_id) + ' &middot; ' + esc(catLabel(t.category)) + ' &middot; ' + esc(t.user_type || '-') + ' &middot; ' + fmtDate(t.created_at) + '</p>' +
            '</div>' +
            '<i class="fas fa-chevron-down text-slate-300 text-xs tk-chev"></i>' +
          '</div>' +
          '<div class="tk-detail hidden px-4 pb-4">' +
            '<div class="bg-slate-50 rounded-xl p-4 text-sm">' +
              '<p class="text-slate-700 whitespace-pre-wrap mb-3">' + esc(t.message) + '</p>' +
              '<div class="flex flex-wrap gap-4 text-[12px] text-slate-500 mb-4">' +
                (t.email ? '<span><i class="fas fa-envelope mr-1 text-slate-400"></i>' + esc(t.email) + '</span>' : '') +
                (t.reference_id ? '<span><i class="fas fa-hashtag mr-1 text-slate-400"></i>' + esc(t.reference_id) + '</span>' : '') +
              '</div>' +
              '<div class="flex flex-wrap items-end gap-3">' +
                '<div>' +
                  '<label class="block text-[11px] font-bold text-slate-500 uppercase mb-1">Status</label>' +
                  '<select class="tk-status fmn-input w-auto text-sm">' +
                    ['new', 'in_progress', 'resolved', 'closed'].map(function (s) {
                      return '<option value="' + s + '"' + (t.status === s ? ' selected' : '') + '>' + statusText(s) + '</option>';
                    }).join('') +
                  '</select>' +
                '</div>' +
                '<div class="flex-1 min-w-[200px]">' +
                  '<label class="block text-[11px] font-bold text-slate-500 uppercase mb-1">Resolution note (emailed to submitter)</label>' +
                  '<input type="text" class="tk-note fmn-input w-full text-sm" placeholder="Optional note..." value="' + esc(t.resolution_note || '') + '">' +
                '</div>' +
                '<button type="button" class="tk-save bg-[#ea580c] hover:bg-[#c2410c] text-white text-xs font-bold px-4 py-2 rounded-lg">Save</button>' +
              '</div>' +
            '</div>' +
          '</div>' +
        '</div>';
    }).join('') : '<div class="px-4 py-10 text-center text-slate-400 text-sm">No tickets in this view.</div>';

    root.innerHTML =
      '<div class="card overflow-hidden">' +
        '<div class="px-5 py-4 border-b border-slate-100 flex flex-wrap items-center gap-2.5">' +
          '<div class="mr-auto"><h3 class="font-extrabold text-slate-900 text-[15px]">Support Tickets</h3>' +
          '<p class="text-[12px] text-slate-400 font-medium">Submitted from the Help Center</p></div>' +
          filters +
        '</div>' +
        '<div>' + body + '</div>' +
      '</div>';

    wire(root);
  }

  function statusText(s) {
    return { new: 'New', in_progress: 'In progress', resolved: 'Resolved', closed: 'Closed' }[s] || s;
  }

  function wire(root) {
    root.querySelectorAll('.tk-filter').forEach(function (b) {
      b.addEventListener('click', function () { _filter = b.getAttribute('data-f'); render(root); });
    });
    root.querySelectorAll('.tk-row').forEach(function (row) {
      row.addEventListener('click', function () {
        var det = row.parentNode.querySelector('.tk-detail');
        var chev = row.querySelector('.tk-chev');
        if (det) det.classList.toggle('hidden');
        if (chev) chev.classList.toggle('fa-rotate-180');
      });
    });
    root.querySelectorAll('.tk-save').forEach(function (btn) {
      btn.addEventListener('click', function () { saveTicket(btn.closest('[data-id]'), btn); });
    });
  }

  async function saveTicket(wrap, btn) {
    var id = wrap.getAttribute('data-id');
    var status = wrap.querySelector('.tk-status').value;
    var note = wrap.querySelector('.tk-note').value.trim();
    var old = btn.textContent;
    btn.disabled = true; btn.textContent = 'Saving...';
    try {
      var res = await fetch(apiBase() + '/admin/support/tickets/' + id, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: status, resolution_note: note }),
      });
      if (!res.ok) {
        var e = await res.json().catch(function () { return {}; });
        throw new Error(typeof e.detail === 'string' ? e.detail : 'HTTP ' + res.status);
      }
      toast('Ticket updated.', 'success');
      loadAdminTickets();
    } catch (e) {
      toast('Update failed: ' + e.message, 'error');
    } finally {
      btn.disabled = false; btn.textContent = old;
    }
  }
})();
