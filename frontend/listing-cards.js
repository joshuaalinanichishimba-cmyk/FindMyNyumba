/**
 * listing-cards.js — FindMyNyumba
 *
 * Self-contained card renderer. Exports (via window.FMNCards):
 *   renderListings(listings)  — renders the full grid
 *   buildCard(p)              — builds a single card HTML string
 *
 * Usage in browse.html:
 *   <script src="listing-cards.js"></script>
 *   Then call: FMNCards.renderListings(listings)
 *   Or for a single card: container.innerHTML = FMNCards.buildCard(p)
 *
 * The module relies on resolveImageUrl() and esc() already being
 * present in the page (they are defined in browse.html's own script).
 * It also reads window.FMN.API_HOST for the fallback image path.
 *
 * No external dependencies beyond Font Awesome (already loaded).
 */
'use strict';

(function (global) {

  /* ── Saved listings ─────────────────────────────────────────────── */
  const SAVED_KEY = 'fmn_saved';

  function getSaved() {
    try { return new Set(JSON.parse(localStorage.getItem(SAVED_KEY) || '[]')); }
    catch (_) { return new Set(); }
  }

  function toggleSaved(id) {
    const s = getSaved();
    s.has(id) ? s.delete(id) : s.add(id);
    localStorage.setItem(SAVED_KEY, JSON.stringify([...s]));
    return s.has(id);
  }

  /* ── Infer listing type from title/description ──────────────────── */
  function inferType(p) {
    const t = (p.title || '').toLowerCase();
    if (t.includes('bedspace') || t.includes('bed space')) return 'Bedspace';
    if (t.includes('quatt') || t.includes('quatting'))     return 'Quatting';
    if (t.includes('shared') || t.includes('flatmate'))    return 'Shared Room';
    if (t.includes('boarding'))                             return 'Boarding';
    if (p.total_spots > 1)                                  return 'Bedspace';
    return 'Rental';
  }

  /* ── Infer amenity pills from description text ──────────────────── */
  function inferAmenities(p) {
    const text = ((p.title || '') + ' ' + (p.description || '')).toLowerCase();
    const pills = [];
    if (/wi-?fi|wifi|internet/.test(text))      pills.push({ icon: 'fa-wifi',           label: 'Wi-Fi' });
    if (/securit|guard|gated|fence/.test(text)) pills.push({ icon: 'fa-shield-halved',  label: 'Security' });
    if (/water|borehole|tank/.test(text))       pills.push({ icon: 'fa-droplet',        label: 'Water' });
    if (/parking|garage|car/.test(text))        pills.push({ icon: 'fa-square-parking', label: 'Parking' });
    if (/kitchen|cook|meal/.test(text))         pills.push({ icon: 'fa-kitchen-set',    label: 'Kitchen' });
    if (/electricity|power|zesco/.test(text))   pills.push({ icon: 'fa-bolt',           label: 'Power' });

    const bedMatch = text.match(/(\d+)\s*bed/);
    if (bedMatch) {
      pills.push({ icon: 'fa-bed', label: `${bedMatch[1]} Bed${Number(bedMatch[1]) > 1 ? 's' : ''}` });
    } else if (p.total_spots) {
      pills.push({ icon: 'fa-bed', label: `${p.total_spots} Spot${p.total_spots > 1 ? 's' : ''}` });
    }

    return pills.slice(0, 4);
  }

  /**
   * mockRating — deterministic pseudo-random rating seeded by listing id.
   * Replace with real avg_rating / review_count fields when the Review
   * model is wired up (one-line swap: `return { rating: p.avg_rating,
   * count: p.review_count }` at the top of this function).
   */
  function mockRating(id) {
    const seed   = (id * 2654435761) >>> 0;
    const rating = (3.8 + (seed % 14) / 10).toFixed(1);
    const count  = 3 + (seed % 39);
    return { rating, count };
  }

  /** mockViews — replace with p.view_count when that field exists. */
  function mockViews(id) { return ((id * 7) % 19) + 1; }

  /* ── Distance chip label ────────────────────────────────────────── */
  function distanceLabel(p) {
    // If backend adds a `distance_km` field in future:
    //   if (p.distance_km != null) return `${p.distance_km} km to ${p.nearest_institution}`;
    if (p.nearest_institution) return `Near ${p.nearest_institution}`;
    return null;
  }

  /* ── HTML-escape helper (safe to call even if browse.html's esc is not yet loaded) */
  function _esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /* ── Image URL resolver (wraps the browse.html version) ─────────── */
  function _resolveImg(raw) {
    if (typeof resolveImageUrl === 'function') return resolveImageUrl(raw);
    const FALLBACK = 'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&q=80';
    if (!raw) return FALLBACK;
    const url = String(raw).trim();
    if (!url) return FALLBACK;
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    const apiHost = (global.FMN && global.FMN.API_HOST) || '';
    return apiHost + (url.startsWith('/') ? url : '/' + url);
  }

  /* ════════════════════════════════════════════════════════════════
     buildCard(p)

     p must match the /api/v1/properties response shape:
     {
       id, title, description, price, location, image_url,
       is_boosted, status, created_at, owner_id,
       owner: { id, full_name, role, verification_status, avatar_url },
       nearest_institution, availability_status,
       total_spots, available_spots
     }
  ════════════════════════════════════════════════════════════════ */
  function buildCard(p) {
    const saved     = getSaved();
    const isSaved   = saved.has(p.id);
    const imgUrl    = _resolveImg(p.image_url);
    const price     = Number(p.price).toLocaleString();
    const safeTitle = _esc(p.title || 'Untitled');
    const safeLoc   = _esc(p.location || '');
    const type      = inferType(p);
    const amenities = inferAmenities(p);
    const { rating, count } = mockRating(p.id);
    const views     = mockViews(p.id);
    const distLabel = distanceLabel(p);

    const isVerified = p.owner?.verification_status === 'verified';
    const isNew      = p.created_at && (Date.now() - new Date(p.created_at).getTime()) < 7 * 864e5;
    const ownerName  = _esc(p.owner?.full_name || '');
    const spotsLeft  = p.available_spots ?? null;
    const totalSpots = p.total_spots ?? null;
    const isLowStock = spotsLeft !== null && totalSpots > 1 && spotsLeft <= 2;

    /* ── Badges ────────────────────────────────────────────────────── */
    const typeBadge = `<span class="fmn-badge fmn-badge-type">${_esc(type)}</span>`;
    const verifiedBadge = isVerified
      ? `<span class="fmn-badge fmn-badge-verified"><i class="fas fa-shield-halved" aria-hidden="true"></i>&nbsp;Verified</span>`
      : '';
    const newBadge   = isNew      ? `<span class="fmn-badge fmn-badge-new">New</span>` : '';
    const boostBadge = p.is_boosted
      ? `<span class="fmn-badge fmn-badge-boosted"><i class="fas fa-bolt" aria-hidden="true"></i>&nbsp;Featured</span>`
      : '';

    /* ── Amenity pills ─────────────────────────────────────────────── */
    const pillsHtml = amenities.length
      ? `<div class="fmn-amenities">${
          amenities.map(a =>
            `<span class="fmn-pill"><i class="fas ${_esc(a.icon)}" aria-hidden="true"></i>${_esc(a.label)}</span>`
          ).join('')
        }</div>`
      : '';

    /* ── Spots badge (only for multi-bed listings) ─────────────────── */
    const spotsHtml = (spotsLeft !== null && totalSpots > 1)
      ? `<span class="fmn-spots${isLowStock ? ' fmn-spots-urgent' : ''}">
           <i class="fas fa-door-open" aria-hidden="true"></i>
           ${spotsLeft} of ${totalSpots} left
         </span>`
      : '';

    /* ── Owner row ─────────────────────────────────────────────────── */
    const ownerHtml = ownerName
      ? `<span class="fmn-owner">by&nbsp;<span class="fmn-owner-name">${ownerName}</span>${
          isVerified
            ? `&nbsp;<i class="fas fa-circle-check fmn-owner-check" title="Verified" aria-label="Verified landlord"></i>`
            : ''
        }</span>`
      : '';

    /* ── Views / newly listed ──────────────────────────────────────── */
    const viewsMeta = isNew
      ? `<span class="fmn-views"><i class="fas fa-circle-dot" aria-hidden="true"></i>&nbsp;Newly listed</span>`
      : `<span class="fmn-views"><i class="fas fa-eye" aria-hidden="true"></i>&nbsp;${views} viewed today</span>`;

    /* ── Carousel dots (static 2; extend when multi-image is added) ── */
    const dots = `
      <div class="fmn-dots" aria-hidden="true">
        <div class="fmn-dot active"></div>
        <div class="fmn-dot"></div>
      </div>`;

    /* ── Card HTML ─────────────────────────────────────────────────── */
    return `
    <article class="fmn-card" data-id="${p.id}" role="article" aria-label="${safeTitle}">

      <div class="fmn-img-wrap">
        <img src="${imgUrl}" loading="lazy" alt="${safeTitle}"
             onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&q=80'">

        <div class="fmn-top-left">
          ${typeBadge}${verifiedBadge}${newBadge}${boostBadge}
        </div>

        <button class="fmn-fav-btn${isSaved ? ' active' : ''}"
                onclick="FMNCards.handleFav(event, ${p.id})"
                aria-label="${isSaved ? 'Remove from saved' : 'Save listing'}"
                title="${isSaved ? 'Saved' : 'Save'}">
          <i class="${isSaved ? 'fas' : 'far'} fa-heart" aria-hidden="true"></i>
        </button>

        ${distLabel ? `<div class="fmn-distance"><i class="fas fa-location-dot" aria-hidden="true"></i>&nbsp;${_esc(distLabel)}</div>` : ''}
        ${dots}
      </div>

      <div class="fmn-body">
        <div class="fmn-title-row">
          <h3 class="fmn-title">${safeTitle}</h3>
          <div class="fmn-rating" aria-label="Rated ${rating} out of 5 by ${count} reviewers">
            <i class="fas fa-star" aria-hidden="true"></i>${rating}
            <span class="fmn-rating-count">(${count})</span>
          </div>
        </div>

        <p class="fmn-location">
          <i class="fas fa-location-dot" aria-hidden="true"></i>
          <span>${safeLoc}</span>
        </p>

        ${pillsHtml}

        <div class="fmn-divider" role="separator"></div>

        <div class="fmn-footer">
          <div class="fmn-price-block">
            <div>
              <span class="fmn-price">K${price}</span><span class="fmn-price-unit">&nbsp;/mo</span>
            </div>
            ${ownerHtml}
          </div>
          <a href="listing.html?id=${encodeURIComponent(p.id)}"
             class="fmn-cta"
             aria-label="View details for ${safeTitle}">
            View
          </a>
        </div>

        <div class="fmn-meta-row">
          ${viewsMeta}
          <div class="fmn-meta-actions">
            ${spotsHtml}
            <button class="fmn-report"
                    onclick="FMNCards.handleReport(event, ${p.id})"
                    aria-label="Report this listing">
              <i class="fas fa-flag" aria-hidden="true"></i>&nbsp;Report
            </button>
          </div>
        </div>
      </div>
    </article>`;
  }

  /* ════════════════════════════════════════════════════════════════
     renderListings(listings)
     Drop-in replacement for the existing function in browse.html.
  ════════════════════════════════════════════════════════════════ */
  function renderListings(listings) {
    const container = document.getElementById('listings-container');
    const countEl   = document.getElementById('results-count');
    if (!container) return;

    /* Client-side sort (mirrors original behaviour) */
    const sortVal = document.getElementById('sort-filter')?.value || 'newest';
    if (sortVal === 'price_asc')  listings.sort((a, b) => Number(a.price) - Number(b.price));
    if (sortVal === 'price_desc') listings.sort((a, b) => Number(b.price) - Number(a.price));

    if (!listings || !listings.length) {
      if (countEl) countEl.textContent = '';
      container.innerHTML = `
        <div class="col-span-full text-center py-16 bg-white rounded-3xl border border-dashed border-gray-200 px-6">
          <i class="fas fa-magnifying-glass text-4xl text-gray-300 mb-4 block" aria-hidden="true"></i>
          <p class="text-lg text-gray-700 font-black">No properties found.</p>
          <p class="text-gray-400 text-sm mt-2">Try adjusting your filters or search terms.</p>
        </div>`;
      return;
    }

    if (countEl) {
      countEl.textContent = `${listings.length} listing${listings.length !== 1 ? 's' : ''} found`;
    }

    container.innerHTML = listings.map(p => buildCard(p)).join('');

    /* Stagger-in animation */
    requestAnimationFrame(() => {
      container.querySelectorAll('.fmn-card').forEach((el, i) => {
        el.style.opacity  = '0';
        el.style.transform = 'translateY(14px)';
        el.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        setTimeout(() => {
          el.style.opacity  = '1';
          el.style.transform = 'translateY(0)';
        }, i * 50);
      });
    });
  }

  /* ── Favourite handler (called from onclick in card HTML) ────────── */
  function handleFav(event, id) {
    event.preventDefault();
    event.stopPropagation();
    const btn  = event.currentTarget;
    const icon = btn.querySelector('i');
    const now  = toggleSaved(id);
    btn.classList.toggle('active', now);
    icon.className = (now ? 'fas' : 'far') + ' fa-heart';
    btn.setAttribute('aria-label', now ? 'Remove from saved' : 'Save listing');
    btn.style.transform = 'scale(1.4)';
    setTimeout(() => { btn.style.transform = ''; }, 180);
  }

  /* ── Report handler ──────────────────────────────────────────────── */
  function handleReport(event, id) {
    event.preventDefault();
    event.stopPropagation();
    window.location.href = `listing.html?id=${encodeURIComponent(id)}&action=report`;
  }

  /* ── Skeleton loader HTML (8 placeholders) ───────────────────────── */
  function skeletonHTML() {
    return Array.from({ length: 6 }, () => `<div class="fmn-skeleton" aria-hidden="true"></div>`).join('');
  }

  /* ── Public API ──────────────────────────────────────────────────── */
  global.FMNCards = {
    renderListings,
    buildCard,
    handleFav,
    handleReport,
    skeletonHTML,
    getSaved,
  };

})(window);
