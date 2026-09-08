/* ============================================================
   FindMyNyumba - floating support widget
   A fixed chat bubble (bottom-right) that opens a small panel where a
   visitor can send a support message. Posts to POST /support/tickets
   (public - works logged in or not) and shows the ticket ID to track.

   Include once on any public page, before </body>:
     <script src="fmn-support-widget.js"></script>
   Self-injects its own markup and styles; no other setup needed.
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

  // avoid double-injection
  if (document.getElementById('fmn-support-widget')) return;

  var wrap = document.createElement('div');
  wrap.id = 'fmn-support-widget';
  wrap.innerHTML =
    '<button id="fmn-sw-toggle" aria-label="Get help" ' +
      'style="position:fixed;bottom:20px;right:20px;z-index:60;width:56px;height:56px;border-radius:9999px;border:0;cursor:pointer;background:#ea580c;color:#fff;box-shadow:0 6px 20px rgba(0,0,0,.18);font-size:22px;display:flex;align-items:center;justify-content:center;">' +
      '<i class="fas fa-headset"></i></button>' +
    '<div id="fmn-sw-panel" ' +
      'style="position:fixed;bottom:88px;right:20px;z-index:60;width:340px;max-width:calc(100vw - 40px);background:#fff;border-radius:18px;box-shadow:0 12px 40px rgba(0,0,0,.22);overflow:hidden;display:none;">' +
      '<div style="background:#0f172a;color:#fff;padding:16px 18px;">' +
        '<p style="margin:0;font-weight:800;font-size:15px;">Need help?</p>' +
        '<p style="margin:2px 0 0;color:#94a3b8;font-size:12px;">Send us a message and we\'ll get back to you.</p>' +
      '</div>' +
      '<div id="fmn-sw-body" style="padding:16px 18px;">' +
        '<div id="fmn-sw-ok" style="display:none;background:#f0fdf4;border:1px solid #bbf7d0;color:#166534;border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:10px;"></div>' +
        '<div id="fmn-sw-err" style="display:none;background:#fef2f2;border:1px solid #fecaca;color:#b91c1c;border-radius:10px;padding:10px 12px;font-size:13px;margin-bottom:10px;"></div>' +
        '<input id="fmn-sw-email" type="email" placeholder="Your email (so we can reply)" ' +
          'style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #e2e8f0;border-radius:10px;font-size:13px;margin-bottom:8px;">' +
        '<textarea id="fmn-sw-msg" rows="3" placeholder="How can we help?" ' +
          'style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #e2e8f0;border-radius:10px;font-size:13px;resize:none;margin-bottom:10px;"></textarea>' +
        '<button id="fmn-sw-send" ' +
          'style="width:100%;background:#ea580c;color:#fff;border:0;border-radius:10px;padding:10px;font-weight:700;font-size:13px;cursor:pointer;">Send message</button>' +
        '<p style="margin:10px 0 0;color:#94a3b8;font-size:11px;">Never pay rent before inspecting a property in person.</p>' +
      '</div>' +
    '</div>';
  document.body.appendChild(wrap);

  var toggle = document.getElementById('fmn-sw-toggle');
  var panel = document.getElementById('fmn-sw-panel');
  var okBox = document.getElementById('fmn-sw-ok');
  var errBox = document.getElementById('fmn-sw-err');
  var sendBtn = document.getElementById('fmn-sw-send');

  toggle.addEventListener('click', function () {
    var open = panel.style.display === 'block';
    panel.style.display = open ? 'none' : 'block';
    toggle.innerHTML = open ? '<i class="fas fa-headset"></i>' : '<i class="fas fa-times"></i>';
  });

  sendBtn.addEventListener('click', async function () {
    okBox.style.display = 'none'; errBox.style.display = 'none';
    var email = (document.getElementById('fmn-sw-email').value || '').trim();
    var msg = (document.getElementById('fmn-sw-msg').value || '').trim();
    if (msg.length < 5) { errBox.textContent = 'Please type a short message (at least 5 characters).'; errBox.style.display = 'block'; return; }
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { errBox.textContent = 'Please enter a valid email, or leave it blank.'; errBox.style.display = 'block'; return; }

    var orig = sendBtn.textContent;
    sendBtn.disabled = true; sendBtn.textContent = 'Sending...';
    try {
      var res = await fetch(apiBase() + '/support/tickets', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject: 'Help widget message', message: msg, email: email, category: 'general' }),
      });
      var d = await res.json().catch(function () { return {}; });
      if (!res.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Could not send. Please try again.');
      okBox.innerHTML = 'Message sent. Your ticket ID is <b>' + esc(d.ticket_id) + '</b> - track it on the Help Center.';
      okBox.style.display = 'block';
      document.getElementById('fmn-sw-msg').value = '';
    } catch (e) {
      errBox.textContent = e.message; errBox.style.display = 'block';
    } finally {
      sendBtn.disabled = false; sendBtn.textContent = orig;
    }
  });
})();
