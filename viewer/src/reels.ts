// Join the digest with reels.json: which saved reels back each idea, and the marks
// `db.py mark` stored. Only the fields the viewer shows are read; the rest is ignored.

import type { Digest, Idea, Status } from "./digest";

export interface Reel {
  shortcode: string;
  url: string | null;
  author: string | null;
  source: string;
  collection: string | null;
  /** Seconds since 1970, when it was saved (or added to the database, for old records). */
  savedAt: number | null;
}

export interface Mark {
  status: Exclude<Status, "todo">;
  note: string | null;
  updated: number | null;
}

export interface Database {
  /** Reels by the digest entry (idea slug) they were merged into. */
  byEntry: Map<string, Reel[]>;
  marks: Map<string, Mark>;
  total: number;
}

export interface ViewIdea extends Idea {
  reels: Reel[];
  /** The mark from reels.json if there is one, else what the digest says. */
  status: Status;
  note: string | null;
}

const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;

/** Read reels.json text. Throws an Error with a readable message if it is not the plugin's database. */
export function parseDatabase(text: string): Database {
  let data: unknown;
  try {
    data = JSON.parse(text.replace(/^﻿/, ""));
  } catch (e) {
    throw new Error(`reels.json is not valid JSON (${(e as Error).message})`);
  }
  const reels = obj(obj(data)?.reels);
  if (!reels) throw new Error('reels.json has no "reels" table: is it the file saved-reels-digest writes?');

  const byEntry = new Map<string, Reel[]>();
  let total = 0;
  for (const [code, value] of Object.entries(reels)) {
    const r = obj(value);
    if (!r) continue;
    total++;
    const entry = str(r.entry);
    if (!entry) continue;
    const reel: Reel = {
      shortcode: str(r.shortcode) ?? code,
      url: str(r.url),
      author: str(r.author),
      source: str(r.source) ?? "instagram",
      collection: str(r.collection),
      savedAt: num(r.saved_at) ?? num(r.added_at),
    };
    const list = byEntry.get(entry) ?? [];
    list.push(reel);
    byEntry.set(entry, list);
  }
  for (const list of byEntry.values()) list.sort((a, b) => (a.savedAt ?? 0) - (b.savedAt ?? 0));

  const marks = new Map<string, Mark>();
  for (const [slug, value] of Object.entries(obj(obj(data)?.entries) ?? {})) {
    const e = obj(value);
    if (e && (e.status === "tried" || e.status === "discarded")) {
      marks.set(slug, { status: e.status, note: str(e.note), updated: num(e.updated) });
    }
  }
  return { byEntry, marks, total };
}

/** Ideas ready to show: each with its reels, and the database mark winning over the digest text. */
export function joinIdeas(digest: Digest, db: Database | null): ViewIdea[] {
  return digest.ideas.map((idea) => {
    const mark = db?.marks.get(idea.slug);
    return {
      ...idea,
      reels: db?.byEntry.get(idea.slug) ?? [],
      status: mark?.status ?? idea.status,
      note: mark?.note ?? null,
    };
  });
}

export interface Filter {
  query?: string;
  category?: string | null;
  status?: Status | null;
}

/** Case- and accent-insensitive: "automatizacion" finds "Automatización". */
export function fold(s: string): string {
  return s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

/** Ideas matching every word of the query (in title, body, category, slug or authors) and the filters. */
export function filterIdeas(ideas: ViewIdea[], f: Filter): ViewIdea[] {
  const words = fold(f.query ?? "").split(/\s+/).filter(Boolean);
  return ideas.filter((i) => {
    if (f.category && i.category !== f.category) return false;
    if (f.status && i.status !== f.status) return false;
    if (!words.length) return true;
    const hay = fold([i.title, i.body, i.category, i.slug, i.note ?? "",
      ...i.reels.map((r) => r.author ?? "")].join("\n"));
    return words.every((w) => hay.includes(w));
  });
}

export function categories(ideas: ViewIdea[]): string[] {
  return [...new Set(ideas.map((i) => i.category))];
}
