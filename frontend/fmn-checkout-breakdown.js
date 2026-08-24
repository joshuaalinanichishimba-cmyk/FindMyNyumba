/* ============================================================
   FindMyNyumba - Stage 3: Checkout breakdown + operator detection
   Enhances Step 2 of pay-verified-access.html.

   Renders into #checkout-breakdown (already in the page) whenever a tier is
   selected, reading the FULL package object from the global PACKAGES array
   that loadPackages() already populates - nothing is hardcoded.

   Also adds live mobile-money operator detection to the #msisdn field,
   mirroring the backend detect_operator prefixes exactly.

   Install: add ONE line before </body> in pay-verified-access.html:
     <script src="fmn-checkout-breakdown.js"></script>
============================================================= */
(function () {
  'use strict';

  /* ---- prefixes must match backend lenco_service.detect_operator ---- */
  var OPERATORS = {
    '96': { name: 'MTN',    color: '#ffcc00', text: '#1a1a1a' },
    '76': { name: 'MTN',    color: '#ffcc00', text: '#1a1a1a' },
    '97': { name: 'Airtel', color: '#ed1c24', text: '#ffffff' },
    '77': { name: 'Airtel', color: '#ed1c24', text: '#ffffff' },
    '95': { name: 'Zamtel', color: '#009639', text: '#ffffff' },
    '75': { name: 'Zamtel', color: '#009639', text: '#ffffff' }
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }
  function pkgByCode(code) {
    if (typeof PACKAGES === 'undefined' || !PACKAGES) return null;
    for (var i = 0; i < PACKAGES.length; i++) {
      if (PACKAGES[i].code === code) return PACKAGES[i];
    }
    return null;
  }
  function fee(p) {
    var v = (p && (p.service_fee != null ? p.service_fee : p.price));
    return (v == null || isNaN(v)) ? 0 : Number(v);
  }
  function zmw(n) { return 'ZMW ' + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

  function injectCss() {
    if (document.getElementById('fmncb-style')) return;
    var css = [
      "#checkout-breakdown{margin:0 0 16px}",
      ".cb-card{border:1px solid #e2e8f0;border-radius:14px;overflow:hidden}",
      ".cb-head{background:#0F172A;padding:14px 16px;display:flex;align-items:center;justify-content:space-between;gap:8px}",
      ".cb-name{color:#fff;font-weight:800;font-size:14.5px}",
      ".cb-aud{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.05em;background:rgba(234,88,12,.9);color:#fff;padding:3px 8px;border-radius:99px}",
      ".cb-dur{padding:10px 16px;background:#fff7ed;border-bottom:1px solid #fee9d6;font-size:12.5px;font-weight:700;color:#9a3412;display:flex;align-items:center;gap:7px}",
      ".cb-dur i{color:#ea580c}",
      ".cb-feats{list-style:none;margin:0;padding:12px 16px;display:flex;flex-direction:column;gap:8px;border-bottom:1px solid #f1f5f9}",
      ".cb-feats li{display:flex;align-items:flex-start;gap:9px;font-size:12.5px;color:#334155}",
      ".cb-feats i{color:#16a34a;margin-top:2px;font-size:11px;flex-shrink:0}",
      ".cb-fin{padding:12px 16px}",
      ".cb-line{display:flex;justify-content:space-between;align-items:center;font-size:12.5px;padding:4px 0}",
      ".cb-line .lbl{color:#64748b}",
      ".cb-line .val{color:#334155;font-weight:600}",
      ".cb-line .val.inc{color:#16a34a;font-weight:700;font-size:11.5px}",
      ".cb-total{display:flex;justify-content:space-between;align-items:baseline;margin-top:8px;padding-top:10px;border-top:1.5px dashed #e2e8f0}",
      ".cb-total .lbl{font-size:13px;font-weight:800;color:#0f172a}",
      ".cb-total .val{font-size:19px;font-weight:800;color:#ea580c}",
      ".cb-disc{display:flex;align-items:flex-start;gap:8px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:10px 12px;margin-top:12px}",
      ".cb-disc i{color:#16a34a;font-size:12px;margin-top:2px;flex-shrink:0}",
      ".cb-disc p{margin:0;font-size:11.5px;color:#166534;line-height:1.5}",
      /* operator badge on the phone field */
      "#cb-operator{display:none;align-items:center;gap:6px;margin:6px 0 10px;font-size:12px;font-weight:700}",
      "#cb-operator.show{display:flex}",
      "#cb-operator .chip{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:99px;font-size:11px;font-weight:800}",
      "#cb-operator .switch{background:none;border:none;color:#ea580c;font-size:11.5px;font-weight:700;cursor:pointer;text-decoration:underline;font-family:inherit;padding:0}",
      "#cb-op-menu{display:none;gap:6px;margin:2px 0 10px}",
      "#cb-op-menu.show{display:flex}",
      "#cb-op-menu button{flex:1;border:1.5px solid #e2e8f0;background:#fff;border-radius:9px;padding:7px;font-size:11.5px;font-weight:700;cursor:pointer;font-family:inherit}",
      "#cb-op-menu button:hover{border-color:#ea580c}"
    ].join("");
    var s = document.createElement('style');
    s.id = 'fmncb-style';
    s.textContent = css;
    document.head.appendChild(s);
  }

  /* -------- breakdown render -------- */
  window.renderCheckoutBreakdown = function (code) {
    var box = document.getElementById('checkout-breakdown');
    if (!box) return;
    injectCss();

    var p = pkgByCode(code);
    if (!p) { box.innerHTML = ''; return; }

    var f = fee(p);
    var dur = p.duration_days || 0;
    var aud = (p.audience || 'student');
    var feats = (p.features && p.features.length) ? p.features : [];

    var featHtml = feats.length
      ? '<ul class="cb-feats">' + feats.map(function (x) {
          return '<li><i class="fas fa-check"></i>' + esc(x) + '</li>';
        }).join('') + '</ul>'
      : '';

    box.innerHTML =
      '<div class="cb-card">' +
        '<div class="cb-head">' +
          '<span class="cb-name">' + esc(p.name) + '</span>' +
          '<span class="cb-aud">' + esc(aud) + '</span>' +
        '</div>' +
        '<div class="cb-dur"><i class="fas fa-clock"></i>' + dur + ' Days Full Access</div>' +
        featHtml +
        '<div class="cb-fin">' +
          '<div class="cb-line"><span class="lbl">Service fee</span><span class="val">' + zmw(f) + '</span></div>' +
          '<div class="cb-line"><span class="lbl">Taxes &amp; charges</span><span class="val inc">K0.00 Included</span></div>' +
          '<div class="cb-total"><span class="lbl">Total due</span><span class="val">' + zmw(f) + '</span></div>' +
        '</div>' +
      '</div>' +
      '<div class="cb-disc"><i class="fas fa-circle-info"></i>' +
        '<p>The FindMyNyumba service fee is separate from monthly accommodation rent, which is payable directly to property landlords.</p>' +
      '</div>';
  };

  /* -------- operator detection on the phone field -------- */
  var _override = null;

  function detectOperator(rawValue) {
    var digits = String(rawValue || '').replace(/\D/g, '');
    // strip leading 0 or 260 to get the 9-digit local part starting with 9/7
    if (digits.indexOf('260') === 0) digits = digits.slice(3);
    if (digits.length === 10 && digits.charAt(0) === '0') digits = digits.slice(1);
    if (digits.length < 2) return null;
    // for a 9-digit number starting 9x/7x, prefix is first two digits
    var prefix = digits.slice(0, 2);
    return OPERATORS[prefix] || null;
  }

  function paintOperator(op) {
    var wrap = document.getElementById('cb-operator');
    if (!wrap) return;
    if (!op) { wrap.classList.remove('show'); return; }
    wrap.querySelector('.chip').style.background = op.color;
    wrap.querySelector('.chip').style.color = op.text;
    wrap.querySelector('.chip .nm').textContent = op.name;
    wrap.classList.add('show');
    try {
      var _val = op.name === 'Airtel' ? 'airtel_money' : (op.name === 'MTN' ? 'mtn_money' : null);
      if (_val) {
        var _r = document.querySelector('input[name=\"method\"][value=\"' + _val + '\"]');
        if (_r && !_r.disabled) { _r.checked = true; if (typeof syncMethodHighlight === "function") syncMethodHighlight(); }
      }
    } catch (e) {}
  }

  window.cbToggleOpMenu = function () {
    document.getElementById('cb-op-menu').classList.toggle('show');
  };
  window.cbPickOperator = function (name) {
    _override = name;
    var found = null;
    for (var k in OPERATORS) { if (OPERATORS[k].name === name) { found = OPERATORS[k]; break; } }
    paintOperator(found);
    document.getElementById('cb-op-menu').classList.remove('show');
  };

  function wireOperator(tries) {
    var input = document.getElementById('msisdn');
    if (!input) { if (tries > 0) setTimeout(function () { wireOperator(tries - 1); }, 300); return; }
    if (document.getElementById('cb-operator')) return;
    injectCss();

    // badge + override menu, inserted right after the phone input's row
    var badge = document.createElement('div');
    badge.id = 'cb-operator';
    badge.innerHTML =
      '<span style="color:#64748b">Network:</span>' +
      '<span class="chip"><i class="fas fa-mobile-screen"></i><span class="nm"></span></span>' +
      '<button type="button" class="switch" onclick="cbToggleOpMenu()">not right?</button>';
    var menu = document.createElement('div');
    menu.id = 'cb-op-menu';
    menu.innerHTML =
      '<button type="button" onclick="cbPickOperator(\'Airtel\')">Airtel</button>' +
      '<button type="button" onclick="cbPickOperator(\'MTN\')">MTN</button>' +
      '<button type="button" onclick="cbPickOperator(\'Zamtel\')">Zamtel</button>';

    // place after the msisdn error line if present, else after the input
    var errEl = document.getElementById('msisdn-err');
    var anchor = errEl || input;
    anchor.parentNode.insertBefore(badge, anchor.nextSibling);
    badge.parentNode.insertBefore(menu, badge.nextSibling);

    input.addEventListener('input', function () {
      _override = null;               // typing resets a manual override
      paintOperator(detectOperator(input.value));
    });
    // initial paint in case of prefilled value
    paintOperator(detectOperator(input.value));
  }

  function start() { wireOperator(40); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
  /* keep the visual "selected" state on whichever method radio is checked */
  function syncMethodHighlight() {
    var radios = document.querySelectorAll('input[name="method"]');
    radios.forEach(function (r) {
      var label = r.closest('label');
      if (!label) return;
      var on = r.checked && !r.disabled;
      label.classList.toggle('border-[#ea580c]', on);
      label.classList.toggle('border-2', on);
      label.classList.toggle('bg-orange-50/40', on);
      label.classList.toggle('border', !on);
      label.classList.toggle('border-slate-100', !on && r.disabled);
      label.classList.toggle('border-slate-200', !on && !r.disabled);
      var chk = label.querySelector('.fa-circle-check');
      if (chk) chk.style.display = on ? '' : 'none';
    });
  }
  document.addEventListener('change', function (e) {
    if (e.target && e.target.name === 'method') syncMethodHighlight();
  });
})();
