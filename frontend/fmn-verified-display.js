/* ============================================================
   FindMyNyumba - verified price display on the listing page (Stage 2)
   Shows a student-sourced fair-rent estimate beside the landlord's asking
   price. Read-only, visible to everyone. Makes clear the landlord's price
   is unchanged and rent is paid directly to them.

   Install: add ONE line before </body> in listing.html (after the concern one):
     <script src="fmn-price-concern.js"></script>
     <script src="fmn-verified-display.js"></script>
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
  function listingId() {
    var m = new URLSearchParams(window.location.search).get('id');
    return m ? parseInt(m, 10) : null;
  }
  function money(v) {
    if (v == null || isNaN(v)) return '';
    return 'K' + Number(v).toLocaleString();
  }

  function injectCss() {
    if (document.getElementById('fmnvd-style')) return;
    var css = [
      "#fmnvd-box{margin-top:10px;display:flex;align-items:flex-start;gap:9px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:12px;padding:11px 13px;max-width:380px}",
      "#fmnvd-box>i{color:#16a34a;font-size:15px;flex-shrink:0;margin-top:1px}",
      "#fmnvd-txt{font-size:12.5px;color:#166534;line-height:1.5}",
      "#fmnvd-txt .fmnvd-head{font-weight:800;display:block;margin-bottom:1px}",
      "#fmnvd-txt .fmnvd-amt{font-weight:800}",
      "#fmnvd-txt .fmnvd-sub{color:#4b5563;font-weight:500}",
      "#fmnvd-box .fmnvd-info{margin-left:auto;color:#16a34a;cursor:help;font-size:12px;flex-shrink:0;margin-top:1px}"
    ].join("");
    var s = document.createElement('style');
    s.id = 'fmnvd-style';
    s.textContent = css;
    document.head.appendChild(s);
  }

  async function run(tries) {
    var priceEl = document.getElementById('prop-price');
    if (!priceEl) { if (tries > 0) setTimeout(function () { run(tries - 1); }, 300); return; }
    var id = listingId();
    if (!id) return;

    try {
      var r = await fetch(apiBase() + '/listings/' + id + '/price-insight');
      if (!r.ok) return;
      var d = await r.json();
      if (d.verified_market_price == null) return;

      injectCss();
      if (document.getElementById('fmnvd-box')) return;

      var asking = d.price;
      var vf = d.verified_market_price;
      var rel = '';
      if (asking != null && vf != null) {
        if (vf < asking) rel = ' (below what this listing asks)';
        else if (vf > asking) rel = ' (above what this listing asks)';
        else rel = ' (in line with this listing)';
      }

      var box = document.createElement('div');
      box.id = 'fmnvd-box';
      box.innerHTML =
        '<i class="fas fa-users"></i>' +
        '<span id="fmnvd-txt">' +
          '<span class="fmnvd-head">Students suggest a fair rent near <span class="fmnvd-amt">' + money(vf) + '</span>' + rel + '</span>' +
          '<span class="fmnvd-sub">The landlord sets the listed price. Rent is always paid directly to them, never through FindMyNyumba.</span>' +
        '</span>' +
        '<i class="fas fa-circle-info fmnvd-info" title="This estimate comes from FindMyNyumba reviewing reports from students about similar places. It does not change the landlord\u2019s price."></i>';

      var concern = document.getElementById('fmnpc-link');
      var after = concern || priceEl;
      after.parentNode.insertBefore(box, after.nextSibling);
    } catch (e) { /* silent */ }
  }

  function start() { run(40); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
