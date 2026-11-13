// Bundle src/main.ts into one script and inline it into index.html, giving dist/index.html:
// a single file that works when opened straight from disk (file://), where module scripts
// and separate .js files are blocked by the browser.
// With --demo it also embeds examples/digest.md and examples/reels.json and opens them on load,
// giving dist/demo.html: the copy published on GitHub Pages.
import { build } from "esbuild";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const demo = process.argv.includes("--demo");
const sample = demo
  ? { digest: readFileSync("../examples/digest.md", "utf-8"), reels: readFileSync("../examples/reels.json", "utf-8") }
  : null;
const out = demo ? "dist/demo.html" : "dist/index.html";

const result = await build({
  entryPoints: ["src/main.ts"], bundle: true, format: "iife", target: "es2020",
  minify: true, write: false, charset: "utf8", define: { __DEMO__: JSON.stringify(sample) },
});
const js = result.outputFiles[0].text.replaceAll("</script", "<\\/script");
const html = readFileSync("index.html", "utf-8");
if (!html.includes("/*VIEWER_JS*/")) throw new Error("index.html lost its /*VIEWER_JS*/ placeholder");
mkdirSync("dist", { recursive: true });
writeFileSync(out, html.replace("/*VIEWER_JS*/", () => js));
console.log(`${out} (${Math.round(Buffer.byteLength(js) / 1024)} KB of script)`);
