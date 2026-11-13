// Bundle src/main.ts into one script and inline it into index.html, giving dist/index.html:
// a single file that works when opened straight from disk (file://), where module scripts
// and separate .js files are blocked by the browser.
import { build } from "esbuild";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const result = await build({
  entryPoints: ["src/main.ts"], bundle: true, format: "iife", target: "es2020",
  minify: true, write: false, charset: "utf8",
});
const js = result.outputFiles[0].text.replaceAll("</script", "<\\/script");
const html = readFileSync("index.html", "utf-8");
if (!html.includes("/*VIEWER_JS*/")) throw new Error("index.html lost its /*VIEWER_JS*/ placeholder");
mkdirSync("dist", { recursive: true });
writeFileSync("dist/index.html", html.replace("/*VIEWER_JS*/", () => js));
console.log(`dist/index.html (${Math.round(Buffer.byteLength(js) / 1024)} KB of script)`);
