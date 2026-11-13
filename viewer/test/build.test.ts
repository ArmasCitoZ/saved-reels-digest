import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// The build is what people open: one self-contained dist/index.html that must work from file://.
const viewer = fileURLToPath(new URL("../", import.meta.url));

describe("npm run build", () => {
  const run = spawnSync(process.execPath, ["scripts/build.mjs"], { cwd: viewer, encoding: "utf-8" });
  const html = run.status === 0 ? readFileSync(`${viewer}dist/index.html`, "utf-8") : "";

  it("succeeds", () => {
    expect(run.stderr).toBe("");
    expect(run.status).toBe(0);
  });

  it("inlines the bundled script in place of the placeholder", () => {
    expect(html).not.toContain("/*VIEWER_JS*/");
    // the whole page is one file: no external scripts or module imports that file:// would block
    expect(html).not.toMatch(/<script[^>]+src=/);
    expect(html).not.toMatch(/\bimport\s*[{*"']/);
    // exactly one script element, so nothing in the bundle closed it early
    expect(html.match(/<script>/g)).toHaveLength(1);
    expect(html.match(/<\/script/gi)).toHaveLength(1);
    expect(html.indexOf("</script>")).toBeGreaterThan(html.indexOf("<script>") + 1000);
  });

  it("keeps the page's Spanish text and the elements the script looks up", () => {
    for (const id of ["files", "q", "category", "status", "ideas", "changes", "commands", "copy", "discard"]) {
      expect(html).toContain(`id="${id}"`);
    }
    expect(html).toContain("Visor del digest");
  });
});
