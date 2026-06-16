/*
 * fmn-report.js — FindMyNyumba "Report listing" button + modal
 * ---------------------------------------------------------------------------
 * Drop-in, no dependencies beyond what the site already loads.
 *
 * Usage A (auto): place a button anywhere with the data attributes:
 *     <button data-fmn-report data-listing-id="123">Report this listing</button>
 *   The script wires every such button on the page.
 *
 * Usage B (programmatic):
 *     FMNReport.open({ listingId: 123 });
 *     FMNReport.open({ userId: 45 });
 *
 * Submitting POSTs to /api/v1/fraud/reports with the logged-in user's JWT
 * (read from localStorage 'fmn_token' / 'token' / 'access_token' — whichever
 * the site uses). If no token is found, the modal prompts the user to log in.
 */
(function () {
  "use strict";

  var local =
    location.hostname === "localhost" || location.hostname === "127.0.0.1";
  var API_BASE =
    (local ? "http://localhost:8000" : "https://findmynyumba.onrender.com") +
    "/api/v1";

  var CATEGORIES = [
    ["scam", "Scam / fraud"],
    ["fake_photos", "Fake photos"],
    ["wrong_location", "Wrong location"],
    ["fake_landlord", "Fake landlord"],
    ["viewing_fee_request", "Asked for a viewing fee"],
    ["agent_fee_scam", "Agent fee scam"],
    ["other", "Other"],
  ];

  function token() {
    var keys = ["fmn_token", "token", "access_token", "jwt"];
    for (var i = 0; i < keys.length; i++) {
      var v = localStorage.getItem(keys[i]);
      if (v) return v;
    }
    return null;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var overlay = null;

  function close() {
    if (overlay) {
      overlay.remove();
      overlay = null;
      document.removeEventListener("keydown", onKey);
    }
  }
  function onKey(e) {
    if (e.key === "Escape") close();
  }

  function open(opts) {
    opts = opts || {};
    close();

    overlay = document.createElement("div");
    overlay.style.cssText =
      "position:fixed;inset:0;background:rgba(15,23,42,.55);z-index:1000;" +
      "display:flex;align-items:center;justify-content:center;padding:16px;";
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) close();
    });

    var opts_html = CATEGORIES.map(function (c) {
      return '<option value="' + c[0] + '">' + esc(c[1]) + "</option>";
    }).join("");

    var card = document.createElement("div");
    card.style.cssText =
      "background:#fff;border-radius:16px;max-width:440px;width:100%;" +
      "box-shadow:0 20px 50px rgba(15,23,42,.3);overflow:hidden;";
    card.innerHTML =
      '<div style="background:#0f172a;color:#fff;padding:16px 20px;display:flex;' +
      'align-items:center;gap:10px;">' +
      '<i class="fas fa-shield-halved" style="color:#4ade80"></i>' +
      '<strong style="font-size:16px">Report this listing</strong>' +
      '<button id="fmn-r-x" aria-label="Close" style="margin-left:auto;background:0;' +
      'border:0;color:#94a3b8;font-size:18px;cursor:pointer"><i class="fas fa-times"></i></button>' +
      "</div>" +
      '<div style="padding:20px">' +
      '<p style="font-size:13px;color:#475569;margin:0 0 14px">Your report is ' +
      "confidential and reviewed by our Trust &amp; Safety team. Reporting a " +
      "scam helps protect other students.</p>" +
      '<label style="font-size:13px;font-weight:700;color:#0f172a;display:block;margin-bottom:6px">What\u2019s wrong?</label>' +
      '<select id="fmn-r-cat" style="width:100%;padding:10px 12px;border:1px solid #cbd5e1;' +
      'border-radius:10px;font-size:14px;margin-bottom:14px;background:#fff">' +
      opts_html +
      "</select>" +
      '<label style="font-size:13px;font-weight:700;color:#0f172a;display:block;margin-bottom:6px">Details (optional)</label>' +
      '<textarea id="fmn-r-desc" rows="3" maxlength="2000" placeholder="e.g. Landlord asked me to send K150 on Airtel Money before viewing" ' +
      'style="width:100%;padding:10px 12px;border:1px solid #cbd5e1;border-radius:10px;' +
      'font-size:14px;resize:vertical;box-sizing:border-box"></textarea>' +
      '<div id="fmn-r-err" style="display:none;color:#b91c1c;font-size:13px;margin-top:10px"></div>' +
      '<button id="fmn-r-submit" style="margin-top:16px;width:100%;background:#16a34a;' +
      "color:#fff;border:0;padding:12px;border-radius:10px;font-weight:700;font-size:14px;" +
      'cursor:pointer">Submit report</button>' +
      "</div>";

    overlay.appendChild(card);
    document.body.appendChild(overlay);
    document.addEventListener("keydown", onKey);

    card.querySelector("#fmn-r-x").addEventListener("click", close);

    var btn = card.querySelector("#fmn-r-submit");
    btn.addEventListener("click", function () {
      var errBox = card.querySelector("#fmn-r-err");
      errBox.style.display = "none";

      var t = token();
      if (!t) {
        errBox.textContent = "Please log in to submit a report.";
        errBox.style.display = "block";
        return;
      }

      var payload = {
        category: card.querySelector("#fmn-r-cat").value,
        description: card.querySelector("#fmn-r-desc").value || null,
      };
      if (opts.listingId) payload.listing_id = Number(opts.listingId);
      if (opts.userId) payload.reported_user_id = Number(opts.userId);

      btn.disabled = true;
      btn.textContent = "Submitting\u2026";

      fetch(API_BASE + "/fraud/reports", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + t,
        },
        body: JSON.stringify(payload),
      })
        .then(function (r) {
          if (r.status === 429) throw new Error("You\u2019ve sent several reports recently. Please try again later.");
          if (r.status === 401) throw new Error("Your session expired. Please log in again.");
          if (!r.ok) return r.json().then(function (j) {
            throw new Error(j.detail || "Could not submit report.");
          });
          return r.json();
        })
        .then(function () {
          card.innerHTML =
            '<div style="padding:32px 24px;text-align:center">' +
            '<div style="width:56px;height:56px;border-radius:50%;background:#dcfce7;' +
            "display:flex;align-items:center;justify-content:center;margin:0 auto 16px\">" +
            '<i class="fas fa-check" style="color:#16a34a;font-size:24px"></i></div>' +
            '<h3 style="margin:0 0 8px;color:#0f172a;font-size:18px">Report received</h3>' +
            '<p style="margin:0 0 20px;color:#475569;font-size:14px">Thank you. Our ' +
            "Trust &amp; Safety team will review this listing. Never pay before you " +
            "have physically viewed a property.</p>" +
            '<button id="fmn-r-done" style="background:#0f172a;color:#fff;border:0;' +
            'padding:10px 22px;border-radius:10px;font-weight:700;cursor:pointer">Done</button>' +
            "</div>";
          card.querySelector("#fmn-r-done").addEventListener("click", close);
        })
        .catch(function (e) {
          errBox.textContent = e.message;
          errBox.style.display = "block";
          btn.disabled = false;
          btn.textContent = "Submit report";
        });
    });
  }

  function wireButtons() {
    document.querySelectorAll("[data-fmn-report]").forEach(function (b) {
      if (b.__fmnWired) return;
      b.__fmnWired = true;
      b.addEventListener("click", function (e) {
        e.preventDefault();
        open({
          listingId: b.getAttribute("data-listing-id"),
          userId: b.getAttribute("data-user-id"),
        });
      });
    });
  }

  window.FMNReport = { open: open, close: close, wire: wireButtons };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireButtons);
  } else {
    wireButtons();
  }
})();
