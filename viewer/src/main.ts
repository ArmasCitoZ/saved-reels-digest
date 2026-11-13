// The viewer page: open digest.md (and optionally reels.json) from disk, then search and filter.
// Files are read with the File API in the browser; nothing leaves the computer.

import { type Digest, parseDigest, type Status } from "./digest";
import { inline, render, escapeHtml } from "./markdown";
import { categories, type Database, filterIdeas, joinIdeas, parseDatabase, type Reel, type ViewIdea } from "./reels";

const STATUS_LABEL: Record<Status, string> = { todo: "Pendiente", tried: "✅ Probado", discarded: "🚫 Descartado" };

const state: { digest: Digest | null; db: Database | null; ideas: ViewIdea[] } = { digest: null, db: null, ideas: [] };

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

function day(ts: number | null): string {
  return ts ? new Date(ts * 1000).toISOString().slice(0, 10) : "";
}

function reelLink(r: Reel): string {
  const who = escapeHtml(r.author ? `@${r.author}` : r.shortcode);
  const when = r.savedAt ? ` <span class="muted">${day(r.savedAt)}</span>` : "";
  const label = r.url ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer">${who}</a>` : who;
  return `<li>${label}${when}${r.source !== "instagram" ? ` <span class="muted">${escapeHtml(r.source)}</span>` : ""}</li>`;
}

function card(i: ViewIdea): string {
  const note = i.note ? `<p class="note"><strong>Nota:</strong> ${escapeHtml(i.note)}</p>` : "";
  const reels = i.reels.length
    ? `<details><summary>${i.reels.length} reel${i.reels.length === 1 ? "" : "s"} en reels.json</summary>` +
      `<ul class="reels">${i.reels.map(reelLink).join("")}</ul></details>`
    : "";
  return `<article id="${escapeHtml(i.slug)}" class="idea status-${i.status}">
  <header><h3>${escapeHtml(i.title)}</h3>
  <span class="tag">${escapeHtml(i.category)}</span> <span class="badge">${STATUS_LABEL[i.status]}</span></header>
  ${render(i.body)}${note}${reels}
</article>`;
}

function show(): void {
  const { digest } = state;
  if (!digest) return;
  const query = $<HTMLInputElement>("q").value;
  const category = $<HTMLSelectElement>("category").value || null;
  const status = ($<HTMLSelectElement>("status").value || null) as Status | null;
  const found = filterIdeas(state.ideas, { query, category, status });
  const filtering = Boolean(query.trim() || category || status);

  $("count").textContent = `${found.length} de ${state.ideas.length} ideas` +
    (state.db ? ` · ${state.db.total} reels en la base de datos` : "");
  $("top").innerHTML = digest.top.length && !filtering
    ? `<h2>${escapeHtml(digest.topHeading)}</h2><ol>${digest.top.map((t) => `<li>${inline(t)}</li>`).join("")}</ol>`
    : "";
  $("ideas").innerHTML = found.length
    ? found.map(card).join("\n")
    : `<p class="empty">Ninguna idea coincide con la búsqueda.</p>`;
}

function setDigest(text: string): void {
  const digest = parseDigest(text);
  if (!digest.ideas.length) throw new Error("No hay ideas en este digest.md (se esperan entradas '### Título {#slug}' bajo '## Categoría').");
  state.digest = digest;
  $("title").textContent = digest.title;
  $("date").textContent = digest.date ? `Actualizado ${digest.date}` : "";
}

function refresh(): void {
  if (!state.digest) return;
  state.ideas = joinIdeas(state.digest, state.db);
  const select = $<HTMLSelectElement>("category");
  const current = select.value;
  select.innerHTML = `<option value="">Todas las categorías</option>` +
    categories(state.ideas).map((c) => `<option>${escapeHtml(c)}</option>`).join("");
  select.value = categories(state.ideas).includes(current) ? current : "";
  document.body.classList.add("loaded");
  show();
}

async function openFiles(files: Iterable<File>): Promise<void> {
  const error = $("error");
  error.textContent = "";
  try {
    for (const f of files) {
      const text = await f.text();
      if (f.name.toLowerCase().endsWith(".json")) state.db = parseDatabase(text);
      else setDigest(text);
    }
    if (!state.digest) error.textContent = "Falta digest.md: ábrelo junto con reels.json.";
    refresh();
  } catch (e) {
    error.textContent = (e as Error).message;
  }
}

function init(): void {
  const input = $<HTMLInputElement>("files");
  input.addEventListener("change", () => input.files && openFiles(input.files));
  for (const id of ["q", "category", "status"]) $(id).addEventListener("input", show);
  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer?.files.length) void openFiles(e.dataTransfer.files);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement?.tagName !== "INPUT") {
      e.preventDefault();
      $("q").focus();
    }
  });
}

init();
