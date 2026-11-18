// Small helpers for the pages. All data changes go through /api.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.style.display = "block";
  clearTimeout(t._h); t._h = setTimeout(() => (t.style.display = "none"), 2200);
}

async function api(path, opts = {}) {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" }, credentials: "same-origin", ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast("copied"); }
  catch { toast("couldn't reach the clipboard; select the text and copy"); }
}

// cycle switcher in the header
const cyc = $("#cycleSwitch");
if (cyc) cyc.onchange = () => { const u = new URL(location); u.searchParams.set("cycle", cyc.value); location = u; };

// clickable table rows
$$("tr[data-href]").forEach(tr => tr.onclick = e => { if (!e.target.closest("a,button,input")) location = tr.dataset.href; });

// Run review (dashboard)
const runBtn = $("#runReview");
if (runBtn) runBtn.onclick = async () => {
  const log = $("#runLog");
  runBtn.disabled = true;
  log.textContent = `starting review · ${runBtn.dataset.label}\n`;
  try {
    const r = await api("/reviews", { method: "POST", body: JSON.stringify({ cycle_id: +runBtn.dataset.cycle }) });
    log.textContent += `${r.total} submissions checked against every required document and plan section in ${r.duration_ms} ms\n` +
      `  complete ......... ${r.complete}\n  late ............. ${r.late}\n  missing items .... ${r.missing}\n` +
      `  not submitted .... ${r.not_submitted}\n  open items ....... ${r.open_items}\nreminder list updated. reloading…`;
    setTimeout(() => location.reload(), 1400);
  } catch (e) { log.textContent += "failed: " + e.message; runBtn.disabled = false; }
};

// Checklist on a submission page
$$("input[data-req]").forEach(cb => cb.onchange = async () => {
  const sid = cb.dataset.sid, rid = cb.dataset.req;
  cb.disabled = true;
  try {
    const r = await api(`/submissions/${sid}/items/${rid}`, { method: "PATCH", body: JSON.stringify({ present: cb.checked }) });
    toast(cb.checked ? "recorded as received" : "reopened");
    const st = $("#statusTag");
    st.className = "tag s-" + r.status;
    st.textContent = { complete: "Complete", late: "Late", missing: "Missing items", not_submitted: "Not submitted" }[r.status];
    $("#openCount").textContent = r.missing.length;
    cb.closest(".check").classList.toggle("have", cb.checked);
    setTimeout(() => location.reload(), 700);
  } catch (e) { toast(e.message); cb.checked = !cb.checked; cb.disabled = false; }
});

const notes = $("#notes");
if (notes) $("#saveNotes").onclick = async () => {
  await api(`/submissions/${notes.dataset.sid}/notes`, { method: "PUT", body: JSON.stringify({ notes: notes.value }) });
  toast("note saved");
};

// Copy buttons on reminders
$$("[data-copy]").forEach(b => b.onclick = () => copyText($(b.dataset.copy).innerText));

// Import form
const imp = $("#importForm");
if (imp) imp.onsubmit = async e => {
  e.preventDefault();
  const fd = new FormData(imp), out = $("#importResult");
  out.innerHTML = "uploading…";
  try {
    const res = await fetch(`/api/import?cycle=${imp.dataset.cycle}`, { method: "POST", body: fd, credentials: "same-origin" });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error);
    out.innerHTML = `<div class="ok-box">${d.created} created · ${d.updated} updated${d.errors.length ? " · " + d.errors.length + " rows skipped" : ""}. Run the review on the dashboard to refresh statuses.</div>` +
      (d.errors.length ? "<ul>" + d.errors.map(x => `<li class="mono">${x}</li>`).join("") + "</ul>" : "");
  } catch (err) { out.innerHTML = `<div class="flash">${err.message}</div>`; }
};
