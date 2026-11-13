// Parse digest.md the same way skills/digest/scripts/export_digest.py does (parse_digest).
// Python is the reference: if the two ever disagree, fix this file.

export type Status = "todo" | "tried" | "discarded";

export interface Idea {
  title: string;
  slug: string;
  category: string;
  /** Markdown under the idea's ### heading, trimmed. */
  body: string;
  /** From the "Status:" line the digest writes under the heading. */
  status: Status;
  /** Every http(s) link in the body, in order, without repeats. */
  sources: string[];
}

export interface Digest {
  title: string;
  /** First YYYY-MM-DD found before the first ## section, usually the update date. */
  date: string | null;
  topHeading: string;
  /** Lines of the "Do these first" list, without their numbers. */
  top: string[];
  ideas: Idea[];
}

const FIRST_SECTION = "Do these first";
// the digest is written in the user's language, so the heading may be translated
const TOP_HEADINGS = new Set([FIRST_SECTION.toLowerCase(), "haz esto primero"]);
// \w in Python is Unicode-aware: letters, digits and underscore in any alphabet
const ENTRY_RE = /^###\s+(.+?)\s*(?:\{#([\p{L}\p{N}_-]+)\})?\s*$/u;
const DATE_RE = /\b(\d{4}-\d{2}-\d{2})\b/;
export const ANCHOR_LINK_RE = /\]\(#([\p{L}\p{N}_-]+)\)/gu;
const URL_RE = /\]\((https?:\/\/[^)\s]+)\)/g;
const STATUS_RE = /^\*\*Status:\*\*\s*(?:\S+\s+)?(Tried|Discarded)\b/im;
const NUMBERED_RE = /^\s*\d+\.\s/;
// the marks are the same in every language, even when "Status: Tried" gets translated:
// "**Estado:** ✅ Probado: nota" (one word after the mark, so "✅ follow these steps" is not one)
const STATUS_MARK_RE = /^\*\*[^*\n]+:\*\*\s*(✅|🚫)️?\s*\S+\s*(?::|$)/u;
const STATUS_MARKS: Record<string, Status> = { "✅": "tried", "🚫": "discarded" };

export function slugify(text: string): string {
  const s = text.toLowerCase().replace(/[^\p{L}\p{N}_\s-]/gu, "");
  return s.replace(/[\s_]+/gu, "-").replace(/^-+|-+$/g, "") || "idea";
}

/** For each line, whether it is part of a fenced code block. An unclosed fence does not count. */
function inCode(lines: string[]): boolean[] {
  const out: boolean[] = [];
  let opened: number | null = null;
  lines.forEach((line, n) => {
    const text = line.trim();
    const marker = text.startsWith("```") || text.startsWith("~~~") ? text.slice(0, 3) : null;
    if (opened !== null) {
      out.push(true);
      const openMarker = (lines[opened] ?? "").trim().slice(0, 3);
      if (marker === openMarker && marker !== null && text.split(marker[0]!).join("") === "") {
        opened = null;
      }
    } else {
      out.push(marker !== null);
      if (marker) opened = n;
    }
  });
  if (opened !== null) out.fill(false, opened);
  return out;
}

/** The first ## section is the top list if it is numbered and holds no ideas, in any language. */
function topSection(lines: string[], code: boolean[]): string | null {
  const headings = lines.flatMap((line, n) => (line.startsWith("## ") && !code[n] ? [n] : []));
  const first = headings[0];
  if (first === undefined) return null;
  const end = headings[1] ?? lines.length;
  const body = lines.slice(first + 1, end);
  if (body.some((l) => ENTRY_RE.test(l)) || !body.some((l) => NUMBERED_RE.test(l))) return null;
  return lines[first]!.slice(3).trim();
}

/** todo, tried or discarded, from the line the digest puts first under an idea's heading. */
export function ideaStatus(body: string): Status {
  const first = body.split("\n").find((l) => l.trim()) ?? "";
  const mark = STATUS_MARK_RE.exec(first);
  if (mark) return STATUS_MARKS[mark[1]!]!;
  const m = STATUS_RE.exec(body);
  return m ? (m[1]!.toLowerCase() as Status) : "todo";
}

export function parseDigest(text: string): Digest {
  const out: Digest = { title: "Saved reels digest", date: null, topHeading: FIRST_SECTION, top: [], ideas: [] };
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const code = inCode(lines);
  const top = topSection(lines, code);
  const isTop = (name: string) => name === top || TOP_HEADINGS.has(name.toLowerCase());

  let section: string | null = null;
  type RawIdea = { title: string; slug: string; category: string; body: string[] };
  let idea: RawIdea | null = null;
  const raw: RawIdea[] = [];
  lines.forEach((line, n) => {
    if (code[n]) {
      // a "## comment" in a code sample is not a heading
      if (idea) idea.body.push(line);
      return;
    }
    if (line.startsWith("# ") && raw.length === 0 && section === null) {
      out.title = line.slice(2).trim();
      return;
    }
    if (line.startsWith("## ")) {
      section = line.slice(3).trim();
      idea = null;
      if (isTop(section)) out.topHeading = section;
      return;
    }
    const m = ENTRY_RE.exec(line);
    if (m && section && !isTop(section)) {
      idea = { title: m[1]!, slug: m[2] ?? slugify(m[1]!), category: section, body: [] };
      raw.push(idea);
      return;
    }
    const date = DATE_RE.exec(line);
    if (section === null && out.date === null && date) {
      out.date = date[1]!;
    } else if (section && isTop(section) && NUMBERED_RE.test(line)) {
      out.top.push(line.replace(/^\s*\d+\.\s*/, "").trim());
    } else if (idea) {
      idea.body.push(line);
    }
  });
  out.ideas = raw.map((i) => {
    const body = i.body.join("\n").trim();
    const sources = [...new Set([...body.matchAll(URL_RE)].map((m) => m[1]!))];
    return { ...i, body, status: ideaStatus(body), sources };
  });
  return out;
}
