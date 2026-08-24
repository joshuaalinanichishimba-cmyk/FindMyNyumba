/* ============================================================
   FindMyNyumba - Student "Is this price fair?" control (Stage 2)
   Outlined pill under the price. Logged-in students only.
   Posts to /listings/{id}/price-review.

   Distinct from the general Report flow: a report flags a dishonest
   listing; a price review contributes structured market data that feeds
   the listing's price confidence.

   Install: add ONE line before </body> in listing.html:
     <script src="fmn-price-concern.js"></script>
============================================================= */
(function () {
  'use strict';

  function apiBase() {
    if (typeof API_BASE !== 'undefined' && API_BASE) return API_BASE;
    if (typeof API !== 'undefined' && API) return API;
    var host = window.location.hostname;
    var local = (host === 'localhost' || host === '127.0.0.1' || host === '');
    return (local ? 'http://127.0.0.1:8000' : 'https://findmynyumba.onrender.com') + '/api/v1';
  }
  function getToken() {
    try { return localStorage.getItem('token') || sessionStorage.getItem('token'); }
    catch (e) { return null; }
  }
  function getRole() {
    try { return (localStorage.getItem('role') || sessionStorage.getItem('role') || '').toLowerCase(); }
    catch (e) { return ''; }
  }
  function listingId() {
    var m = new URLSearchParams(window.location.search).get('id');
    return m ? parseInt(m, 10) : null;
  }

  function injectCss() {
    if (document.getElementById('fmnpc-style')) return;
    var css = [
      "#fmnpc-link{display:inline-flex;align-items:center;gap:8px;margin-top:12px;font-size:13.5px;font-weight:700;color:#fff;background:#ea580c;border:none;border-radius:12px;cursor:pointer;padding:11px 18px;font-family:inherit;transition:all .15s;box-shadow:0 2px 8px rgba(234,88,12,.28);-webkit-appearance:none;appearance:none}",
      "#fmnpc-link i{font-size:14px;color:#fff}",
      "#fmnpc-link:hover{background:#c2410c;box-shadow:0 4px 12px rgba(234,88,12,.36)}",
      "#fmnpc-link:active{transform:translateY(1px)}",
      ".fmnpc-overlay{position:fixed;inset:0;background:rgba(15,23,42,.5);display:none;align-items:center;justify-content:center;padding:16px;z-index:9999;font-family:'Plus Jakarta Sans',system-ui,-apple-system,sans-serif}",
      ".fmnpc-overlay.open{display:flex}",
      ".fmnpc-modal{background:#fff;border-radius:16px;padding:22px;width:100%;max-width:440px;max-height:92vh;overflow:auto;box-shadow:0 25px 50px -12px rgba(0,0,0,.35)}",
      ".fmnpc-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px}",
      ".fmnpc-top h3{font-size:17px;font-weight:800;color:#0f172a;margin:0}",
      ".fmnpc-x{width:34px;height:34px;border-radius:10px;border:none;background:transparent;color:#64748b;cursor:pointer;font-size:15px}",
      ".fmnpc-x:hover{background:#f1f5f9}",
      ".fmnpc-sub{font-size:12.5px;color:#64748b;margin:0 0 16px;line-height:1.5}",
      ".fmnpc-label{display:block;font-size:12px;font-weight:700;color:#475569;margin:0 0 7px}",
      ".fmnpc-types{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px}",
      ".fmnpc-type{border:1.5px solid #e5e7eb;border-radius:11px;padding:11px 12px;cursor:pointer;text-align:left;background:#fff;transition:all .15s}",
      ".fmnpc-type.sel{border-color:#ea580c;background:#fff7ed}",
      ".fmnpc-type-t{display:block;font-size:13px;font-weight:700;color:#0f172a}",
      ".fmnpc-type-d{display:block;font-size:10.5px;color:#94a3b8;margin-top:1px}",
      ".fmnpc-in{width:100%;padding:10px 13px;border:1.5px solid #e5e7eb;border-radius:11px;font-size:14px;font-family:inherit;outline:none;margin-bottom:16px;box-sizing:border-box}",
      ".fmnpc-in:focus{border-color:#ea580c;box-shadow:0 0 0 3px rgba(234,88,12,.12)}",
      "textarea.fmnpc-in{resize:vertical}",
      ".fmnpc-amt-wrap{margin-bottom:16px}",
      ".fmnpc-amt-wrap.hide{display:none}",
      ".fmnpc-err{display:none;font-size:12.5px;font-weight:600;color:#dc2626;background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:9px 12px;margin-bottom:14px}",
      ".fmnpc-err.show{display:block}",
      ".fmnpc-ok{text-align:center;padding:12px 0 4px}",
      ".fmnpc-ok i{font-size:34px;color:#16a34a;margin-bottom:10px}",
      ".fmnpc-ok p{font-size:14px;color:#0f172a;font-weight:600;margin:0 0 4px}",
      ".fmnpc-ok span{font-size:12.5px;color:#64748b}",
      ".fmnpc-acts{display:flex;gap:10px;justify-content:flex-end;margin-top:4px}",
      ".fmnpc-btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;font-weight:700;border-radius:11px;cursor:pointer;border:none;font-size:13px;padding:10px 16px;font-family:inherit}",
      ".fmnpc-btn-pri{background:#ea580c;color:#fff}.fmnpc-btn-pri:hover{background:#c2410c}",
      ".fmnpc-btn-ghost{background:#fff;color:#334155;border:1.5px solid #e5e7eb}.fmnpc-btn-ghost:hover{background:#f8fafc}"
    ].join("");
    var s = document.createElement('style');
    s.id = 'fmnpc-style';
    s.textContent = css;
    document.head.appendChild(s);
  }

  var TYPES = [
    { key: 'too_high', t: 'Too high', d: 'Above the going rate', amount: true },
    { key: 'too_low', t: 'Too low', d: 'Suspiciously cheap', amount: true },
    { key: 'paid_different', t: 'I paid different', d: 'The real rent differs', amount: true },
    { key: 'confirmed_accurate', t: 'Looks accurate', d: 'This price is right', amount: false }
  ];
  var _sel = null;

  function addLink(tries) {
    if (!getToken() || getRole() !== 'student') return;
    var priceEl = document.getElementById('prop-price');
    if (!priceEl) { if (tries > 0) setTimeout(function () { addLink(tries - 1); }, 300); return; }
    if (document.getElementById('fmnpc-link')) return;

    injectCss();
    var link = document.createElement('button');
    link.id = 'fmnpc-link';
    link.type = 'button';
    link.innerHTML = '<i class="fas fa-scale-balanced"></i>Is this price fair?';
    link.onclick = openConcern;
    priceEl.parentNode.insertBefore(link, priceEl.nextSibling);
  }

  window.openConcern = function () {
    if (!getToken()) { window.location.href = 'login.html'; return; }
    _sel = null;
    document.getElementById('fmnpc-err').classList.remove('show');
    document.getElementById('fmnpc-form').style.display = '';
    document.getElementById('fmnpc-done').style.display = 'none';
    document.getElementById('fmnpc-foot').style.display = '';
    document.getElementById('fmnpc-amount').value = '';
    document.getElementById('fmnpc-note').value = '';
    renderTypes();
    syncAmount();
    document.getElementById('fmnpc-modal').classList.add('open');
  };
  window.closeConcern = function () { document.getElementById('fmnpc-modal').classList.remove('open'); };

  window.pcPick = function (key) { _sel = key; renderTypes(); syncAmount(); };

  function renderTypes() {
    document.querySelectorAll('#fmnpc-types .fmnpc-type').forEach(function (el) {
      el.classList.toggle('sel', el.dataset.k === _sel);
    });
  }
  function syncAmount() {
    var t = TYPES.find(function (x) { return x.key === _sel; });
    var needsAmount = !t || t.amount;
    document.getElementById('fmnpc-amt-wrap').classList.toggle('hide', !needsAmount);
  }

  window.submitConcern = async function () {
    var err = document.getElementById('fmnpc-err');
    err.classList.remove('show');
    function fail(m) { err.textContent = m; err.classList.add('show'); }

    if (!_sel) { fail('Please choose what the concern is.'); return; }
    var t = TYPES.find(function (x) { return x.key === _sel; });
    var amount = null;
    if (t.amount) {
      var raw = document.getElementById('fmnpc-amount').value.trim();
      amount = Number(raw);
      if (raw === '' || isNaN(amount) || amount < 0) {
        fail('Please enter the rent amount you are reporting.'); return;
      }
    }
    var note = document.getElementById('fmnpc-note').value.trim();

    var btn = document.getElementById('fmnpc-submit');
    btn.disabled = true; btn.textContent = 'Sending...';
    try {
      var r = await fetch(apiBase() + '/listings/' + listingId() + '/price-review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken() },
        body: JSON.stringify({ review_type: _sel, reported_price: amount, note: note || null })
      });
      var d = await r.json().catch(function () { return {}; });
      if (r.status === 401) { window.location.href = 'login.html'; return; }
      if (r.status === 409) { fail(d.detail || 'You already have a price review pending on this listing.'); return; }
      if (!r.ok) throw new Error(d.detail || ('HTTP ' + r.status));
      document.getElementById('fmnpc-form').style.display = 'none';
      document.getElementById('fmnpc-foot').style.display = 'none';
      document.getElementById('fmnpc-done').style.display = 'block';
    } catch (e) {
      fail(e.message || 'Could not send. Please try again.');
    } finally {
      btn.disabled = false; btn.textContent = 'Send';
    }
  };

  function buildModal() {
    if (document.getElementById('fmnpc-modal')) return;
    injectCss();
    var typeCards = TYPES.map(function (t) {
      return '<button type="button" class="fmnpc-type" data-k="' + t.key + '" onclick="pcPick(\'' + t.key + '\')">' +
        '<span class="fmnpc-type-t">' + t.t + '</span><span class="fmnpc-type-d">' + t.d + '</span></button>';
    }).join('');

    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div id="fmnpc-modal" class="fmnpc-overlay" onclick="if(event.target===this)closeConcern()">' +
        '<div class="fmnpc-modal">' +
          '<div class="fmnpc-top">' +
            '<h3>Is this price fair?</h3>' +
            '<button class="fmnpc-x" onclick="closeConcern()"><i class="fas fa-xmark"></i></button>' +
          '</div>' +
          '<div id="fmnpc-form">' +
            '<p class="fmnpc-sub">Your input helps other students judge listings. The landlord sets their own price and rent is always paid directly to them. This never changes the listed price.</p>' +
            '<div id="fmnpc-err" class="fmnpc-err"></div>' +
            '<label class="fmnpc-label">What is your view on the price?</label>' +
            '<div id="fmnpc-types" class="fmnpc-types">' + typeCards + '</div>' +
            '<div id="fmnpc-amt-wrap" class="fmnpc-amt-wrap">' +
              '<label class="fmnpc-label">What rent are you reporting? (K)</label>' +
              '<input id="fmnpc-amount" class="fmnpc-in" type="number" min="0" step="1" placeholder="e.g. 2000" inputmode="numeric">' +
            '</div>' +
            '<label class="fmnpc-label">Anything to add? <span style="font-weight:500;color:#94a3b8">(optional)</span></label>' +
            '<textarea id="fmnpc-note" class="fmnpc-in" rows="3" placeholder="e.g. a similar room two doors down goes for less"></textarea>' +
          '</div>' +
          '<div id="fmnpc-done" style="display:none">' +
            '<div class="fmnpc-ok"><i class="fas fa-circle-check"></i>' +
              '<p>Thank you</p><span>Our team will review this shortly.</span></div>' +
          '</div>' +
          '<div id="fmnpc-foot" class="fmnpc-acts">' +
            '<button class="fmnpc-btn fmnpc-btn-ghost" onclick="closeConcern()">Cancel</button>' +
            '<button id="fmnpc-submit" class="fmnpc-btn fmnpc-btn-pri" onclick="submitConcern()">Send</button>' +
          '</div>' +
        '</div>' +
      '</div>';
    while (wrap.firstChild) document.body.appendChild(wrap.firstChild);
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var m = document.getElementById('fmnpc-modal');
      if (m && m.classList.contains('open')) closeConcern();
    }
  });

  function start() { buildModal(); addLink(40); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
