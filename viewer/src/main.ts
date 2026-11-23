// The viewer page: open digest.md (and optionally reels.json) from disk, then search and filter.
// Files are read with the File API in the browser; nothing leaves the computer.

import { type Digest, parseDigest, type Status } from "./digest";
import { type Change, applyChanges, markCommands, pending } from "./marks";
import { inline, render, escapeHtml } from "./markdown";
import {
  categories, type Database, filterIdeas, joinIdeas, parseDatabase, platformName, platforms, type Reel, type Sort,
  sortIdeas, type ViewIdea,
} from "./reels";
import { readView, type View, writeView } from "./view";

/** The sample files, embedded by `npm run build:demo` (the GitHub Pages copy); null in the normal build. */
declare const __DEMO__: { digest: string; reels: string } | null;

const STATUS_LABEL: Record<Status, string> = { todo: "Pendiente", tried: "✅ Probado", discarded: "🚫 Descartado" };

const state = {
  digest: null as Digest | null,
  db: null as Database | null,
  /** Ideas as the files say, and with the viewer's marks applied. */
  base: [] as ViewIdea[],
  ideas: [] as ViewIdea[],
  changes: new Map<string, Change>(),
  /** Filters from the URL, applied once the files are loaded and the selects have their options. */
  urlView: readView(location.hash) as View | null,
};

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

function day(ts: number | null): string {
  return ts ? new Date(ts * 1000).toISOString().slice(0, 10) : "";
}

function reelLink(r: Reel): string {
  const who = escapeHtml(r.author ? `@${r.author}` : r.shortcode);
  const when = r.savedAt ? ` <span class="muted">${day(r.savedAt)}</span>` : "";
  const label = r.url ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer">${who}</a>` : who;
  return `<li>${label}${when}${r.platform !== "instagram" ? ` <span class="muted">${escapeHtml(platformName(r.platform))}</span>` : ""}</li>`;
}

/** "+N nuevos" on a marked idea with reels saved after the mark, like `db.py marks --new`. */
function newBadge(i: ViewIdea): string {
  if (i.status === "todo" || i.newSinceMark <= 0) return "";
  const n = i.newSinceMark;
  return ` <span class="badge new" title="${n} reel${n === 1 ? "" : "s"} guardado${n === 1 ? "" : "s"} después de marcarla. ` +
    `Cuando los leas, vuelve a marcarla para poner el contador a cero.">+${n} nuevo${n === 1 ? "" : "s"}</span>`;
}

function card(i: ViewIdea): string {
  const note = i.note ? `<p class="note"><strong>Nota:</strong> ${escapeHtml(i.note)}</p>` : "";
  const reels = i.reels.length
    ? `<details><summary>${i.reels.length} reel${i.reels.length === 1 ? "" : "s"} en reels.json</summary>` +
      `<ul class="reels">${i.reels.map(reelLink).join("")}</ul></details>`
    : "";
  const buttons = (Object.keys(STATUS_LABEL) as Status[]).map((s) =>
    `<button type="button" data-mark="${s}" aria-pressed="${s === i.status}">${STATUS_LABEL[s]}</button>`).join("");
  const noteInput = i.status === "todo" ? "" :
    `<input class="note-input" data-slug="${escapeHtml(i.slug)}" value="${escapeHtml(i.note ?? "")}" ` +
    `placeholder="Nota (opcional): por qué" aria-label="Nota">`;
  return `<article id="${escapeHtml(i.slug)}" data-slug="${escapeHtml(i.slug)}" class="idea status-${i.status}">
  <header><h3>${escapeHtml(i.title)}</h3>
  <span class="tag">${escapeHtml(i.category)}</span> <span class="badge">${STATUS_LABEL[i.status]}</span>${newBadge(i)}</header>
  ${render(i.body)}${note}${reels}
  <div class="mark">${buttons}${noteInput}</div>
</article>`;
}

/** Set the inputs to a view; a category or platform the files do not have is left unset. */
function applyView(view: View): void {
  $<HTMLInputElement>("q").value = view.q;
  $<HTMLSelectElement>("status").value = view.status;
  $<HTMLSelectElement>("sort").value = view.sort;
  $<HTMLInputElement>("news").checked = view.news === "1";
  for (const id of ["category", "platform"] as const) {
    const select = $<HTMLSelectElement>(id);
    select.value = [...select.options].some((o) => o.value === view[id]) ? view[id] : "";
  }
}

