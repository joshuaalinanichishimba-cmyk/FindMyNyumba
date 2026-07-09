# Session notes - viewing codes + two-way reputation (COMPLETE)

## DONE & LIVE this session (all tested/deployed)
- Viewing-codes feature end-to-end: student requests -> host accepts -> FMN code
  shown to student only -> host verifies code in person -> completed. Works for
  BOTH landlord and student-host (backend keys on listing owner = landlord_id).
- Security: viewing_code hidden from host API view (student-only); ownership guards on all actions.
- Reschedule generates a code too; readable dates + inline date/time pickers (no prompt popups).
- Review gating: students can only review a property after a COMPLETED viewing of it.
- Landlord->student reviews: new StudentReview model + table (migration 20260619_student_reviews) +
  POST/GET /students/{id}/reviews, gated on completed viewing. Both landlord AND student_host roles allowed.
- Frontend: viewing management + "rate this student" on landlord AND student-host dashboards;
  student dashboard shows code on accepted/rescheduled viewings.
- listing.html request-viewing fixed (/viewing-requests + preferred_date/time); promote block removed.

## NEXT POSSIBLE (all optional - core trust system is complete)
- Display student rating somewhere a host sees it when reviewing a request (StudentReview GET exists, unused on frontend).
- Approach B: pre-hide review form for ineligible students (currently shows friendly 403 toast - acceptable).
- Admin moderation UI for StudentReviews (model has status=pending; property reviews already moderated - student reviews may need an admin view to approve).

## TECH DEBT (minor)
- Duplicate Operation ID warning: admin_list_reviews (admin.py + admin_extra.py).
- Junk files: "trust_models (1).py", "user.backup.py".
- Email delivery dormant: needs registered domain -> Resend -> MAIL_FROM on Render.
- Phone OTP: needs paid SMS provider.

## KNOWN: StudentReview moderation
StudentReviews start status="pending" and GET only returns "approved". There is currently
NO admin endpoint to approve them, so they will never show until that is built. (Property
reviews ARE moderated via /admin/reviews.) Consider adding StudentReview to admin moderation.

## SESSION (2026-06-26 cont.) — Review/Trust/Anti-Scam Layer + Loose Ends

### Shipped & LIVE
- Public reviews GET: GET /properties/{id}/reviews (trust fields: reviewer_verified, reviewer_member_since, reviewer_avatar, verified_viewing, +count/average). listings.py ~310.
- Trust-rich review cards on listing.html (avatar, name->profile popup, Verified + Visited badges, member-since, stars). loadPropertyReviews() ~1058.
- Listing trust badge + scam cues on listing.html (verified/unverified host, new-listing caution, always-on "never pay before viewing"). renderSafetyCues() ~681, trust-badge fed by loadPropertyReviews.
- Unbiased review form: stars start at 0 (was forced 5), rating label, char counter, disabled-until-ready button, eligibility note. updateReviewFormState().
- Report-a-review: POST /properties/reviews/{id}/report -> status="flagged" (hidden from public, surfaces in /admin/reviews?status=flagged). reportReview() ~1159.
- Host reply to reviews (FULL STACK):
  - Review model: reply_text (Text), reply_at (DateTime). Migration 20260620_review_reply (head).
  - POST /properties/reviews/{id}/reply (owner-only, <=1000 chars). reply_to_review() ~375.
  - reply in GET payload. _replyBlock() + _ownerReplyUI() in loadPropertyReviews; fetchCurrentUserThenReviews() gets /auth/me -> currentUserId to check currentProperty.owner_id.
- StudentReview moderation (closes two-way reputation gap): GET /admin/student-reviews, PATCH /admin/student-reviews/{id}/approve|reject. admin.py ~588. (Endpoints live; admin UI tab NOT built.)

### OPEN ITEMS (next session)
1. Admin dashboard UI: add a "Student Reviews" moderation tab calling /admin/student-reviews (endpoints exist; approve via API until UI built).
2. Host reply from dashboards (option 2): reply currently works from listing page only; landlord + student-host dashboards could get a Reviews section.
3. Toast in screenshots ("log in to post review") text does NOT exist in code = stale cache, NOT a bug. listing.html #toast is correctly centered (translate(-50%,...)).
4. Structured rating categories ("as described?") - market-specific anti-scam, needs schema change.
5. Duplicate fmn-trust.js exists (assets/ vs assets/js/); listing.html loads assets/fmn-trust.js.

