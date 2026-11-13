// Marks made in the viewer, turned into `db.py mark` commands. The viewer never writes
// reels.json itself: db.py stays the only writer, with its checks (unknown slugs, backups).

import type { Status } from "./digest";
import type { ViewIdea } from "./reels";

export interface Change {
  status: Status;
  /** Only kept for tried / discarded, like db.py mark --note. */
  note: string;
}

/** Changes that actually differ from what the idea already shows. */
export function pending(ideas: ViewIdea[], changes: Map<string, Change>): Map<string, Change> {
  const out = new Map<string, Change>();
  for (const idea of ideas) {
    const c = changes.get(idea.slug);
    if (!c) continue;
    const note = c.status === "todo" ? "" : c.note.trim();
    if (c.status !== idea.status || note !== (idea.note ?? "")) out.set(idea.slug, { status: c.status, note });
  }
  return out;
}

/** A note as one double-quoted argument that means the same in bash, zsh and PowerShell:
 *  the characters those shells treat specially inside double quotes are dropped or replaced. */
export function quoteNote(note: string): string {
  const safe = note.replace(/\s+/g, " ").replace(/"/g, "'").replace(/[`$\\]/g, "").replace(/!/g, ".").trim();
  return `"${safe}"`;
}

/** One `db.py mark` command per status and note, slugs in digest order. */
export function markCommands(changes: Map<string, Change>, prefix = "$PY db.py"): string[] {
  const groups = new Map<string, { status: Status; note: string; slugs: string[] }>();
  for (const [slug, c] of changes) {
    const key = `${c.status}\u0000${c.note}`;
    const g = groups.get(key) ?? { status: c.status, note: c.note, slugs: [] };
    g.slugs.push(slug);
    groups.set(key, g);
  }
  return [...groups.values()].map((g) =>
    `${prefix} mark ${g.status} ${g.slugs.join(" ")}` + (g.note && g.status !== "todo" ? ` --note ${quoteNote(g.note)}` : ""));
}

/** The ideas with the viewer's changes applied, so filters and badges show them right away. */
export function applyChanges(ideas: ViewIdea[], changes: Map<string, Change>): ViewIdea[] {
  return ideas.map((i) => {
    const c = changes.get(i.slug);
    return c ? { ...i, status: c.status, note: c.status === "todo" ? null : c.note.trim() || null } : i;
  });
}
