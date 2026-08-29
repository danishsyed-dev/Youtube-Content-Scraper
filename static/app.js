/* Front-end controller: submit a scrape, poll for progress, render results.
   No dependencies — plain fetch + DOM. */
(function () {
  "use strict";

  const form = document.getElementById("scrape-form");
  const input = document.getElementById("company");
  const submitBtn = document.getElementById("submit-btn");
  const errorEl = document.getElementById("form-error");

  const monitor = document.getElementById("monitor");
  const dot = monitor.querySelector(".status-dot");
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

  function showError(message) {
    errorEl.textContent = message;
    errorEl.hidden = false;
  }
  function clearError() {
    errorEl.hidden = true;
    errorEl.textContent = "";
  }
  function setBusy(busy) {
    submitBtn.disabled = busy;
    submitBtn.querySelector(".btn-label").textContent = busy ? "Working…" : "Extract videos";
  }
  function setState(state) {
    dot.setAttribute("data-state", state);
  }
  function setProgress(frac) {
    const pct = Math.max(0, Math.min(100, Math.round(frac * 100)));
    bar.style.width = pct + "%";
    statusPct.textContent = pct + "%";
    progressbar.setAttribute("aria-valuenow", String(pct));
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function renderPreview(job) {
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

    resultsTitle.textContent = job.row_count + " video" + (job.row_count === 1 ? "" : "s");
    const shown = (job.preview || []).length;
    previewNote.textContent =
      shown < job.row_count
        ? "Showing first " + shown + " of " + job.row_count + " — full set is in the CSV."
        : "All rows shown.";
    downloadBtn.href = "/download/" + job.id;
    results.hidden = false;
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
        statusText.textContent = job.message || job.status;
        setProgress(job.progress || 0);
        roCount.textContent = job.row_count ? job.row_count : "—";

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
          statusText.textContent = "Failed";
          showError(job.error || "The scrape failed.");
          setBusy(false);
        }
      })
      .catch(function (err) {
        setState("error");
        statusText.textContent = "Connection lost";
        showError(err.message);
        setBusy(false);
      });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    const company = input.value.trim();
    clearError();
    if (!company) {
      showError("Please enter a company name.");
      return;
    }

    stopPolling();
    setBusy(true);
    results.hidden = true;
    resultsBody.innerHTML = "";
    monitor.hidden = false;
    setState("pending");
    setProgress(0);
    statusText.textContent = "Queued";
    roCompany.textContent = company;
    roJob.textContent = "…";
    roCount.textContent = "—";

    const body = new URLSearchParams();
    body.set("company", company);

    fetch("/scrape", { method: "POST", body: body })
      .then(function (r) {
        return r.json().then(function (data) { return { ok: r.ok, data: data }; });
      })
      .then(function (res) {
        if (!res.ok) throw new Error(res.data.error || "Could not start the scrape.");
        roJob.textContent = res.data.job_id.slice(0, 8);
        poll(res.data.job_id);
      })
      .catch(function (err) {
        setState("error");
        statusText.textContent = "Failed";
        showError(err.message);
        setBusy(false);
      });
  });
})();
