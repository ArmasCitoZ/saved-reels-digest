// Just enough Markdown for the digest's idea bodies: paragraphs, lists, code blocks, `code`,
// **bold**, *italic* and links. Everything is escaped first, so text from captions or a
// hand-edited digest can never inject HTML or scripts; only http(s) and #anchor links survive.

const ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ESCAPES[c]!);
}

/** Inline Markdown of one line, already safe to put in innerHTML. */
export function inline(text: string): string {
  const codes: string[] = [];
  // code spans first, so nothing inside them is formatted
  let s = escapeHtml(text).replace(/`([^`]+)`/g, (_, c: string) => `\u0000${codes.push(c) - 1}\u0000`);
  s = s.replace(/\[([^\]]+)\]\(((?:https?:\/\/|#)[^)\s]+)\)/g, (_, label: string, href: string) => {
    const external = !href.startsWith("#");
    return `<a href="${href}"${external ? ' target="_blank" rel="noopener noreferrer"' : ""}>${label}</a>`;
  });
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[\s(])[*_]([^*_\s][^*_]*?)[*_](?=$|[\s).,:;!?])/g, "$1<em>$2</em>");
  return s.replace(/\u0000(\d+)\u0000/g, (_, n: string) => `<code>${codes[Number(n)]}</code>`);
}

/** Block Markdown (an idea body) to safe HTML. */
export function render(md: string): string {
  const out: string[] = [];
  let list: "ul" | "ol" | null = null;
  let para: string[] = [];
  let fence: string | null = null;
  let code: string[] = [];

  const flushPara = () => {
    if (para.length) out.push(`<p>${para.map(inline).join("<br>")}</p>`);
    para = [];
  };
  const closeList = () => {
    if (list) out.push(`</${list}>`);
    list = null;
  };

  for (const line of md.replace(/\r\n?/g, "\n").split("\n")) {
    const t = line.trim();
    if (fence !== null) {
      if (t.startsWith(fence) && !t.split(fence[0]!).join("")) {
        out.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
        fence = null;
        code = [];
      } else {
        code.push(line);
      }
      continue;
    }
    if (t.startsWith("```") || t.startsWith("~~~")) {
      flushPara();
      closeList();
      fence = t.slice(0, 3);
      continue;
    }
    const item = /^\s*(?:([-*+])|\d+[.)])\s+(.*)$/.exec(line);
    if (item) {
      flushPara();
      const kind = item[1] ? "ul" : "ol";
      if (list !== kind) {
        closeList();
        out.push(`<${kind}>`);
        list = kind;
      }
      out.push(`<li>${inline(item[2]!)}</li>`);
    } else if (!t) {
      flushPara();
      closeList();
    } else {
      closeList();
      para.push(t);
    }
  }
  if (fence !== null) out.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
  flushPara();
  closeList();
  return out.join("\n");
}
