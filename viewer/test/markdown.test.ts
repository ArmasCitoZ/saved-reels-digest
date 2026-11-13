import { describe, expect, it } from "vitest";
import { inline, render } from "../src/markdown";

describe("markdown", () => {
  it("formats the bits the digest uses", () => {
    expect(inline("**Cómo aplicarlo:** ejecuta `/init` y *recorta*")).toBe(
      "<strong>Cómo aplicarlo:</strong> ejecuta <code>/init</code> y <em>recorta</em>");
    expect(inline("[@ana](https://www.instagram.com/reel/X/) → [entrada](#plan)")).toBe(
      '<a href="https://www.instagram.com/reel/X/" target="_blank" rel="noopener noreferrer">@ana</a> → ' +
      '<a href="#plan">entrada</a>');
  });

  it("leaves snake_case and code alone", () => {
    expect(inline("usa snake_case_names")).toBe("usa snake_case_names");
    expect(inline("`**no** [x](#y)`")).toBe("<code>**no** [x](#y)</code>");
  });

  it("never lets HTML or script links through", () => {
    const html = render('<img src=x onerror=alert(1)> [x](javascript:alert(1)) "q" & `<b>`');
    expect(html).not.toMatch(/<img|<b>|href="javascript/);
    expect(html).toContain("&lt;img src=x onerror=alert(1)&gt;");
    expect(html).toContain("&quot;q&quot; &amp;");
  });

  it("renders paragraphs, lists and code blocks", () => {
    const html = render("Uno\ndos\n\n- a\n- b\n1. c\n\n```sh\n## <no heading>\n```\nfin");
    expect(html).toBe([
      "<p>Uno<br>dos</p>", "<ul>", "<li>a</li>", "<li>b</li>", "</ul>", "<ol>", "<li>c</li>", "</ol>",
      "<pre><code>## &lt;no heading&gt;</code></pre>", "<p>fin</p>"].join("\n"));
  });
});