### Commit chain (this session)
afe4743 reviews GET -> c69ba13 trust cards -> 5c65890 trust badge+cues -> 4eb9943 unbiased form -> 51e4c8a toast CSS -> 55d44bc report endpoint -> 91401bf report UI -> d6ed7d6 host-reply backend -> ed3d6fe host-reply UI -> e6ac92b student-review moderation

## SESSION (2026-06-27) — Closed remaining open items + structured ratings

### Done this session
- Admin Reviews moderation tab (admin.html): filled the empty #tab-reviews. Two panels - Property Reviews (filter: pending/flagged/approved/rejected; "flagged" surfaces report-a-review reports) + Student Reviews (host->student). loadReviews()/moderateReview(kind,id,action). Removed old duplicate single-review loadReviews block.
- Host reply from dashboards: GET /landlord/reviews + GET /student-host/reviews (all reviews across owned listings w/ status+reply+categories). Reviews tab added to dashboard-landlord.html (loadMyReviews) and dashboard-student-host.html (loadShReviews, uses API_BASE + inline _shEsc). Inline reply reuses POST /properties/reviews/{id}/reply.
- Removed duplicate assets/js/fmn-trust.js (all pages load assets/fmn-trust.js; were byte-identical). Only one copy now.
- Structured rating categories (Accuracy/Landlord/Value, all optional, nullable):
  - Review model: rating_accuracy, rating_landlord, rating_value (Integer nullable). Migration 20260627_review_categories (head).
  - ReviewCreate + post_review accept them (Field None ge=1 le=5). Included in public GET + landlord + student-host payloads.
  - listing.html review form: 3 optional cat-stars rows (catRatings{}), initCategoryStars(), sent in POST, reset after submit. _catBreakdown(r) renders chips on review cards.

