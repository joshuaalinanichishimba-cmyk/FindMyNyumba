/* ============================================================
   FindMyNyumba - shared footer compliance script
   Include on every public page with a footer. It:
   1. Adds a "Refunds" link to the bottom legal bar (next to Terms/Privacy)
      if one isn't already there.
   2. Pulls support email / phone / legal business name from /site-settings
      so contact details stay current when edited in the admin dashboard.

   Safe to include anywhere: it only acts on elements it finds, and never
   throws if the footer shape differs.

   Include once, before </body>:
     <script src="fmn-footer.js"></script>
============================================================= */
(function () {
  'use strict';

  function apiBase() {
    return (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
      ? 'http://127.0.0.1:8000/api/v1'
      : 'https://findmynyumba.onrender.com/api/v1';
  }

  function ensureRefundsLink() {
    // the bottom legal bar is a small <div class="flex gap-4"> holding Terms/Privacy
    var termsLinks = Array.prototype.slice.call(document.querySelectorAll('a[href="terms.html"]'));
    termsLinks.forEach(function (t) {
      var bar = t.parentNode;
      if (!bar) return;
      // only act on the compact bottom bar (Terms + Privacy siblings), not the big columns
      var already = bar.querySelector('a[href="refunds.html"]');
      if (already) return;
      var privacy = bar.querySelector('a[href="privacy.html"]');
      // clone the styling of the Privacy link so it matches
      var ref = document.createElement('a');
      ref.href = 'refunds.html';
      ref.textContent = 'Refunds';
      if (privacy) { ref.className = privacy.className; privacy.parentNode.insertBefore(ref, privacy.nextSibling); }
      else { ref.className = t.className; bar.appendChild(ref); }
    });
  }

  async function fillContact() {
    try {
      var res = await fetch(apiBase() + '/site-settings');
      if (!res.ok) return;
      var d = await res.json();

      if (d.support_email) {
        document.querySelectorAll('[id="footer-support"], #support-link').forEach(function (el) {
          el.href = 'mailto:' + d.support_email; el.textContent = d.support_email;
        });
      }
      if (d.support_phone) {
        document.querySelectorAll('#footer-phone').forEach(function (el) { el.textContent = d.support_phone; });
      }
            // social links: show only the ones with a URL set
      [['soc-facebook','facebook_url'],['soc-instagram','instagram_url'],
       ['soc-tiktok','tiktok_url'],['soc-whatsapp','whatsapp_url']].forEach(function(pair){
        var el = document.getElementById(pair[0]);
        if(!el) return;
        var url = d[pair[1]];
        if(url){ el.href = url; el.target = '_blank'; el.rel = 'noopener'; el.style.display = ''; }
        else { el.style.display = 'none'; }
      });
      if (d.legal_name) {
        document.querySelectorAll('#footer-legal').forEach(function (el) { el.textContent = d.legal_name; });
      }
    } catch (e) { /* keep static fallback */ }
  }

  function run() { try { ensureRefundsLink(); } catch (e) {} fillContact(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else { run(); }
})();
