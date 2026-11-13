import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parseDigest, slugify } from "../src/digest";

const root = fileURLToPath(new URL("../../", import.meta.url));
const example = readFileSync(`${root}examples/digest.md`, "utf-8");

const PORTUGUESE = `# Resumo

## Faça isto primeiro
1. **Plano curto** → [entrada](#plano)

## Ferramentas
### Plano curto {#plano}
**Estado:** ✅ Testado: funcionou
Resumo.

### Sem marca {#sem-marca}
**Como aplicar:** ✅ siga os passos
Outro resumo.

### Descartada {#descartada}
**Estado:** 🚫 Descartado
Resumo.
`;

const FENCED = `# D

## Tools
### Set up the hook {#hook}
Paste this:
\`\`\`markdown
## Not a category
### Not an idea
\`\`\`
**How to apply:** done.

### Second idea {#second}
Text.
`;

const ACCENTS = `# D

## Hazlo ya
1. **Automatiza** → [entrada](#automatización)

## Herramientas
### Automatiza tus tareas {#automatización}
Mira [otra](#revisión).

### Revisa antes de publicar {#revisión}
Texto.
`;

describe("parseDigest", () => {
  it("reads the example digest", () => {
    const d = parseDigest(example);
    expect(d.title).toBe("IA y Claude: resumen de mis reels guardados");
    expect(d.date).toBe("2026-11-01");
    expect(d.topHeading).toBe("Haz esto primero");
    expect(d.top).toHaveLength(4);
    expect([...new Set(d.ideas.map((i) => i.category))]).toEqual(["Claude Code", "Prompting", "Herramientas de IA"]);
    const byslug = Object.fromEntries(d.ideas.map((i) => [i.slug, i]));
    expect(byslug["subagentes-revision"]?.status).toBe("tried");
    expect(byslug["prompt-secreto"]?.status).toBe("discarded");
    expect(byslug["claude-md-corto"]?.sources).toHaveLength(3);
  });

  it("finds the top list and status marks in any language", () => {
    const d = parseDigest(PORTUGUESE);
    expect(d.top).toHaveLength(1);
    expect(d.topHeading).toBe("Faça isto primeiro");
    expect(Object.fromEntries(d.ideas.map((i) => [i.slug, i.status]))).toEqual({
      plano: "tried", "sem-marca": "todo", descartada: "discarded",
    });
  });

  it("does not take a first category of ideas for the top list", () => {
    const d = parseDigest("# T\n\n## Tools\n### One {#one}\n1. a numbered step\n");
    expect(d.top).toEqual([]);
    expect(d.ideas[0]?.slug).toBe("one");
  });

  it("keeps headings inside code blocks in the idea", () => {
    for (const text of [FENCED, FENCED.replace("```markdown", "~~~").replaceAll("```", "~~~")]) {
      const d = parseDigest(text);
      expect(d.ideas.map((i) => i.slug)).toEqual(["hook", "second"]);
      expect(d.ideas[0]?.body).toContain("### Not an idea");
    }
  });

  it("does not let a fence that is never closed swallow the rest", () => {
    const d = parseDigest("# D\n\n## Tools\n### One {#one}\n```\ncode\n\n### Two {#two}\nText.\n");
    expect(d.ideas.map((i) => i.slug)).toEqual(["one", "two"]);
  });

  it("accepts slugs with accents and Windows line endings", () => {
    const d = parseDigest(ACCENTS.replaceAll("\n", "\r\n"));
    expect(d.ideas.map((i) => [i.title, i.slug])).toEqual([
      ["Automatiza tus tareas", "automatización"], ["Revisa antes de publicar", "revisión"]]);
  });

  it("makes a slug from the title when the heading has none", () => {
    expect(parseDigest("## Tools\n### Ideas rápidas, ¡ya!\nx\n").ideas[0]?.slug).toBe("ideas-rápidas-ya");
    expect(slugify("¿?")).toBe("idea");
  });
});

// Python's export_digest.py is the reference parser: both must read every digest the same way.
const python = ["python3", "python"].find((p) => spawnSync(p, ["--version"]).status === 0);

describe.skipIf(!python)("same result as export_digest.py --json", () => {
  const cases = { example, PORTUGUESE, FENCED, ACCENTS };
  for (const [name, text] of Object.entries(cases)) {
    it(name, () => {
      const file = join(mkdtempSync(join(tmpdir(), "srd-viewer-")), "digest.md");
      writeFileSync(file, text, "utf-8");
      const r = spawnSync(python!, [`${root}skills/digest/scripts/export_digest.py`, "--json", "--digest", file], {
        encoding: "utf-8", env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      });
      if (r.status !== 0) throw new Error(r.stderr);
      const py = JSON.parse(r.stdout);
      const ts = parseDigest(text);
      expect({ title: ts.title, date: ts.date, top: ts.top }).toEqual({ title: py.title, date: py.date, top: py.top });
      expect(ts.ideas.map(({ title, slug, category, status, sources, body }) =>
        ({ title, slug, category, status, sources, body }))).toEqual(py.ideas);
    });
  }
});
