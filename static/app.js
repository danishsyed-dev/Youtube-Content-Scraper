/* Front-end controller: submit a scrape, poll for progress, render results.
   No dependencies — plain fetch + DOM.

   Robustness notes:
   - Runs on DOMContentLoaded (and immediately if the DOM is already parsed),
     so it works whether or not the <script> is deferred or moved.
   - The submit handler is attached to the form FIRST, and calls
     preventDefault() as its very first statement. That guarantees the form
     never falls back to a native navigation, even if an unrelated element
     lookup below were to fail. (The form also has action="/scrape"
     method="post" as a last-ditch fallback if JS doesn't run at all.)
   - UI updates are null-guarded so a missing optional element can degrade a
     visual detail without breaking the core submit/poll flow. */
(function () {
  "use strict";

  function init() {
    const form = document.getElementById("scrape-form");
    if (!form) return; // Nothing to enhance.

    const input = document.getElementById("company");
    const submitBtn = document.getElementById("submit-btn");
    const errorEl = document.getElementById("form-error");

    const monitor = document.getElementById("monitor");
    const dot = monitor ? monitor.querySelector(".status-dot") : null;
    const statusText = document.getElementById("status-text");
    const statusPct = document.getElementById("status-pct");
    const bar = document.getElementById("bar");
    const progressbar = document.getElementById("progressbar");
    const roCompany = document.getElementById("ro-company");
    const roJob = document.getElementById("ro-job");
    const roCount = document.getElementById("ro-count");

    const results = document.getElementById("results");
    const resultsTitle = document.getElementById("results-title");
    const resultsBody = document.getElementById("results-body");
    const downloadBtn = document.getElementById("download-btn");
    const previewNote = document.getElementById("preview-note");

    const POLL_MS = 1200;
    let pollTimer = null;

    function setText(el, value) {
      if (el) el.textContent = value;
    }
    function showError(message) {
      if (!errorEl) return;
      errorEl.textContent = message;
      errorEl.hidden = false;
    }
    function clearError() {
      if (!errorEl) return;
      errorEl.hidden = true;
      errorEl.textContent = "";
    }
    function setBusy(busy) {
      if (submitBtn) {
        submitBtn.disabled = busy;
        const label = submitBtn.querySelector(".btn-label");
        if (label) label.textContent = busy ? "Working…" : "Extract videos";
      }
    }
    function setState(state) {
      if (dot) dot.setAttribute("data-state", state);
    }
    function setProgress(frac) {
      const pct = Math.max(0, Math.min(100, Math.round((frac || 0) * 100)));
      if (bar) bar.style.width = pct + "%";
      setText(statusPct, pct + "%");
      if (progressbar) progressbar.setAttribute("aria-valuenow", String(pct));
    }

    function esc(s) {
      const d = document.createElement("div");
      d.textContent = s == null ? "" : String(s);
      return d.innerHTML;
    }

    function renderPreview(job) {
      if (resultsBody) {
        resultsBody.innerHTML = "";
        (job.preview || []).forEach(function (row, i) {
          const tr = document.createElement("tr");
          tr.innerHTML =
            '<td class="idx">' + (i + 1) + "</td>" +
            '<td class="title">' + esc(row.title || "(untitled)") + "</td>" +
            '<td class="views">' + esc(row.views || "—") + "</td>" +
            '<td class="uploaded">' + esc(row.upload_time || "—") + "</td>" +
            '<td class="col-link"><a class="watch" href="' + esc(row.link) +
              '" target="_blank" rel="noopener">watch ↗</a></td>";
          resultsBody.appendChild(tr);
        });
      }

      setText(resultsTitle, job.row_count + " video" + (job.row_count === 1 ? "" : "s"));
      const shown = (job.preview || []).length;
      setText(
        previewNote,
        shown < job.row_count
          ? "Showing first " + shown + " of " + job.row_count + " — full set is in the CSV."
          : "All rows shown."
      );
      if (downloadBtn) downloadBtn.href = "/download/" + job.id;
      if (results) results.hidden = false;
    }

    function stopPolling() {
      if (pollTimer) {
        clearTimeout(pollTimer);
        pollTimer = null;
      }
    }

    function poll(jobId) {
      fetch("/status/" + encodeURIComponent(jobId))
        .then(function (r) {
          if (!r.ok) throw new Error("Lost track of the job (status " + r.status + ").");
          return r.json();
        })
        .then(function (job) {
          setText(statusText, job.message || job.status);
          setProgress(job.progress || 0);
          setText(roCount, job.row_count ? job.row_count : "—");

          if (job.status === "running" || job.status === "pending") {
            setState("running");
            pollTimer = setTimeout(function () { poll(jobId); }, POLL_MS);
          } else if (job.status === "done") {
            setState("done");
            setProgress(1);
            renderPreview(job);
            setBusy(false);
          } else if (job.status === "error") {
            setState("error");
            setText(statusText, "Failed");
            showError(job.error || "The scrape failed.");
            setBusy(false);
          }
        })
        .catch(function (err) {
          setState("error");
          setText(statusText, "Connection lost");
          showError(err.message);
          setBusy(false);
        });
    }

    function onSubmit(e) {
      e.preventDefault(); // Must be first: never let the form navigate natively.

      const company = input ? input.value.trim() : "";
      clearError();
      if (!company) {
        showError("Please enter a company name.");
        return;
      }

      stopPolling();
      setBusy(true);
      if (results) results.hidden = true;
      if (resultsBody) resultsBody.innerHTML = "";
      if (monitor) monitor.hidden = false;
      setState("pending");
      setProgress(0);
      setText(statusText, "Queued");
      setText(roCompany, company);
      setText(roJob, "…");
      setText(roCount, "—");

      const body = new URLSearchParams();
      body.set("company", company);

      fetch("/scrape", { method: "POST", body: body })
        .then(function (r) {
          return r.json().then(function (data) { return { ok: r.ok, data: data }; });
        })
        .then(function (res) {
          if (!res.ok) throw new Error(res.data.error || "Could not start the scrape.");
          setText(roJob, String(res.data.job_id).slice(0, 8));
          poll(res.data.job_id);
        })
        .catch(function (err) {
          setState("error");
          setText(statusText, "Failed");
          showError(err.message);
          setBusy(false);
        });
    }

    // Attach the handler up front so preventDefault is always in force.
    form.addEventListener("submit", onSubmit);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
