// AMTP user-side demo — front end. Talks to /api/* and renders what the user sees.
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const short = (hex, n = 10) => (hex ? `${hex.slice(0, n)}…` : "");

let state = null;
let uid = "mali";
let picked = new Set(["A", "B"]);

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  return res.json();
}

// ---------------- sidebar ----------------
function renderUsers() {
  $("#users").innerHTML = state.users.map((u) => `
    <button class="user ${u.uid === uid ? "on" : ""}" data-uid="${u.uid}">
      <span class="avatar">${esc(u.name.replace("Dr. ", "")[0])}</span>
      <span><b>${esc(u.name)}</b><small>${esc(u.role)}</small></span>
    </button>`).join("");
  const me = state.users.find((u) => u.uid === uid);
  $("#me").innerHTML = `
    <div class="row"><span class="k">Attributes (CP-ABE key)</span>
      <div class="chips">${me.attrs.map((a) => `<span class="chip attr">${esc(a)}</span>`).join("")}</div></div>
    <div class="row"><span class="k">Query keys from DA</span>
      <div class="chips">${state.domains.map((d) => me.domains.includes(d.id)
        ? `<span class="chip key">Domain ${d.id}</span>`
        : `<span class="chip nokey">Domain ${d.id}: none</span>`).join("")}</div></div>`;
  document.querySelectorAll(".user").forEach((b) => b.onclick = () => {
    uid = b.dataset.uid; renderUsers();
  });
}

function renderAnchors() {
  $("#anchors").innerHTML = state.domains.map((d) => `
    <div class="anchor">
      <div class="anchorhead">
        <b>Domain ${d.id}</b><span>${esc(d.name)}</span>
        <span class="epoch">epoch ${d.epoch}</span>
      </div>
      <div class="root"><span class="k">Domain Root R<sub>D</sub></span><code>${short(d.R_D, 16)}</code></div>
      <button class="ghost small publish" data-d="${d.id}" ${d.pending.length ? "" : "disabled"}
        title="Simulates the Data Owner uploading a record (Phases 1–3) and anchoring a new root">
        ${d.pending.length ? `Owner adds “${esc(d.pending[0])}” → epoch ${d.epoch + 1}` : "No more records to add"}
      </button>
    </div>`).join("");
  $("#rg").textContent = short(state.R_G, 16);
  $("#history").innerHTML = state.history.map((h) =>
    `<li>block ${h.block}: Domain ${h.domain} → epoch ${h.epoch} <code>${short(h.R_D, 8)}</code></li>`).join("");
  document.querySelectorAll(".publish").forEach((b) => b.onclick = async () => {
    b.disabled = true;
    const r = await api("/api/publish", { domain: b.dataset.d });
    state = r.state;
    renderAnchors();
    toast(`Owner published “${r.published}”. ${r.splits.length ? "Partition split: " + r.splits.join("; ") : ""}`);
  });
}

function renderControls() {
  $("#examples").innerHTML = state.examples.map((q) =>
    `<button class="chip ex" data-q="${esc(q)}">${esc(q)}</button>`).join("");
  document.querySelectorAll(".ex").forEach((b) => b.onclick = () => {
    $("#query").value = b.dataset.q; search();
  });
  $("#domainPick").innerHTML = state.domains.map((d) => `
    <label class="toggle"><input type="checkbox" value="${d.id}" ${picked.has(d.id) ? "checked" : ""}>
      <span>Domain ${d.id} · ${esc(d.name)}</span></label>`).join("");
  document.querySelectorAll("#domainPick input").forEach((i) => i.onchange = () => {
    i.checked ? picked.add(i.value) : picked.delete(i.value);
  });
  $("#mode").innerHTML = state.attacks.map(([k, v]) =>
    `<option value="${k}">${k === "honest" ? "✓ " : "⚠ "}${esc(v)}</option>`).join("");
}

// ---------------- search ----------------
async function search() {
  if (!picked.size) return toast("Pick at least one domain");
  $("#go").disabled = true;
  const body = { uid, domains: [...picked].sort(), query: $("#query").value, mode: $("#mode").value };
  const r = await api("/api/search", body);
  $("#go").disabled = false;
  $("#empty").hidden = true;
  $("#results").innerHTML = "";
  r.results.forEach((c) => $("#results").appendChild(card(c)));
  state = await api("/api/state");
  renderAnchors();
}

const VERDICT = {
  accepted: ["Verified", "ok"],
  rejected: ["Rejected", "bad"],
  storage_error: ["Storage error", "warn"],
  refused: ["Query refused", "warn"],
  no_key: ["No query key", "muted"],
  bad_query: ["Query error", "muted"],
};

function card(c) {
  const el = $("#cardTpl").content.firstElementChild.cloneNode(true);
  const [label, tone] = VERDICT[c.status];
  $(".dname", el).textContent = `Domain ${c.domain} · ${c.name}`;
  $(".sub", el).textContent = c.trapdoor ? `Pinned to epoch ${c.trapdoor.epoch}` : "";
  const v = $(".verdict", el);
  v.textContent = label; v.className = `verdict ${tone}`;
  el.classList.add(tone);

  if (c.attack && c.attack.mode !== "honest") {
    $(".attack", el).innerHTML = `<b>Server behaviour:</b> ${esc(c.attack.label)} — <i>${esc(c.attack.what)}</i>`;
  } else $(".attack", el).remove();

  $(".flow", el).innerHTML = flow(c);
  $(".body", el).innerHTML = body(c);
  return el;
}

