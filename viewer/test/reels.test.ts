import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { parseDigest } from "../src/digest";
import { categories, filterIdeas, joinIdeas, parseDatabase } from "../src/reels";

const DIGEST = `# Digest

## Herramientas
### Automatiza tus tareas {#automatizacion}
**Status:** ✅ Tried: useful
Usa scripts.

### Revisa antes de publicar {#revision}
Pide una revisión.

## Prompting
### Ejemplos en vez de adjetivos {#ejemplos}
Dos ejemplos valen más que "hazlo profesional".
`;

const DB = JSON.stringify({
  version: 1,
  reels: {
    B2: { shortcode: "B2", author: "ana", entry: "revision", saved_at: 200, url: "https://x/B2" },
    A1: { shortcode: "A1", author: "luis", entry: "revision", saved_at: 100 },
    C3: { shortcode: "C3", author: "eva", entry: "ejemplos", added_at: 50, source: "tiktok" },
    D4: { shortcode: "D4", relevant: false },
  },
  entries: {
    automatizacion: { status: "discarded", note: "too fiddly", updated: 1 },
    ejemplos: { status: "nonsense" },
  },
});

describe("parseDatabase", () => {
  it("groups reels by idea, oldest first, and reads the marks", () => {
    const db = parseDatabase(DB);
    expect(db.total).toBe(4);
    expect(db.byEntry.get("revision")?.map((r) => r.shortcode)).toEqual(["A1", "B2"]);
    expect(db.byEntry.get("ejemplos")?.[0]).toMatchObject({ source: "tiktok", savedAt: 50, url: null });
    expect([...db.marks.keys()]).toEqual(["automatizacion"]); // an unknown status is not a mark
  });

  it("explains files that are not the plugin's database", () => {
    expect(() => parseDatabase("{oops")).toThrow(/not valid JSON/);
    expect(() => parseDatabase('{"version": 1}')).toThrow(/no "reels" table/);
    expect(() => parseDatabase("[]")).toThrow(/no "reels" table/);
  });

  it("accepts a byte order mark", () => {
    expect(parseDatabase("﻿" + DB).total).toBe(4);
  });
});

describe("joinIdeas and filterIdeas", () => {
  const ideas = joinIdeas(parseDigest(DIGEST), parseDatabase(DB));

  it("attaches reels and lets marks in reels.json win over the digest", () => {
    const auto = ideas.find((i) => i.slug === "automatizacion")!;
    expect(auto.status).toBe("discarded");
    expect(auto.note).toBe("too fiddly");
    expect(ideas.find((i) => i.slug === "revision")?.reels).toHaveLength(2);
  });

  it("works with the digest alone", () => {
    const alone = joinIdeas(parseDigest(DIGEST), null);
    expect(alone.map((i) => i.status)).toEqual(["tried", "todo", "todo"]);
    expect(alone.every((i) => i.reels.length === 0)).toBe(true);
  });

  it("searches every word, ignoring case and accents, in text and authors", () => {
    const slugs = (q: string) => filterIdeas(ideas, { query: q }).map((i) => i.slug);
    expect(slugs("REVISION")).toEqual(["revision"]);
    expect(slugs("revisión pide")).toEqual(["revision"]);
    expect(slugs("eva")).toEqual(["ejemplos"]);
    expect(slugs("fiddly")).toEqual(["automatizacion"]);
    expect(slugs("revision ejemplos")).toEqual([]);
    expect(slugs("  ")).toHaveLength(3);
  });

  it("filters by category and status", () => {
    expect(categories(ideas)).toEqual(["Herramientas", "Prompting"]);
    expect(filterIdeas(ideas, { category: "Herramientas" }).map((i) => i.slug)).toEqual(["automatizacion", "revision"]);
    expect(filterIdeas(ideas, { category: "Herramientas", status: "todo" }).map((i) => i.slug)).toEqual(["revision"]);
  });
});

describe("the sample in examples/", () => {
  const dir = new URL("../../examples/", import.meta.url);
  const ideas = joinIdeas(
    parseDigest(readFileSync(new URL("digest.md", dir), "utf-8")),
    parseDatabase(readFileSync(new URL("reels.json", dir), "utf-8")),
  );

  it("gives every idea its reels, oldest first", () => {
    expect(ideas).toHaveLength(6);
    for (const i of ideas) expect(i.reels.length, i.slug).toBeGreaterThan(0);
    const claudeMd = ideas.find((i) => i.slug === "claude-md-corto")!;
    expect(claudeMd.reels.map((r) => r.author)).toEqual(["demo_devcorner", "demo_ana.codes", "demo_shipfast"]);
    expect(claudeMd.reels[2]?.source).toBe("tiktok");
  });

  it("shows the marks stored with db.py mark, with their notes", () => {
    const byStatus = (s: string) => ideas.filter((i) => i.status === s).map((i) => i.slug);
    expect(byStatus("tried")).toEqual(["subagentes-revision"]);
    expect(byStatus("discarded")).toEqual(["prompt-secreto"]);
    expect(ideas.find((i) => i.slug === "prompt-secreto")?.note).toMatch(/no noté diferencia/);
  });
});