### Still open
1. contact-landlord.html desktop layout: user reports Request-a-Viewing card looks covered/behind Contact Landlord card on laptop. Investigated: grid is correct (3+6+3 col-span, proper section close, no sticky/absolute/hidden on viewing card after removing lg:sticky). Likely browser cache OR narrow viewport (mobile layout) OR just below-the-fold scroll. NEEDS full-width maximized screenshot to confirm if real bug. NOTE: dashboard-landlord showToast uses bottom-5 right-4 (that's the bottom-right toast seen earlier).
2. (optional) helpful-votes on reviews; photo uploads in reviews (deferred - moderation/CSAM risk).

### Commit chain (this session)
2b31810 admin reviews tab -> [landlord reviews backend 599b571] -> 03bfb3e/landlord dash -> 6d1c78e student-host dash -> f345740 contact-landlord sticky removal -> dbe79a9 fmn-trust dedupe -> fec5703 review categories backend -> 510f51b review categories frontend

## SESSION (2026-06-27 cont.) — Cleanup wrap-up

- contact-landlord.html: confirmed ORPHANED (every student entry point - browse.html, browse.js, student-dashboard.js, dashboard-student.html, listing.html similar-listings - links to listing.html?id=; only contact-landlord.html self-referenced). DELETED (commit 553b573). The desktop "Request a Viewing covered" issue was on this unreachable page, so not student-facing. Recoverable via git: `git show 510f51b:frontend/contact-landlord.html`.
- Cleaned stale "contact-landlord.html" mention in dashboard-student.html comment (923288d).

### Student journey - all live & working
browse -> listing.html (trust badge, scam cues, verified-host) -> reviews (verified/visited badges, category breakdown, host replies, reporter profile popup) -> message / request viewing -> viewing code -> completion -> leave review (overall + Accuracy/Landlord/Value, gated on completed viewing) -> report fake reviews.

### Admin/host tooling - all live
Admin Reviews moderation tab (property+student, flagged filter); host reply from both dashboards; StudentReview moderation; structured ratings full stack.

### ALL session-notes open items now RESOLVED. No known student-facing gaps.
### Optional future ideas only: helpful-votes on reviews; review photo uploads (deferred - moderation/CSAM risk).

## SESSION (2026-06-27 cont.) — Listing freshness signals + incident note

### Shipped: listing freshness/availability signals (browse + detail)
- Backend (listings.py): _listing_card() now returns available_spots, total_spots, availability_status, view_count (getattr l._view_count). Browse endpoint batches view counts in ONE grouped ListingEvent query (kind="view") and attaches _l._view_count before serializing. get_listing_detail returns same fields + _detail_view_count (single-listing count, defined with guaranteed `=0` default BEFORE the return).
- Frontend detail (listing.html): #freshness-signals container after price; renderFreshness(data) + _freshAgo()/_freshChip(); wired after renderSafetyCues. Shows posted-date always, availability/spots (only "N of M spots left" if total_spots>1, else "Available", "Taken" if status==taken), views ONLY if view_count>=5 (so quiet marketplace never shows "1 view").
- Frontend browse (browse.html): freshness vars (freshAgo/taken/spotsLeft) + browseFreshAgo() helper; compact row on cards (clock + Taken/N-left). Short forms ("2w ago","3 left").

### INCIDENT (resolved): listing detail 500 for ~stretch
- Root cause: in commit 43930cb the return dict referenced _detail_view_count but its DEFINITION was lost (Ctrl+C during edit). The line USING it committed; the line DEFINING it did not. IMPORTS OK does NOT catch this (runtime NameError inside endpoint body). The immediate post-push 200 check passed only due to Render deploy lag serving old code = false all-clear.
- Fix (commit 808e1bb): define `_detail_view_count = 0` then try/except count, placed BEFORE the return. Verified live with detail-18/detail-17 both 200 + view_count present.
- LESSON: for changes that add a variable used in a response, re-hit the LIVE endpoint ~2 min after deploy (not immediately). IMPORTS OK is insufficient for runtime NameErrors.

### Commit chain: 43930cb freshness backend (introduced bug) -> 1331569 detail frontend -> d449d78 browse frontend -> 808e1bb FIX _detail_view_count

## SESSION (2026-06-28) — Features 11, 12, 13 (Property History, Response Quality, Analytics)

### Feature 11 — Property History Timeline (DONE)
- GET /properties/{id}/history (listings.py) - real dated events ONLY: listed, host-joined, first approved review, completed-viewings milestone. host_verified as a STATE (no verified_at column exists, so NO fake date). NO reports exposed publicly (unfair/abusable). Verified live on listing 18.
- Frontend: #property-history-card on listing.html (before "Students Also Viewed"), loadPropertyHistory() + _histIcon/_histEsc/_histDate; hidden until real data exists.

### Feature 12 — Response Quality (DONE, user chose FULL public transparency)
- GET /properties/host/{owner_id}/response-stats (listings.py): response_rate, median_response_seconds, communication_quality (= avg Review.rating_landlord), total_inquiries. Only counts threads where STUDENT messaged first; reply must be AFTER inquiry; median (robust). Threshold: enough_data = total_inquiries>=3 (below = "Not enough data yet" - integrity, not hiding).
- Public: listing.html contact card #stat-response + #stat-time (replaced static "Usually replies quickly"); loadHostResponseStats(owner.id). Below threshold -> "Not enough data yet".
- Private: landlord dashboard Response Quality card (rq-rate/rq-time/rq-comm/rq-note); shown ALWAYS with sample-size + public-threshold note.

### Feature 13 — Analytics & BI (DONE; GA skipped by choice; geo heatmap deferred)
- NEW model SearchLog (app/models/search_log.py, Base from app.core.database) - ANONYMOUS (no user_id). Migration 20260628_search_logs (head). Fire-and-forget logging in browse get_all_properties (only when q/university/price filter present).
- Rewired EXISTING /admin/analytics/search (admin_extra.py) to query SearchLog -> returns {areas:[{area,count}]} (universities + query terms). Feeds EXISTING loadSearchGeo() / "Growth & Demand" admin tab. Falls back to {areas:[]} honest empty state.
- Removed my own redundant /admin/analytics from admin.py (existing /admin/stats + /admin/analytics/growth already cover BI). NO duplicate.
- GA snippet: SKIPPED deliberately (privacy - keep data in-app). Geo heatmap (/admin/analytics/geo): still stub, deferred until volume.
- Also deleted stray duplicate app/models/trust_models (1).py.

### Feature 9 — Area Safety Score: NOT BUILT. Flagged risky (defamation/liability assigning public 1-10 safety scores to real neighbourhoods on thin data). To discuss reframing as factual counts before any build.

### Commit chain: 2ce7f9e history -> e5a41fe/e910143 response-stats -> a4f565d dash RQ -> 502ead8 SearchLog -> 7fe0dba(removed) -> 1dd61bb analytics wired+dedupe

## SESSION (2026-06-28 cont.) — Feature 9 reframed: Area Insights (admin-only)

### Feature 9 — Area Insights (DONE, reframed from "Safety Score")
- User agreed to reframe risky public 1-10 safety score -> FACTUAL COUNTS, and further chose ADMIN-ONLY (no public) because data too sparse (only 16 listings; nearest_institution set on just 5/16 - CBU x4, LMMU x1; rest null).
- GET /admin/area-insights (admin_extra.py): groups active listings by area_key = nearest_institution if set, else 2nd comma-segment of location (neighbourhood-ish), else location. Per area returns: listings, verified_hosts (distinct verified owners), approved_reviews, completed_viewings, total_reports, scam_reports (Report.reason ilike %scam%). All REAL counts, NO score, NO judgment.
- Frontend: admin "Growth & Demand" tab (#tab-analytics) - Area Insights table; loadAreaInsights() uses _adminToken(); wired into showTab('analytics') alongside loadAnalytics/loadSearchGeo. Scam column red when >0.
- NOT public (no defamation risk; would be thin "1 listing" insights anyway). Public listing-page version DEFERRED until listing density exists.

### ALL 4 requested features now done: 11 (history), 12 (response quality), 13 (analytics), 9 (area insights/reframed).
### Data-reality caveat across all: most show thin/empty states at current volume (16 listings, few reviews/viewings/messages). Value is LATENT - pays off with real usage. Highest-leverage next step remains getting real students/listings on + email setup (Resend), not more features.

### Commit chain: c1a8f4e notes -> fcf60af area-insights backend -> 4d7e051 area-insights frontend

## RELIABILITY (2026-06-28) — outage + fixes

### INCIDENT: full production outage
- Supabase project unreachable: `FATAL: (ENOTFOUND) tenant/user postgres.nternkltoqadmwfwynzl not found` from BOTH Render and local. App died at Base.metadata.create_all() on boot. NOT caused by code (our migrations were additive only). Cause: free-tier Supabase project paused/unreachable. Recovered on its own (backend later returned 200; data intact).

### FIX SHIPPED: real /health endpoint (commit cf15515)
- OLD: `@app.get("/health")` returned `{"status":"ok"}` UNCONDITIONALLY - never touched the DB. It would have reported "healthy" through the entire outage. A monitor watching it would never alert.
- NEW: executes `SELECT 1` via engine; returns 200 + {"status":"ok","api":"ok","database":"ok"} when healthy, and **503** + {"status":"degraded","database":"unreachable","error_type":<ExcName>} when the DB is down. Only exception TYPE exposed (never credentials).
- Verified: local TestClient 200/ok, prod https://findmynyumba.onrender.com/health -> 200 {"database":"ok"}.

### TODO (operational, not code — Joshua must do):
1. Set up free uptime monitor (UptimeRobot / Better Stack) on https://findmynyumba.onrender.com/health, alert when status != 200, timeout 30s+ (Render free tier cold starts are slow).
2. Supabase: free tier PAUSES on inactivity -> unannounced outages. Fine pre-launch. MUST resolve (paid tier / non-pausing provider) BEFORE real students depend on FMN. Check current Supabase pricing directly - do not rely on remembered numbers.
3. Email delivery (Resend + domain + MAIL_FROM on Render) still dormant - blocks password resets & notifications for real users.

### These 3 operational items matter MORE than any additional feature right now.