function flow(c) {
  const s = (t, st) => `<li class="${st}"><span></span>${t}</li>`;
  const sent = !!c.trapdoor;
  const answered = ["accepted", "rejected"].includes(c.status);
  const server = c.status === "refused" ? "fail" : c.status === "storage_error" ? "warn" : answered ? "done" : "idle";
  return [
    s("1 · Build trapdoor", sent ? "done" : "fail"),
    s("2 · Server searches", sent ? server : "idle"),
    s("3 · Verify proof", c.status === "accepted" ? "done" : c.status === "rejected" ? "fail" : "idle"),
    s("4 · Decrypt", c.status === "accepted" ? "done" : "idle"),
  ].join("");
}

function body(c) {
  if (c.status === "no_key" || c.status === "bad_query")
    return `<p class="note">${esc(c.reason)}</p>`;

  let html = trapdoor(c.trapdoor);
  if (c.status === "refused")
    return html + `<p class="note warn">The cloud server refused the query: ${esc(c.reason)}</p>`;
  if (c.status === "storage_error")
    return html + `<p class="note warn"><b>StorageError:</b> ${esc(c.reason)}. The server must report the
      failure instead of sending a partial result, so nothing is shown. Try again later.</p>`;

  html += `<h4>Verification · Accept<sub>Q</sub> = all 7 checks</h4><ul class="checks">` +
    c.checks.map((k) => `
      <li class="${k.ok === true ? "pass" : k.ok === false ? "fail" : "skip"}">
        <span class="mark">${k.ok === true ? "✓" : k.ok === false ? "✗" : "–"}</span>
        <div><b>${esc(k.label)}</b> <small>b<sub>${k.key}</sub></small>
          <p>${esc(k.detail)}</p><p class="meaning">${esc(k.meaning)}</p></div>
      </li>`).join("") + `</ul>`;

  if (c.status === "rejected") {
    html += `<p class="note bad"><b>Response discarded.</b> One failed check is enough to reject the whole
      answer, so nothing is decrypted or shown.</p>`;
  } else {
    html += files(c.files);
  }
  html += stats(c);
  return html;
}

function trapdoor(t) {
  return `<details class="trap"><summary>What I sent: trapdoor T<sub>Q</sub> for
      <code>${esc(t.expression)}</code></summary>
    <table>
      ${t.keywords.map((k) => `<tr><td>${esc(k.word)}</td><td>→ h = <code>${short(k.h, 16)}</code></td></tr>`).join("")}
      <tr><td>anchored epoch e*</td><td>${t.epoch} · R<sub>D</sub> <code>${short(t.R_D, 16)}</code></td></tr>
      <tr><td>nonce η</td><td><code>${short(t.nonce, 16)}</code></td></tr>
      <tr><td>tag τ<sub>Q</sub></td><td><code>${short(t.tau, 16)}</code></td></tr>
    </table>
    <p class="meaning">The server sees only the hashed keys h, never the words.</p></details>`;
}

function files(list) {
  if (!list.length) return `<h4>Files</h4><p class="note">No file matches. The proof shows that this
    empty answer is complete, not that the server held something back.</p>`;
  const open = list.filter((f) => f.status === "open").length;
  return `<h4>Files <small>${list.length} verified · ${open} readable with your attributes</small></h4>
    <ul class="files">${list.map((f) => f.status === "open" ? `
      <li class="file"><div class="ft"><b>${esc(f.title)}</b><span class="tag">${esc(f.doc)}</span></div>
        <p>${esc(f.body)}</p>
        <p class="meta">cid <code>${short(f.cid, 10)}</code> · partition <code>${esc(f.pid.slice(0, 6))}</code> slot ${f.loc}</p></li>`
      : `
      <li class="file locked"><div class="ft"><b>🔒 Locked record</b><span class="tag">${esc(f.doc)}</span></div>
        <p>Verified, but your attributes do not satisfy its policy
          <code>${esc(f.policy)}</code>, so CP-ABE will not release the key.</p>
        <p class="meta">cid <code>${short(f.cid, 10)}</code></p></li>`).join("")}</ul>`;
}

function stats(c) {
  const s = c.stats;
  const items = [
    ["Server time", `${c.cs_ms} ms`], ["Verify time", `${c.verify_ms} ms`],
    c.decrypt_ms !== undefined ? ["Decrypt time", `${c.decrypt_ms} ms`] : null,
    ["Proof size", `${(s.proof_bytes / 1024).toFixed(1)} KB`],
    ["Keywords", `${s.present} present · ${s.absent} absent`],
    ["Partitions proven", s.partitions],
  ].filter(Boolean);
  return `<dl class="stats">${items.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl>`;
}

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4500);
}

// ---------------- boot ----------------
async function boot() {
  state = await api("/api/state");
  renderUsers(); renderAnchors(); renderControls();
}
$("#go").onclick = search;
$("#query").addEventListener("keydown", (e) => { if (e.key === "Enter") search(); });
$("#reset").onclick = async () => {
  state = await api("/api/reset", {});
  $("#results").innerHTML = ""; $("#empty").hidden = false;
  renderUsers(); renderAnchors(); renderControls();
  toast("Demo reset: fresh keys, two epochs per domain.");
};
boot();
