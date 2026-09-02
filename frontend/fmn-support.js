/* ============================================================
   FindMyNyumba - support ticket form + tracker (help.html)
   Submits to POST /support/tickets, tracks via GET /support/tickets/{id}.
   Client validation, loading state, error handling per spec.
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
  function show(el) { if (el) el.classList.remove('hidden'); }
  function hide(el) { if (el) el.classList.add('hidden'); }

  function statusLabel(s) {
    return { new: 'New', in_progress: 'In progress', resolved: 'Resolved', closed: 'Closed' }[s] || s;
  }
  function statusColor(s) {
    return {
      new: 'background:#fef3c7;color:#92400e;',
      in_progress: 'background:#dbeafe;color:#1e40af;',
      resolved: 'background:#dcfce7;color:#166534;',
      closed: 'background:#f1f5f9;color:#475569;',
    }[s] || 'background:#f1f5f9;color:#475569;';
  }

  // ── Submit ticket ──────────────────────────────────────────
  var submitBtn = document.getElementById('tk-submit');
  if (submitBtn) submitBtn.addEventListener('click', async function () {
    var okBox = document.getElementById('ticket-success');
    var errBox = document.getElementById('ticket-error');
    hide(okBox); hide(errBox);

    var subject = (document.getElementById('tk-subject').value || '').trim();
    var message = (document.getElementById('tk-message').value || '').trim();
    var email   = (document.getElementById('tk-email').value || '').trim();

    // client-side validation
    if (subject.length < 3) { errBox.textContent = 'Please enter a subject (at least 3 characters).'; show(errBox); return; }
    if (message.length < 5) { errBox.textContent = 'Please describe your issue (at least 5 characters).'; show(errBox); return; }
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { errBox.textContent = 'Please enter a valid email address, or leave it blank.'; show(errBox); return; }

    var body = {
      subject: subject,
      message: message,
      user_type: document.getElementById('tk-usertype').value,
      category: document.getElementById('tk-category').value,
      reference_id: (document.getElementById('tk-reference').value || '').trim(),
      email: email,
    };

    var original = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Submitting...';
    try {
      var res = await fetch(apiBase() + '/support/tickets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      var d = await res.json().catch(function () { return {}; });
      if (!res.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Could not submit your ticket.');

      okBox.innerHTML = '<i class="fas fa-circle-check mr-1"></i> Ticket submitted. Your ticket ID is <span class="font-black">' + esc(d.ticket_id) + '</span> - save it to track your request.';
      show(okBox);
      // clear the form
      ['tk-subject', 'tk-message', 'tk-email', 'tk-reference'].forEach(function (id) {
        var el = document.getElementById(id); if (el) el.value = '';
      });
    } catch (e) {
      errBox.textContent = e.message;
      show(errBox);
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = original;
    }
  });

  // ── Track ticket ───────────────────────────────────────────
  var trackBtn = document.getElementById('track-btn');
  if (trackBtn) trackBtn.addEventListener('click', async function () {
    var out = document.getElementById('track-result');
    var id = (document.getElementById('track-id').value || '').trim().toUpperCase();
    if (!id) { out.innerHTML = '<span class="text-slate-300">Enter a ticket ID above.</span>'; show(out); return; }

    out.innerHTML = '<span class="text-slate-300"><i class="fas fa-circle-notch fa-spin"></i> Checking...</span>';
    show(out);
    try {
      var res = await fetch(apiBase() + '/support/tickets/' + encodeURIComponent(id));
      if (res.status === 404) { out.innerHTML = '<span class="text-slate-300">No ticket found with that ID. Check it and try again.</span>'; return; }
      if (!res.ok) throw new Error('Could not check the ticket right now.');
      var d = await res.json();
      var note = d.resolution_note ? '<p class="text-slate-300 mt-2">' + esc(d.resolution_note) + '</p>' : '';
      out.innerHTML =
        '<p class="font-bold mb-1">' + esc(d.subject || d.ticket_id) + '</p>' +
        '<span style="display:inline-block;padding:2px 10px;border-radius:9999px;font-size:11px;font-weight:800;' + statusColor(d.status) + '">' + statusLabel(d.status) + '</span>' +
        note;
    } catch (e) {
      out.innerHTML = '<span class="text-slate-300">' + esc(e.message) + '</span>';
    }
  });
})();
