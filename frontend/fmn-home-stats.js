/* ============================================================
   FindMyNyumba - homepage live stats + listings
   Fills the four stat cards and the "Available now" grid from
   GET /stats/home. Real numbers only — shown exactly as returned
   (3 shows "3", 0 shows "0"), never padded with "+".
   Include once on index.html before </body>: <script src="fmn-home-stats.js"></script>
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

  function fillStats(d) {
    ['active_listings', 'students', 'verified_landlords', 'accommodation_assistants'].forEach(function (k) {
      var el = document.querySelector('[data-stat="' + k + '"]');
      if (el) el.textContent = (typeof d[k] === 'number' ? d[k] : 0);
    });
  }

  function listingCard(l) {
    var img = l.cover_url || (l.images && l.images[0]) || '';
    var media = img
      ? '<img src="' + esc(img) + '" alt="' + esc(l.title || 'Listing') + '" class="w-full h-44 object-cover" loading="lazy">'
      : '<div class="w-full h-44 bg-slate-100 flex items-center justify-center text-slate-300"><i class="fas fa-house text-3xl"></i></div>';
    var verified = l.is_verified
      ? '<span class="inline-flex items-center gap-1 text-[10px] font-bold text-[#15803d] bg-green-50 px-2 py-0.5 rounded-full"><i class="fas fa-shield-halved"></i> Verified</span>'
      : '';
    var featured = l.is_featured
      ? '<span class="inline-flex items-center gap-1 text-[10px] font-bold text-[#ea580c] bg-orange-50 px-2 py-0.5 rounded-full"><i class="fas fa-star"></i> Featured</span>'
      : '';
    var price = (l.price != null) ? ('ZMW ' + Number(l.price).toLocaleString()) : '';
    var loc = esc(l.location || '');
    var type = esc(l.property_type || l.listing_type || '');
    var href = 'listing.html?id=' + encodeURIComponent(l.id);

    return '' +
      '<a href="' + href + '" class="block bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden hover:shadow-md transition">' +
        '<div class="relative">' + media +
          '<div class="absolute top-3 left-3 flex gap-1.5">' + featured + verified + '</div>' +
        '</div>' +
        '<div class="p-4">' +
          '<div class="flex items-start justify-between gap-2 mb-1">' +
            '<h3 class="font-black text-slate-900 text-sm leading-tight truncate">' + esc(l.title || 'Listing') + '</h3>' +
          '</div>' +
          (loc ? '<p class="text-xs text-slate-400 font-medium mb-2"><i class="fas fa-location-dot mr-1 text-[#ea580c]"></i>' + loc + '</p>' : '') +
          '<div class="flex items-center justify-between mt-2">' +
            '<span class="text-[#ea580c] font-black text-sm">' + esc(price) + '<span class="text-slate-400 font-medium text-[11px]">/mo</span></span>' +
            (type ? '<span class="text-[11px] font-bold text-slate-500 bg-slate-50 px-2 py-0.5 rounded-full capitalize">' + type + '</span>' : '') +
          '</div>' +
        '</div>' +
      '</a>';
  }

  function fillListings(list) {
    var box = document.getElementById('home-listings');
    if (!box) return;
    if (!list || !list.length) {
      box.innerHTML =
        '<div class="col-span-full bg-white rounded-2xl border border-dashed border-slate-200 p-10 text-center">' +
          '<div class="w-14 h-14 rounded-full bg-slate-50 text-slate-300 flex items-center justify-center mx-auto mb-3 text-2xl"><i class="fas fa-house"></i></div>' +
          '<p class="text-slate-500 font-bold text-sm">No listings yet</p>' +
          '<p class="text-slate-400 text-xs mt-1">New verified homes will appear here as landlords list them.</p>' +
        '</div>';
      return;
    }
    box.innerHTML = list.map(listingCard).join('');
  }

  function fillAreas(areas) {
    var box = document.getElementById('home-areas');
    if (!box) return;
    if (!areas || !areas.length) {
      box.innerHTML = '<div class="col-span-full bg-white rounded-2xl border border-dashed border-slate-200 p-8 text-center"><p class="text-slate-500 font-bold text-sm">No areas yet</p><p class="text-slate-400 text-xs mt-1">Towns will appear here as verified homes are listed.</p></div>';
      return;
    }
    box.innerHTML = areas.map(function (a) {
      var n = a.count;
      return '<a href="browse.html?q=' + encodeURIComponent(a.city) + '" class="block bg-white rounded-2xl border border-slate-100 shadow-sm p-5 hover:shadow-md hover:border-[#ea580c]/30 transition">' +
        '<div class="w-10 h-10 rounded-xl bg-orange-50 text-[#ea580c] flex items-center justify-center mb-3"><i class="fas fa-location-dot"></i></div>' +
        '<p class="font-black text-slate-900">' + esc(a.city) + '</p>' +
        '<p class="text-[13px] font-bold text-slate-500 mt-0.5">' + n + ' home' + (n === 1 ? '' : 's') + ' available</p>' +
      '</a>';
    }).join('');
  }

  async function load() {
    try {
      var res = await fetch(apiBase() + '/stats/home');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var d = await res.json();
      fillStats(d);
      fillListings(d.featured_listings);
      fillAreas(d.areas);
    } catch (e) {
      // leave the placeholder dashes; render an honest empty listings state
      fillListings([]);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load);
  else load();
})();
