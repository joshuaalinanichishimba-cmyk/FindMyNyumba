/* ============================================================================
 * fmn-gallery.js  —  FindMyNyumba media display (cards + viewer)
 * ----------------------------------------------------------------------------
 * Reads the new media[] / cover_url and falls back to legacy images[]/image_url,
 * so it works against either backend version.
 *
 * Public API:
 *   FMNGallery.normalize(listing, resolve)   -> {items:[{url,type}], cover, count, hasVideo}
 *   FMNGallery.cardCarousel(mountEl, items, {onOpen})   // cover + arrows + swipe + dots + badges
 *   FMNGallery.openLightbox(items, startIndex)          // fullscreen: prev/next, swipe, video, zoom
 *
 * Branding: FMN orange (#ea580c). FontAwesome icons. No dependencies.
 * ========================================================================== */
(function (global) {
  'use strict';

  var ORANGE = '#ea580c';
  var FB = 'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800&q=80';

  function _id(v){ return v; }

  function normalize(L, resolve){
    resolve = resolve || _id;
    var items = [];
    if (L && Array.isArray(L.media)) {
      L.media.forEach(function (m) {
        if (!m) return;
        var u = resolve(m.media_url || m.url || '');
        if (u) items.push({ url: u, type: (m.media_type === 'video' ? 'video' : 'photo') });
      });
    }
    if (!items.length && L && Array.isArray(L.images)) {
      L.images.filter(Boolean).forEach(function (u) { var r = resolve(u); if (r) items.push({ url: r, type: 'photo' }); });
    }
    if (!items.length && L) {
      var s = L.cover_url || L.image_url;
      if (s) { var r = resolve(s); if (r) items.push({ url: r, type: 'photo' }); }
    }
    var cover = null;
    if (L && Array.isArray(L.media) && L.media.length) {
      var c = L.media.find(function (m) { return m && m.is_cover; }) || L.media[0];
      if (c) cover = { url: resolve(c.media_url || c.url || ''), type: (c.media_type === 'video' ? 'video' : 'photo') };
    }
    if (!cover) cover = items[0] || null;
    return { items: items, cover: cover, count: items.length, hasVideo: items.some(function (m) { return m.type === 'video'; }) };
  }

  function _slideHTML(item, eager) {
    if (item.type === 'video') {
      return '<video class="fmn-g-slide" src="' + item.url + '#t=0.1" muted playsinline preload="metadata"></video>' +
             '<span class="fmn-g-playbadge"><i class="fas fa-play"></i></span>';
    }
    return '<img class="fmn-g-slide" ' + (eager ? '' : 'loading="lazy" ') + 'src="' + item.url + '" alt="" ' +
           'onerror="this.onerror=null;this.src=\'' + FB + '\'">';
  }

  // ---- Card carousel ---------------------------------------------------------
  function cardCarousel(mount, items, opts) {
    opts = opts || {};
    if (!mount) return;
    if (!items || !items.length) { items = [{ url: FB, type: 'photo' }]; }
    var idx = 0;
    var multi = items.length > 1;
    var hasVideo = items.some(function (m) { return m.type === 'video'; });

    mount.classList.add('fmn-g-card');
    mount.innerHTML =
      '<div class="fmn-g-track">' + _slideHTML(items[0], true) + '</div>' +
      (multi ? '<button type="button" class="fmn-g-arrow fmn-g-prev" aria-label="Previous"><i class="fas fa-chevron-left"></i></button>' +
               '<button type="button" class="fmn-g-arrow fmn-g-next" aria-label="Next"><i class="fas fa-chevron-right"></i></button>' : '') +
      ((multi || hasVideo) ? '<div class="fmn-g-badge">' + (hasVideo ? '<i class="fas fa-video"></i> ' : '<i class="fas fa-images"></i> ') + items.length + '</div>' : '') +
      (multi ? '<div class="fmn-g-dots">' + items.map(function (_, i) { return '<span class="fmn-g-dot' + (i === 0 ? ' is-on' : '') + '"></span>'; }).join('') + '</div>' : '');

    var track = mount.querySelector('.fmn-g-track');
    var dots = mount.querySelectorAll('.fmn-g-dot');

    function show(i) {
      idx = (i + items.length) % items.length;
      track.innerHTML = _slideHTML(items[idx], true);
      for (var d = 0; d < dots.length; d++) dots[d].classList.toggle('is-on', d === idx);
    }
    if (multi) {
      mount.querySelector('.fmn-g-next').addEventListener('click', function (e) { e.stopPropagation(); show(idx + 1); });
      mount.querySelector('.fmn-g-prev').addEventListener('click', function (e) { e.stopPropagation(); show(idx - 1); });
      // swipe
      var x0 = null;
      mount.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
      mount.addEventListener('touchend', function (e) {
        if (x0 == null) return; var dx = e.changedTouches[0].clientX - x0;
        if (Math.abs(dx) > 40) show(idx + (dx < 0 ? 1 : -1)); x0 = null;
      });
    }
    // open lightbox on tap of the media (not the arrows)
    track.addEventListener('click', function () { if (opts.onOpen) opts.onOpen(idx); else openLightbox(items, idx); });
    _injectStyle();
  }

  // ---- Fullscreen lightbox ---------------------------------------------------
  function openLightbox(items, start) {
    if (!items || !items.length) return;
    _injectStyle();
    var idx = start || 0;
    var zoomed = false;

    var ov = document.createElement('div');
    ov.className = 'fmn-lb';
    ov.innerHTML =
      '<button type="button" class="fmn-lb-close" aria-label="Close"><i class="fas fa-times"></i></button>' +
      '<button type="button" class="fmn-lb-arrow fmn-lb-prev" aria-label="Previous"><i class="fas fa-chevron-left"></i></button>' +
      '<div class="fmn-lb-stage"></div>' +
      '<button type="button" class="fmn-lb-arrow fmn-lb-next" aria-label="Next"><i class="fas fa-chevron-right"></i></button>' +
      '<div class="fmn-lb-count"></div>';
    document.body.appendChild(ov);
    document.body.style.overflow = 'hidden';

    var stage = ov.querySelector('.fmn-lb-stage');
    var count = ov.querySelector('.fmn-lb-count');
    var prevB = ov.querySelector('.fmn-lb-prev');
    var nextB = ov.querySelector('.fmn-lb-next');
    if (items.length < 2) { prevB.style.display = 'none'; nextB.style.display = 'none'; }

    function render() {
      var it = items[idx];
      zoomed = false;
      if (it.type === 'video') {
        stage.innerHTML = '<video class="fmn-lb-media" src="' + it.url + '" controls autoplay playsinline></video>';
      } else {
        stage.innerHTML = '<img class="fmn-lb-media" src="' + it.url + '" alt="" ' +
                          'onerror="this.onerror=null;this.src=\'' + FB + '\'">';
        var img = stage.querySelector('img');
        img.addEventListener('click', function (e) {
          e.stopPropagation();
          zoomed = !zoomed;
          img.classList.toggle('is-zoomed', zoomed);
        });
      }
      count.textContent = (idx + 1) + ' / ' + items.length;
    }
    function go(n) { idx = (n + items.length) % items.length; render(); }
    function close() {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
      ov.remove();
    }
    function onKey(e) {
      if (e.key === 'Escape') close();
      else if (e.key === 'ArrowRight') go(idx + 1);
      else if (e.key === 'ArrowLeft') go(idx - 1);
    }

    nextB.addEventListener('click', function (e) { e.stopPropagation(); go(idx + 1); });
    prevB.addEventListener('click', function (e) { e.stopPropagation(); go(idx - 1); });
    ov.querySelector('.fmn-lb-close').addEventListener('click', close);
    ov.addEventListener('click', function (e) { if (e.target === ov) close(); });
    document.addEventListener('keydown', onKey);

    // swipe
    var x0 = null;
    stage.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    stage.addEventListener('touchend', function (e) {
      if (x0 == null || zoomed) return; var dx = e.changedTouches[0].clientX - x0;
      if (Math.abs(dx) > 45) go(idx + (dx < 0 ? 1 : -1)); x0 = null;
    });

    render();
  }

  function _injectStyle() {
    if (document.getElementById('fmn-g-style')) return;
    var css =
'.fmn-g-card{position:relative;width:100%;height:100%;overflow:hidden;}' +
'.fmn-g-track{width:100%;height:100%;}' +
'.fmn-g-slide{width:100%;height:100%;object-fit:cover;display:block;cursor:pointer;}' +
'.fmn-g-playbadge{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#fff;font-size:30px;text-shadow:0 1px 8px rgba(0,0,0,.6);pointer-events:none;}' +
'.fmn-g-arrow{position:absolute;top:50%;transform:translateY(-50%);width:30px;height:30px;border:none;border-radius:50%;background:rgba(0,0,0,.45);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:12px;opacity:0;transition:opacity .15s,background .15s;z-index:2;}' +
'.fmn-g-card:hover .fmn-g-arrow{opacity:1;}' +
'.fmn-g-arrow:hover{background:' + ORANGE + ';}' +
'.fmn-g-prev{left:8px;}.fmn-g-next{right:8px;}' +
'@media (hover:none){.fmn-g-arrow{opacity:1;}}' +
'.fmn-g-badge{position:absolute;bottom:8px;left:8px;background:rgba(0,0,0,.6);color:#fff;font-size:10px;font-weight:700;padding:2px 8px;border-radius:999px;backdrop-filter:blur(4px);display:flex;align-items:center;gap:4px;z-index:2;}' +
'.fmn-g-dots{position:absolute;bottom:8px;left:0;right:0;display:flex;justify-content:center;gap:5px;z-index:2;pointer-events:none;}' +
'.fmn-g-dot{width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,.55);}' +
'.fmn-g-dot.is-on{background:#fff;width:14px;border-radius:3px;}' +
'.fmn-lb{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.92);display:flex;align-items:center;justify-content:center;}' +
'.fmn-lb-stage{max-width:92vw;max-height:88vh;display:flex;align-items:center;justify-content:center;}' +
'.fmn-lb-media{max-width:92vw;max-height:88vh;object-fit:contain;border-radius:6px;}' +
'img.fmn-lb-media{cursor:zoom-in;transition:transform .2s ease;}' +
'img.fmn-lb-media.is-zoomed{transform:scale(2);cursor:zoom-out;}' +
'.fmn-lb-close{position:absolute;top:16px;right:18px;width:42px;height:42px;border:none;border-radius:50%;background:rgba(255,255,255,.12);color:#fff;font-size:18px;cursor:pointer;z-index:2;}' +
'.fmn-lb-close:hover{background:' + ORANGE + ';}' +
'.fmn-lb-arrow{position:absolute;top:50%;transform:translateY(-50%);width:48px;height:48px;border:none;border-radius:50%;background:rgba(255,255,255,.12);color:#fff;font-size:18px;cursor:pointer;z-index:2;}' +
'.fmn-lb-arrow:hover{background:' + ORANGE + ';}' +
'.fmn-lb-prev{left:16px;}.fmn-lb-next{right:16px;}' +
'.fmn-lb-count{position:absolute;bottom:18px;left:0;right:0;text-align:center;color:#fff;font-weight:700;font-size:13px;}';
    var tag = document.createElement('style'); tag.id = 'fmn-g-style'; tag.textContent = css; document.head.appendChild(tag);
  }

  global.FMNGallery = { normalize: normalize, cardCarousel: cardCarousel, openLightbox: openLightbox };
})(window);
