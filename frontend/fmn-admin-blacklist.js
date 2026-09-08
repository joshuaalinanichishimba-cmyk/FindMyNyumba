/* ============================================================
   FindMyNyumba - Admin Blacklist (Trust & Safety tab)
   Registry of blocked phones/accounts/emails. Add entries (auto-flags
   matching active listings) and revoke them.
     GET    /admin/trust/blacklist
     POST   /admin/trust/blacklist
     DELETE /admin/trust/blacklist/{id}
============================================================= */
(function () {
  'use strict';

  function apiBase() { return (typeof API === 'string' && API) ? API : (window.API || 'https://findmynyumba.onrender.com/api/v1'); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]; }); }
  function toast(m, k) { if (typeof showToast === 'function') showToast(m, k || 'info'); }
  function fmtDate(iso) { if (!iso) return '-'; try { return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }); } catch (e) { return String(iso).slice(0, 10); } }

  var _entries = [];

  window.loadBlacklist = async function () {
    var root = document.getElementById('blacklist-panel');
    if (!root) return;
    if (!root.dataset.built) { root.innerHTML = shell(); root.dataset.built = '1'; wireForm(root); }
    var tbody = document.getElementById('bl-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="data-td text-slate-400 text-sm py-6">Loading...</td></tr>';
    try {
      var res = await fetch(apiBase() + '/admin/trust/blacklist');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var d = await res.json();
      _entries = d.entries || [];
      renderRows();
    } catch (e) {
      if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="data-td text-red-500 text-sm py-6">Could not load blacklist (' + esc(e.message) + ').</td></tr>';
    }
  };

  function shell() {
    return '' +
      '<div class="card overflow-hidden">' +
        '<div class="px-5 py-4 border-b border-slate-100">' +
          '<h3 class="font-extrabold text-slate-900 text-[15px]">Blacklist</h3>' +
          '<p class="text-[12px] text-slate-400 font-medium">Blocked phone numbers, accounts and emails. Adding one auto-flags matching active listings.</p>' +
        '</div>' +
        '<div class="px-5 py-4 border-b border-slate-100 bg-slate-50/60">' +
          '<div class="grid sm:grid-cols-4 gap-2">' +
            '<select id="bl-type" class="fmn-input text-sm"><option value="phone">Phone</option><option value="account">Account</option><option value="email">Email</option></select>' +
            '<input id="bl-value" class="fmn-input text-sm" placeholder="Value (number / account / email)">' +
            '<input id="bl-reason" class="fmn-input text-sm" placeholder="Reason (optional)">' +
            '<button id="bl-add" class="btn btn-pri text-sm"><i class="fas fa-ban mr-1"></i>Add to blacklist</button>' +
          '</div>' +
          '<input id="bl-note" class="fmn-input text-sm w-full mt-2" placeholder="Admin note (optional)">' +
        '</div>' +
        '<div class="overflow-x-auto"><table class="w-full"><thead><tr>' +
          '<th class="data-th">Type</th><th class="data-th">Value</th><th class="data-th">Reason</th><th class="data-th">Added</th><th class="data-th"></th>' +
        '</tr></thead><tbody id="bl-tbody"></tbody></table></div>' +
      '</div>';
  }

  function renderRows() {
    var tbody = document.getElementById('bl-tbody');
    if (!tbody) return;
    if (!_entries.length) { tbody.innerHTML = '<tr><td colspan="5" class="data-td text-slate-400 text-sm py-8 text-center">No blacklisted entries.</td></tr>'; return; }
    tbody.innerHTML = _entries.map(function (b) {
      return '<tr class="hover:bg-slate-50">' +
        '<td class="data-td"><span class="pill bg-slate-100 text-slate-600">' + esc(b.entity_type) + '</span></td>' +
        '<td class="data-td font-bold text-slate-900">' + esc(b.value) + '</td>' +
        '<td class="data-td text-slate-500 text-[13px]">' + esc(b.reason || '-') + '</td>' +
        '<td class="data-td text-slate-400 text-[12px]">' + fmtDate(b.created_at) + '</td>' +
        '<td class="data-td text-right"><button onclick="revokeBlacklist(' + b.id + ')" class="btn btn-ghost text-[12px] text-red-600">Revoke</button></td>' +
        '</tr>';
    }).join('');
  }

  function wireForm(root) {
    var addBtn = document.getElementById('bl-add');
    if (addBtn) addBtn.addEventListener('click', addEntry);
  }

  async function addEntry() {
    var type = document.getElementById('bl-type').value;
    var value = (document.getElementById('bl-value').value || '').trim();
    var reason = (document.getElementById('bl-reason').value || '').trim();
    var note = (document.getElementById('bl-note').value || '').trim();
    if (value.length < 3) { toast('Enter a value to blacklist.', 'error'); return; }
    var btn = document.getElementById('bl-add');
    var old = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i>';
    try {
      var res = await fetch(apiBase() + '/admin/trust/blacklist', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity_type: type, value: value, reason: reason, admin_note: note }),
      });
      var d = await res.json();
      if (!res.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'HTTP ' + res.status);
      var flagged = d.listings_flagged || 0;
      toast('Added to blacklist' + (flagged ? ' (' + flagged + ' listing' + (flagged === 1 ? '' : 's') + ' flagged)' : '') + '.', 'success');
      document.getElementById('bl-value').value = '';
      document.getElementById('bl-reason').value = '';
      document.getElementById('bl-note').value = '';
      loadBlacklist();
    } catch (e) {
      toast('Failed: ' + e.message, 'error');
    } finally { btn.disabled = false; btn.innerHTML = old; }
  }

  window.revokeBlacklist = async function (id) {
    if (typeof confirm === 'function' && !confirm('Revoke this blacklist entry?')) return;
    try {
      var res = await fetch(apiBase() + '/admin/trust/blacklist/' + id, { method: 'DELETE' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      toast('Blacklist entry revoked.', 'success');
      loadBlacklist();
    } catch (e) { toast('Revoke failed: ' + e.message, 'error'); }
  };
})();
