/* ============================================================
   FindMyNyumba - "Set verified price" add-on for the price review queue
   Loads AFTER fmn-price-review-admin.js. Adds a per-listing action on the
   Accepted tab: set FindMyNyumba's verified fair price (median pre-filled),
   shown alongside the landlord's asking price. Never overwrites price.

   Install: add ONE line after the queue include in admin.html:
     <script src="fmn-price-review-admin.js"></script>
     <script src="fmn-verified-price.js"></script>
============================================================= */
(function () {
  'use strict';

  function apiBase() {
    if (typeof API !== 'undefined' && API) return API;
    var host = window.location.hostname;
    var local = (host === 'localhost' || host === '127.0.0.1' || host === '');
    return (local ? 'http://127.0.0.1:8000' : 'https://findmynyumba.onrender.com') + '/api/v1';
  }
  function money(v) {
    if (v == null || isNaN(v)) return '\u2014';
    return 'K' + Number(v).toLocaleString();
  }

  function injectCss() {
    if (document.getElementById('fmnvp-style')) return;
    var css = [
      ".fmnvp-bar{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:10px 0 2px;padding:12px 14px;background:#f8fafc;border:1px solid #eef2f7;border-radius:12px}",
      ".fmnvp-two{display:flex;gap:20px;flex:1;min-width:180px}",
      ".fmnvp-l{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8;font-weight:700}",
      ".fmnvp-v{font-size:16px;font-weight:800;color:#0f172a;font-variant-numeric:tabular-nums}",
      ".fmnvp-v.vf{color:#16a34a}",
      ".fmnvp-v.none{color:#cbd5e1;font-weight:600;font-size:13px}",
      ".fmnvp-set{background:#ea580c;color:#fff;border:none;border-radius:10px;font-family:inherit;font-weight:700;font-size:12px;padding:8px 14px;cursor:pointer}",
      ".fmnvp-set:hover{background:#c2410c}",
      ".fmnvp-modal .fmnvp-sugg{font-size:12px;color:#64748b;margin:-8px 0 14px}",
      ".fmnvp-modal .fmnvp-sugg b{color:#ea580c}",
      ".fmnvp-clear{background:none;border:none;color:#dc2626;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;margin-right:auto}",
      ".fmnvp-clear:hover{text-decoration:underline}"
    ].join("");
    var s = document.createElement('style');
    s.id = 'fmnvp-style';
    s.textContent = css;
    document.head.appendChild(s);
  }

  var _detail = null;   // last loaded listing detail

  /* After the queue renders, add a verified-price bar to each accepted card. */
  function decorate() {
    var body = document.getElementById('pricereview-body');
    if (!body) return;
    // only meaningful on the Accepted tab
    var cards = body.querySelectorAll('.fmnpr-card');
    cards.forEach(function (card) {
      if (card.querySelector('.fmnvp-bar')) return;
      var link = card.querySelector('.fmnpr-lid a');
      if (!link) return;
      // only decorate accepted rows (they carry the status badge)
      if (!card.querySelector('.fmnpr-badge-status.accepted')) return;
      var m = link.getAttribute('href').match(/id=(\d+)/);
      if (!m) return;
      var lid = m[1];

      var bar = document.createElement('div');
      bar.className = 'fmnvp-bar';
      bar.dataset.listing = lid;
      bar.innerHTML =
        '<div class="fmnvp-two">' +
          '<div><div class="fmnvp-l">Landlord asking</div><div class="fmnvp-v" data-ask>\u2014</div></div>' +
          '<div><div class="fmnvp-l">FMN verified</div><div class="fmnvp-v vf" data-vf>loading\u2026</div></div>' +
        '</div>' +
        '<button class="fmnvp-set" onclick="vpOpen(' + lid + ')">Set verified price</button>';
      card.querySelector('.fmnpr-main').appendChild(bar);
      hydrate(lid, bar);
    });
  }

  async function hydrate(lid, bar) {
    try {
      var r = await fetch(apiBase() + '/admin/listings/' + lid + '/price-review-detail');
      if (!r.ok) return;
      var d = await r.json();
      bar.querySelector('[data-ask]').textContent = money(d.asking_price);
      var vf = bar.querySelector('[data-vf]');
      if (d.verified_market_price != null) {
        vf.textContent = money(d.verified_market_price);
        vf.classList.remove('none');
      } else {
        vf.textContent = 'Not set';
        vf.classList.add('none');
      }
    } catch (e) { /* leave placeholders */ }
  }

  window.vpOpen = async function (lid) {
    var r = await fetch(apiBase() + '/admin/listings/' + lid + '/price-review-detail');
    if (!r.ok) { if (typeof showToast === 'function') showToast('Could not load listing detail.'); return; }
    _detail = await r.json();
    _detail.listing_id = lid;

    document.getElementById('fmnvp-ask').textContent = money(_detail.asking_price);
    var sugg = document.getElementById('fmnvp-sugg');
    if (_detail.suggested_price != null) {
      sugg.innerHTML = 'Suggested from ' + _detail.based_on_priced_reviews +
        ' review(s): <b>' + money(_detail.suggested_price) + '</b>';
      sugg.style.display = '';
    } else {
      sugg.style.display = 'none';
    }
    var input = document.getElementById('fmnvp-input');
    input.value = _detail.verified_market_price != null
      ? _detail.verified_market_price
      : (_detail.suggested_price != null ? _detail.suggested_price : '');

    document.getElementById('fmnvp-clear').style.display =
      _detail.verified_market_price != null ? '' : 'none';
    document.getElementById('fmnvp-modal').classList.add('open');
  };
  window.vpClose = function () { document.getElementById('fmnvp-modal').classList.remove('open'); };

  window.vpClear = async function () { await vpSave(true); };

  window.vpSave = async function (clear) {
    var btn = document.getElementById('fmnvp-save');
    var val = null;
    if (!clear) {
      var raw = document.getElementById('fmnvp-input').value.trim();
      val = Number(raw);
      if (raw === '' || isNaN(val) || val < 0) {
        if (typeof showToast === 'function') showToast('Enter a valid amount.');
        return;
      }
    }
    btn.disabled = true;
    try {
      var r = await fetch(apiBase() + '/admin/listings/' + _detail.listing_id + '/verified-price', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ verified_market_price: val })
      });
      var d = await r.json().catch(function () { return {}; });
      if (!r.ok) throw new Error(d.detail || ('HTTP ' + r.status));
      vpClose();
      if (typeof showToast === 'function') {
        showToast(clear ? 'Verified price cleared.'
                        : 'Verified price set to ' + money(val) + '.');
      }
      if (typeof loadPriceReviews === 'function') loadPriceReviews();
    } catch (e) {
      if (typeof showToast === 'function') showToast(e.message || 'Could not save.');
    } finally {
      btn.disabled = false;
    }
  };

  function buildModal() {
    if (document.getElementById('fmnvp-modal')) return;
    injectCss();
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div id="fmnvp-modal" class="fmnpr-overlay" onclick="if(event.target===this)vpClose()">' +
        '<div class="fmnpr-modal fmnvp-modal">' +
          '<h3>Set verified price</h3>' +
          '<p>FindMyNyumba\u2019s fair price for this listing. Shown to students next to the landlord\u2019s price. This never changes the landlord\u2019s asking price.</p>' +
          '<div style="font-size:12px;color:#64748b;margin-bottom:10px">Landlord asking: <b id="fmnvp-ask">\u2014</b></div>' +
          '<label class="fmnpr-l" style="display:block;font-size:12px;font-weight:700;color:#475569;margin-bottom:6px">Verified fair price (K)</label>' +
          '<input id="fmnvp-input" type="number" min="0" step="1" ' +
            'style="width:100%;padding:10px 12px;border:1.5px solid #e5e7eb;border-radius:10px;font-family:inherit;font-size:14px;outline:none;margin-bottom:6px;box-sizing:border-box">' +
          '<p id="fmnvp-sugg" class="fmnvp-sugg"></p>' +
          '<div class="fmnpr-modal-acts">' +
            '<button id="fmnvp-clear" class="fmnvp-clear" onclick="vpClear()">Clear verified price</button>' +
            '<button class="fmnpr-btn fmnpr-view" onclick="vpClose()">Cancel</button>' +
            '<button id="fmnvp-save" class="fmnpr-btn fmnpr-accept" onclick="vpSave(false)">Save</button>' +
          '</div>' +
        '</div>' +
      '</div>';
    while (wrap.firstChild) document.body.appendChild(wrap.firstChild);
  }

  /* Watch the queue body; decorate accepted cards whenever it re-renders. */
  function watch(tries) {
    var body = document.getElementById('pricereview-body');
    if (!body) { if (tries > 0) setTimeout(function () { watch(tries - 1); }, 300); return; }
    injectCss();
    var obs = new MutationObserver(function () { setTimeout(decorate, 30); });
    obs.observe(body, { childList: true });
    decorate();
  }

  function start() { buildModal(); watch(40); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
