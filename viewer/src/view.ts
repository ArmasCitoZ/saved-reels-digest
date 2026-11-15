// The search and filters as a URL fragment (#q=agentes&plataforma=tiktok), so reloading the page
// keeps them and a link can point at one view. The fragment never reaches a server.

import type { Status } from "./digest";
import type { Sort } from "./reels";

export interface View {
  q: string;
  category: string;
  status: Status | "";
  platform: string;
  /** "" is the digest's own order. */
  sort: Exclude<Sort, "digest"> | "";
}

export const EMPTY_VIEW: View = { q: "", category: "", status: "", platform: "", sort: "" };

// Spanish keys, like the rest of the page; "q" is the usual name for a search
const KEYS: Record<keyof View, string> = {
  q: "q", category: "categoria", status: "estado", platform: "plataforma", sort: "orden",
};
const STATUSES: readonly string[] = ["todo", "tried", "discarded"];
const SORTS: readonly string[] = ["recent", "reels"];

/** Read a location.hash ("#q=..." or ""). Unknown keys and statuses are ignored. */
export function readView(hash: string): View {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const get = (k: keyof View) => params.get(KEYS[k])?.trim() ?? "";
  const status = get("status");
  const sort = get("sort");
  return {
    q: get("q"),
    category: get("category"),
    status: STATUSES.includes(status) ? (status as Status) : "",
    platform: get("platform"),
    sort: SORTS.includes(sort) ? (sort as View["sort"]) : "",
  };
}

/** The fragment for a view, without the "#"; empty when nothing is filtered. */
export function writeView(view: View): string {
  const params = new URLSearchParams();
  for (const k of Object.keys(KEYS) as (keyof View)[]) {
    const value = view[k].trim();
    if (value) params.set(KEYS[k], value);
  }
  return params.toString();
}
