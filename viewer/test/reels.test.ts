import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { parseDigest } from "../src/digest";
import {
  categories, filterIdeas, joinIdeas, lastSaved, parseDatabase, platformName, platforms, sortIdeas,
} from "../src/reels";

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
    C3: { shortcode: "C3", author: "eva", entry: "ejemplos", added_at: 50, source: "tiktok", platform: "tiktok" },
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
    expect(db.byEntry.get("ejemplos")?.[0]).toMatchObject({ platform: "tiktok", savedAt: 50, url: null });
    expect(db.byEntry.get("revision")?.[0]?.platform).toBe("instagram"); // no field: an Instagram reel
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

  it("filters by the platform of the reels behind each idea", () => {
    expect(platforms(ideas)).toEqual(["instagram", "tiktok"]);
    const on = (p: string) => filterIdeas(ideas, { platform: p }).map((i) => i.slug);
    expect(on("tiktok")).toEqual(["ejemplos"]);
    expect(on("instagram")).toEqual(["revision"]); // automatizacion has no reels at all
    expect(on("youtube")).toEqual([]);
    expect(filterIdeas(ideas, { platform: "tiktok", query: "eva" })).toHaveLength(1);
  });

  it("lists unknown platforms after the known ones", () => {
    const mixed = joinIdeas(parseDigest(DIGEST), parseDatabase(JSON.stringify({ reels: {
      A: { entry: "revision", platform: "vimeo" }, B: { entry: "revision", platform: "youtube" },
      C: { entry: "ejemplos" },
    } })));
    expect(platforms(mixed)).toEqual(["instagram", "youtube", "vimeo"]);
    expect(platforms(joinIdeas(parseDigest(DIGEST), null))).toEqual([]);
  });
});

describe("reels saved after the mark", () => {
  const MARKED = 1762000000;
  const ideas = joinIdeas(parseDigest(DIGEST), parseDatabase(JSON.stringify({
    reels: {
      A: { entry: "revision", saved_at: MARKED - 86400 },
      B: { entry: "revision", saved_at: MARKED + 86400 },
      C: { entry: "revision", saved_at: MARKED + 2 * 86400 },
      D: { entry: "revision" }, // no date: never new, as in db.py marks
      E: { entry: "automatizacion", saved_at: MARKED + 86400 },
      F: { entry: "ejemplos", saved_at: MARKED + 86400 },
    },
    entries: {
      revision: { status: "tried", updated: MARKED },
      automatizacion: { status: "discarded" }, // a mark with no date counts nothing
    },
  })));
  const bySlug = (s: string) => ideas.find((i) => i.slug === s)!;

  it("counts them like db.py marks --new", () => {
    expect(bySlug("revision").newSinceMark).toBe(2);
    expect(bySlug("automatizacion").newSinceMark).toBe(0);
    expect(bySlug("ejemplos").newSinceMark).toBe(0); // not marked in reels.json
    expect(joinIdeas(parseDigest(DIGEST), null).every((i) => i.newSinceMark === 0)).toBe(true);
  });

  it("filters the marked ideas with news", () => {
    expect(filterIdeas(ideas, { news: true }).map((i) => i.slug)).toEqual(["revision"]);
    expect(filterIdeas(ideas, { news: true, status: "discarded" })).toEqual([]);
    expect(filterIdeas(ideas, { news: false })).toHaveLength(3);
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
    expect(claudeMd.reels[2]?.platform).toBe("tiktok");
  });

  it("shows the marks stored with db.py mark, with their notes", () => {
    const byStatus = (s: string) => ideas.filter((i) => i.status === s).map((i) => i.slug);
    expect(byStatus("tried")).toEqual(["subagentes-revision"]);
    expect(byStatus("discarded")).toEqual(["prompt-secreto"]);
    expect(ideas.find((i) => i.slug === "prompt-secreto")?.note).toMatch(/no noté diferencia/);
  });
});

describe("platformName", () => {
  it("writes the platforms like db.py status, and keeps unknown ones", () => {
    expect(platformName("tiktok")).toBe("TikTok");
    expect(platformName("youtube")).toBe("YouTube");
    expect(platformName("vimeo")).toBe("vimeo");
  });

  it("does not mistake how a reel was collected for its platform", () => {
    const db = parseDatabase(JSON.stringify({ reels: { X: { entry: "e", source: "export" } } }));
    expect(db.byEntry.get("e")?.[0]?.platform).toBe("instagram");
  });
});

describe("sortIdeas", () => {
  const ideas = joinIdeas(parseDigest(DIGEST), parseDatabase(DB));
  const slugs = (list: typeof ideas) => list.map((i) => i.slug);

  it("keeps the digest's order by default, without changing the list it gets", () => {
    const sorted = sortIdeas(ideas, "digest");
    expect(slugs(sorted)).toEqual(["automatizacion", "revision", "ejemplos"]);
    expect(sorted).not.toBe(ideas);
  });

  it("puts the idea with the newest saved reel first, and ideas with no dates last", () => {
    expect(lastSaved(ideas[1]!)).toBe(200);
    expect(lastSaved(ideas[0]!)).toBeNull();
    expect(slugs(sortIdeas(ideas, "recent"))).toEqual(["revision", "ejemplos", "automatizacion"]);
    expect(slugs(ideas)).toEqual(["automatizacion", "revision", "ejemplos"]); // not sorted in place
  });

  it("puts the ideas backed by more reels first, ties in digest order", () => {
    expect(slugs(sortIdeas(ideas, "reels"))).toEqual(["revision", "ejemplos", "automatizacion"]);
    const alone = joinIdeas(parseDigest(DIGEST), null);
    expect(slugs(sortIdeas(alone, "reels"))).toEqual(slugs(alone));
    expect(slugs(sortIdeas(alone, "recent"))).toEqual(slugs(alone));
  });
});
