/* ============================================================
   FindMyNyumba - Service Fees: "New package" add-on
   Loads AFTER fmn-pricing-admin.js and adds package creation
   plus audience grouping. Wires to POST /admin/packages.

   Install: add ONE line after the existing include in admin.html:
     <script src="fmn-pricing-admin.js"></script>
     <script src="fmn-pricing-new.js"></script>
============================================================= */
(function () {
  'use strict';

  function apiBase() {
    if (typeof API !== 'undefined' && API) return API;
    var host = window.location.hostname;
    var local = (host === 'localhost' || host === '127.0.0.1' || host === '');
    return (local ? 'http://127.0.0.1:8000' : 'https://findmynyumba.onrender.com') + '/api/v1';
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }

  /* ---- extra styles for the audience group header + segmented control ---- */
  function injectCss() {
    if (document.getElementById('fmnp-new-style')) return;
    var css = [
      ".fmnp-group-label{grid-column:1/-1;display:flex;align-items:center;gap:10px;margin:6px 0 -4px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.07em;color:#94a3b8}",
      ".fmnp-group-label:before,.fmnp-group-label:after{content:'';height:1px;background:#eef2f7;flex:1}",
      ".fmnp-seg{display:flex;gap:8px;margin-bottom:16px}",
      ".fmnp-seg-opt{flex:1;border:1.5px solid #e5e7eb;border-radius:11px;padding:11px 12px;cursor:pointer;text-align:left;transition:all .15s;background:#fff}",
      ".fmnp-seg-opt.sel{border-color:#ea580c;background:#fff7ed}",
      ".fmnp-seg-t{display:block;font-size:13px;font-weight:700;color:#0f172a}",
      ".fmnp-seg-d{display:block;font-size:11px;color:#94a3b8;margin-top:1px}",
      ".fmnp-boost-note{margin:-8px 0 16px;font-size:11.5px;color:#b45309;background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:9px 12px;display:none}",
      ".fmnp-boost-note.show{display:block}"
    ].join("");
    var s = document.createElement('style');
    s.id = 'fmnp-new-style';
    s.textContent = css;
    document.head.appendChild(s);
  }

  /* ---- add the "New package" button into the panel header ---- */
  function addNewButton(tries) {
    var head = document.querySelector('#tab-pricing .fmnp-head-row');
    if (!head) { if (tries > 0) setTimeout(function () { addNewButton(tries - 1); }, 250); return; }
    if (document.getElementById('fmnp-new-btn')) return;
    var btn = document.createElement('button');
    btn.id = 'fmnp-new-btn';
    btn.className = 'fmnp-btn fmnp-btn-pri';
    btn.style.flex = 'none';
    btn.style.padding = '9px 16px';
    btn.innerHTML = '<i class="fas fa-plus"></i>New package';
    btn.setAttribute('onclick', 'openNewPackage()');
    // sits just before the Refresh button
    var refresh = head.querySelector('.fmnp-btn-ghost');
    if (refresh) head.insertBefore(btn, refresh);
    else head.appendChild(btn);
  }

  var _selAudience = 'student';
  var _selGrant = 'student_access';

  window.openNewPackage = function () {
    _selAudience = 'student';
    _selGrant = 'student_access';
    document.getElementById('pkgnew-err').classList.remove('show');
    ['code', 'name', 'fee', 'duration', 'features', 'desc'].forEach(function (f) {
      document.getElementById('pkgnew-' + f).value = '';
    });
    document.getElementById('pkgnew-currency').value = 'ZMW';
    syncAudienceUi();
    document.getElementById('pkgnew-modal').classList.add('open');
  };
  window.closeNewPackage = function () {
    document.getElementById('pkgnew-modal').classList.remove('open');
  };

  window.pkgnewPickAudience = function (aud) {
    _selAudience = aud;
    // sensible default grant per audience
    _selGrant = (aud === 'landlord') ? 'listing_boost' : 'student_access';
    syncAudienceUi();
  };

  function syncAudienceUi() {
    document.getElementById('pkgnew-aud-student').classList.toggle('sel', _selAudience === 'student');
    document.getElementById('pkgnew-aud-landlord').classList.toggle('sel', _selAudience === 'landlord');
    // boost note: landlord + listing_boost cannot be activated yet
    document.getElementById('pkgnew-boost-note').classList.toggle('show', _selGrant === 'listing_boost');
  }

  window.createPackage = async function () {
    var err = document.getElementById('pkgnew-err');
    var btn = document.getElementById('pkgnew-save');
    err.classList.remove('show');
    function fail(m) { err.textContent = m; err.classList.add('show'); }

    var code = document.getElementById('pkgnew-code').value.trim().toLowerCase();
    var name = document.getElementById('pkgnew-name').value.trim();
    var feeRaw = document.getElementById('pkgnew-fee').value.trim();
    var durRaw = document.getElementById('pkgnew-duration').value.trim();

    if (!/^[a-z][a-z0-9_]{1,48}$/.test(code)) {
      fail('Code must be lowercase letters, numbers and underscores, starting with a letter.'); return;
    }
    if (!name) { fail('Package name is required.'); return; }
    var fee = Number(feeRaw);
    if (feeRaw === '' || isNaN(fee) || fee < 0) { fail('Enter a valid fee (0 or more).'); return; }
    var dur = parseInt(durRaw, 10);
    if (isNaN(dur) || dur < 1) { fail('Duration must be at least 1 day.'); return; }

    var features = document.getElementById('pkgnew-features').value
      .split('\n').map(function (s) { return s.trim(); }).filter(Boolean);

    var payload = {
      code: code, name: name, service_fee: fee,
      currency: document.getElementById('pkgnew-currency').value.trim().toUpperCase() || 'ZMW',
      duration_days: dur,
      features: features,
      description: document.getElementById('pkgnew-desc').value.trim() || null,
      audience: _selAudience,
      grant_type: _selGrant,
      is_active: false           // always created inactive
    };

    btn.disabled = true; btn.textContent = 'Creating...';
    try {
      var r = await fetch(apiBase() + '/admin/packages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      var d = await r.json().catch(function () { return {}; });
      if (!r.ok) throw new Error(d.detail || ('HTTP ' + r.status));
      closeNewPackage();
      if (typeof showToast === 'function') showToast('Package created (inactive). Review, then activate.');
      if (typeof loadPricing === 'function') loadPricing();
    } catch (e) {
      fail(e.message || 'Could not create package. Try again.');
    } finally {
      btn.disabled = false; btn.textContent = 'Create package';
    }
  };

  function buildModal() {
    if (document.getElementById('pkgnew-modal')) return;
    injectCss();
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div id="pkgnew-modal" class="fmnp-overlay" onclick="if(event.target===this)closeNewPackage()">' +
        '<div class="fmnp-modal">' +
          '<div class="fmnp-modal-top">' +
            '<h3 class="fmnp-modal-title">New service package</h3>' +
            '<button class="fmnp-x" onclick="closeNewPackage()"><i class="fas fa-xmark"></i></button>' +
          '</div>' +
          '<p class="fmnp-modal-sub">Created inactive. Review the details, then activate it from its card.</p>' +
          '<div id="pkgnew-err" class="fmnp-err"></div>' +

          '<label class="fmnp-label">Who is this for?</label>' +
          '<div class="fmnp-seg">' +
            '<button type="button" id="pkgnew-aud-student" class="fmnp-seg-opt sel" onclick="pkgnewPickAudience(\'student\')">' +
              '<span class="fmnp-seg-t">Students</span><span class="fmnp-seg-d">Shows on the student payment page</span></button>' +
            '<button type="button" id="pkgnew-aud-landlord" class="fmnp-seg-opt" onclick="pkgnewPickAudience(\'landlord\')">' +
              '<span class="fmnp-seg-t">Landlords</span><span class="fmnp-seg-d">Future landlord offers</span></button>' +
          '</div>' +

          '<div id="pkgnew-boost-note" class="fmnp-boost-note">' +
            'Landlord boost packages can be created and priced now, but cannot be activated yet: purchase activation (featured placement) is not built. It will save as inactive.' +
          '</div>' +

          '<div class="fmnp-row2">' +
            '<div><label class="fmnp-label">Code <span class="muted">(permanent)</span></label>' +
              '<input id="pkgnew-code" class="fmnp-in" placeholder="e.g. fast_tenant"></div>' +
            '<div><label class="fmnp-label">Name</label>' +
              '<input id="pkgnew-name" class="fmnp-in" placeholder="e.g. Fast Tenant"></div>' +
          '</div>' +

          '<div class="fmnp-row2">' +
            '<div><label class="fmnp-label">Service fee</label>' +
              '<input id="pkgnew-fee" type="number" min="0" step="1" class="fmnp-in" placeholder="200"></div>' +
            '<div><label class="fmnp-label">Currency</label>' +
              '<input id="pkgnew-currency" class="fmnp-in" value="ZMW"></div>' +
          '</div>' +

          '<label class="fmnp-label">Duration (days)</label>' +
          '<input id="pkgnew-duration" type="number" min="1" step="1" class="fmnp-in" placeholder="30">' +

          '<label class="fmnp-label">Features (one per line)</label>' +
          '<textarea id="pkgnew-features" rows="4" class="fmnp-in" placeholder="One feature per line"></textarea>' +

          '<label class="fmnp-label">Description</label>' +
          '<textarea id="pkgnew-desc" rows="2" class="fmnp-in"></textarea>' +

          '<div class="fmnp-modal-actions">' +
            '<button class="fmnp-btn fmnp-btn-ghost" onclick="closeNewPackage()">Cancel</button>' +
            '<button id="pkgnew-save" class="fmnp-btn fmnp-btn-pri" style="flex:none;padding:9px 18px" onclick="createPackage()">Create package</button>' +
          '</div>' +
        '</div>' +
      '</div>';
    while (wrap.firstChild) document.body.appendChild(wrap.firstChild);
  }

  /* ---- wrap renderPricing to group by audience ---- */
  function installGrouping(tries) {
    if (typeof window.renderPricing === 'function') {
      // renderPricing is not global in the base file; fall back to observing
    }
    // The base file rebuilds #pricing-body on each load. We post-process it.
    var body = document.getElementById('pricing-body');
    if (!body) { if (tries > 0) setTimeout(function () { installGrouping(tries - 1); }, 300); return; }

    var obs = new MutationObserver(function () { groupByAudience(); });
    obs.observe(body, { childList: true });
    groupByAudience();
  }

  var _grouping = false;
  function groupByAudience() {
    if (_grouping) return;
    var body = document.getElementById('pricing-body');
    if (!body) return;
    var cards = Array.prototype.slice.call(body.querySelectorAll('.fmnp-card'));
    if (!cards.length) return;
    // Already grouped? bail (labels present)
    if (body.querySelector('.fmnp-group-label')) return;

    // Map each card to its package via the code shown in .fmnp-code
    var landlordCodes = (window._packages || [])
      .filter(function (p) { return (p.audience || 'student') === 'landlord'; })
      .map(function (p) { return String(p.code).toUpperCase(); });

    if (!landlordCodes.length) return; // nothing to group yet

    _grouping = true;
    var studentFrag = document.createDocumentFragment();
    var landlordFrag = document.createDocumentFragment();

    cards.forEach(function (card) {
      var codeEl = card.querySelector('.fmnp-code');
      var code = codeEl ? codeEl.textContent.trim().toUpperCase() : '';
      if (landlordCodes.indexOf(code) > -1) landlordFrag.appendChild(card);
      else studentFrag.appendChild(card);
    });

    body.innerHTML = '';
    var sLabel = document.createElement('div');
    sLabel.className = 'fmnp-group-label';
    sLabel.textContent = 'Student packages';
    body.appendChild(sLabel);
    body.appendChild(studentFrag);

    var lLabel = document.createElement('div');
    lLabel.className = 'fmnp-group-label';
    lLabel.textContent = 'Landlord packages';
    body.appendChild(lLabel);
    body.appendChild(landlordFrag);
    _grouping = false;
  }

  function start() {
    buildModal();
    addNewButton(40);
    installGrouping(40);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