/** Keep the filters in the URL, without adding history entries; a bare #idea anchor is left alone. */
function saveView(view: View): void {
  const hash = writeView(view);
  const current = location.hash.replace(/^#/, "");
  if (hash === current || (!hash && !current.includes("="))) return;
  try {
    history.replaceState(null, "", hash ? `#${hash}` : location.pathname + location.search);
  } catch {
    // some browsers refuse history changes on file:// pages; the filters still work
  }
}

function show(): void {
  const { digest } = state;
  if (!digest) return;
  const query = $<HTMLInputElement>("q").value;
  const category = $<HTMLSelectElement>("category").value || null;
  const status = ($<HTMLSelectElement>("status").value || null) as Status | null;
  const platform = $<HTMLSelectElement>("platform").value || null;
  const sort = $<HTMLSelectElement>("sort").value as View["sort"];
  // a hidden checkbox (no idea has news) never filters, even if a link checked it
  const news = $<HTMLInputElement>("news").checked && !$("news-label").hidden;
  saveView({ q: query, category: category ?? "", status: status ?? "", platform: platform ?? "", sort, news: news ? "1" : "" });
  const found = sortIdeas(filterIdeas(state.ideas, { query, category, status, platform, news }), (sort || "digest") as Sort);
  const filtering = Boolean(query.trim() || category || status || platform || news);

  $("count").textContent = `${found.length} de ${state.ideas.length} ideas` +
    (state.db ? ` · ${state.db.total} reels en la base de datos` : "");
  $("top").innerHTML = digest.top.length && !filtering
    ? `<h2>${escapeHtml(digest.topHeading)}</h2><ol>${digest.top.map((t) => `<li>${inline(t)}</li>`).join("")}</ol>`
    : "";
  $("ideas").innerHTML = found.length
    ? found.map(card).join("\n")
    : `<p class="empty">Ninguna idea coincide con la búsqueda.</p>`;
}

function showChanges(): void {
  const changes = pending(state.base, state.changes);
  const box = $("changes");
  box.hidden = changes.size === 0;
  $("changes-count").textContent = `${changes.size} idea${changes.size === 1 ? "" : "s"} marcada${changes.size === 1 ? "" : "s"} en el visor`;
  $<HTMLTextAreaElement>("commands").value = markCommands(changes).join("\n");
}

function setMark(slug: string, change: Change): void {
  state.changes.set(slug, change);
  state.ideas = applyChanges(state.base, state.changes);
  show();
  showChanges();
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
  state.base = joinIdeas(state.digest, state.db);
  state.ideas = applyChanges(state.base, state.changes);
  const select = $<HTMLSelectElement>("category");
  const current = select.value;
  select.innerHTML = `<option value="">Todas las categorías</option>` +
    categories(state.ideas).map((c) => `<option>${escapeHtml(c)}</option>`).join("");
  select.value = categories(state.ideas).includes(current) ? current : "";
  // Only worth a filter when the reels come from more than one platform (needs reels.json)
  const found = platforms(state.ideas);
  const platform = $<HTMLSelectElement>("platform");
  const chosen = platform.value;
  platform.innerHTML = `<option value="">Todas las plataformas</option>` +
    found.map((p) => `<option value="${escapeHtml(p)}">${escapeHtml(platformName(p))}</option>`).join("");
  platform.value = found.includes(chosen) ? chosen : "";
  platform.hidden = found.length < 2;
  // Sorting by date or number of reels needs reels.json; without it every idea ties
  $("sort").hidden = !state.db;
  // "With news" only means something when some marked idea got reels after its mark
  const news = $<HTMLInputElement>("news");
  const anyNews = state.base.some((i) => i.status !== "todo" && i.newSinceMark > 0);
  $("news-label").hidden = !anyNews;
  if (!anyNews) news.checked = false; // a link with novedades=1 still applies below if it has news
  if (state.urlView) {
    applyView(state.urlView);
    state.urlView = null;
  }
  document.body.classList.add("loaded");
  show();
  showChanges();
}

async function openFiles(files: Iterable<{ name: string; text(): Promise<string> }>): Promise<void> {
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

/** Files the person picked or dropped. The first ones replace the sample entirely, so a
 * digest.md opened alone never shows the sample's reels or marks. */
function openOwn(files: FileList): void {
  const banner = $("demo");
  if (!banner.hidden) {
    banner.hidden = true;
    state.digest = null;
    state.db = null;
    state.changes.clear();
  }
  void openFiles(files);
}

function init(): void {
  const input = $<HTMLInputElement>("files");
  input.addEventListener("change", () => input.files && openOwn(input.files));
  for (const id of ["q", "category", "status", "platform", "sort", "news"]) $(id).addEventListener("input", show);
  $("ideas").addEventListener("click", (e) => {
    const button = (e.target as HTMLElement).closest<HTMLButtonElement>("button[data-mark]");
    const slug = button?.closest<HTMLElement>("article")?.dataset.slug;
    if (!button || !slug) return;
    const idea = state.ideas.find((i) => i.slug === slug);
    setMark(slug, { status: button.dataset.mark as Status, note: idea?.note ?? "" });
  });
  $("ideas").addEventListener("change", (e) => {
    const input = e.target as HTMLInputElement;
    const slug = input.dataset.slug;
    const idea = state.ideas.find((i) => i.slug === slug);
    if (slug && idea && input.classList.contains("note-input")) setMark(slug, { status: idea.status, note: input.value });
  });
  $("copy").addEventListener("click", async () => {
    const text = $<HTMLTextAreaElement>("commands");
    try {
      await navigator.clipboard.writeText(text.value);
    } catch {
      text.select(); // file:// pages may not get the clipboard API; leave it selected to copy by hand
      document.execCommand("copy");
    }
    $("copy").textContent = "Copiado";
    setTimeout(() => ($("copy").textContent = "Copiar"), 1500);
  });
  $("discard").addEventListener("click", () => {
    state.changes.clear();
    refresh();
  });
  window.addEventListener("beforeunload", (e) => {
    if (pending(state.base, state.changes).size) e.preventDefault(); // the marks only live in this page
  });
  window.addEventListener("hashchange", () => {
    // a pasted link with other filters; a plain #idea anchor only scrolls
    if (!location.hash.includes("=") && location.hash.length > 1) return;
    applyView(readView(location.hash));
    show();
  });
  document.addEventListener("dragover", (e) => e.preventDefault());
  document.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer?.files.length) openOwn(e.dataTransfer.files);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement?.tagName !== "INPUT") {
      e.preventDefault();
      $("q").focus();
    }
  });
  if (typeof __DEMO__ !== "undefined" && __DEMO__) {
    const demo = __DEMO__;
    $("demo").hidden = false;
    void openFiles([
      { name: "digest.md", text: async () => demo.digest },
      { name: "reels.json", text: async () => demo.reels },
    ]);
  }
}

init();
