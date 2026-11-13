import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parseDigest } from "../src/digest";
import { type Change, applyChanges, markCommands, pending, quoteNote } from "../src/marks";
import { joinIdeas, parseDatabase } from "../src/reels";

const root = fileURLToPath(new URL("../../", import.meta.url));

const DIGEST = `# D

## Tools
### One {#one}
**Status:** ✅ Tried: ok
Text.

### Two {#two}
Text.

### Three {#three}
Text.
`;
const DB = {
  version: 1,
  reels: { A: { shortcode: "A", entry: "one" }, B: { shortcode: "B", entry: "two" }, C: { shortcode: "C", entry: "three" } },
  entries: { two: { status: "discarded", note: "meh" } },
};
const ideas = joinIdeas(parseDigest(DIGEST), parseDatabase(JSON.stringify(DB)));
const changes = (pairs: [string, Change][]) => new Map(pairs);

describe("pending", () => {
  it("drops changes that leave an idea as it was", () => {
    const p = pending(ideas, changes([
      ["one", { status: "tried", note: "" }], // the digest already says tried
      ["two", { status: "discarded", note: " meh " }], // same mark and note
      ["three", { status: "todo", note: "ignored" }], // already pending
    ]));
    expect(p.size).toBe(0);
  });

  it("keeps real changes in digest order and drops notes on todo", () => {
    const p = pending(ideas, changes([
      ["three", { status: "tried", note: "great" }],
      ["two", { status: "todo", note: "meh" }],
      ["gone", { status: "tried", note: "" }], // not in the digest
    ]));
    expect([...p]).toEqual([["two", { status: "todo", note: "" }], ["three", { status: "tried", note: "great" }]]);
  });
});

describe("markCommands", () => {
  it("groups ideas with the same status and note", () => {
    const p = changes([
      ["a", { status: "tried", note: "" }], ["b", { status: "discarded", note: "no" }],
      ["c", { status: "tried", note: "" }], ["d", { status: "discarded", note: "no" }], ["e", { status: "todo", note: "" }],
    ]);
    expect(markCommands(p)).toEqual([
      "$PY db.py mark tried a c", '$PY db.py mark discarded b d --note "no"', "$PY db.py mark todo e"]);
  });

  it("quotes notes so no shell expands or ends them", () => {
    expect(quoteNote('dijo "wow" $(rm -rf ~) `x` C:\\temp !!\n ok')).toBe(
      "\"dijo 'wow' (rm -rf ~) x C:temp .. ok\"");
  });

  it("shows the changes in the page right away", () => {
    const shown = applyChanges(ideas, changes([["three", { status: "discarded", note: " too slow " }]]));
    expect(shown.find((i) => i.slug === "three")).toMatchObject({ status: "discarded", note: "too slow" });
  });
});

// The commands must work as they are when pasted into a shell.
const python = ["python3", "python"].find((p) => spawnSync(p, ["--version"]).status === 0);
const bash = process.platform !== "win32" && spawnSync("bash", ["--version"]).status === 0;

describe.skipIf(!python || !bash)("commands run in db.py", () => {
  it("stores the marks in reels.json", () => {
    const home = mkdtempSync(join(tmpdir(), "srd-marks-"));
    writeFileSync(join(home, "reels.json"), JSON.stringify(DB), "utf-8");
    const p = pending(ideas, changes([
      ["one", { status: "discarded", note: 'not "for" me $HOME' }], ["two", { status: "todo", note: "" }],
      ["three", { status: "tried", note: "¡útil!" }],
    ]));
    for (const cmd of markCommands(p)) {
      const r = spawnSync("bash", ["-c", cmd], {
        encoding: "utf-8", cwd: `${root}skills/digest/scripts`,
        env: { ...process.env, SRD_HOME: home, PY: python!, PYTHONIOENCODING: "utf-8" },
      });
      expect(r.status, r.stderr).toBe(0);
    }
    const entries = JSON.parse(readFileSync(join(home, "reels.json"), "utf-8")).entries;
    expect(entries.one).toMatchObject({ status: "discarded", note: "not 'for' me HOME" });
    expect(entries.two).toBeUndefined();
    expect(entries.three).toMatchObject({ status: "tried", note: "¡útil." });
  });
});
