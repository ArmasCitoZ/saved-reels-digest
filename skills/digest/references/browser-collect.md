# Collecting saved links with browser tools

Use when Claude in Chrome or the built-in browser is available and the user prefers it.
The user must be logged into instagram.com in that browser.

1. Open `https://www.instagram.com/<their_username>/saved/all-posts/`
   (if you don't know the username, open `https://www.instagram.com/` and read it from
   the profile link, or ask).
2. Run this in the page (JavaScript tool). It scrolls slowly, gathers every saved
   link and keeps them in `window.__srd` so the output stays small:

```js
(async () => {
  const links = new Set(); let stable = 0, last = 0;
  for (let i = 0; i < 600 && stable < 6; i++) {
    document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]').forEach(a => {
      links.add(a.href.split('?')[0]);
    });
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 1500 + Math.random() * 1200));
    stable = links.size === last ? stable + 1 : 0; last = links.size;
  }
  window.__srd = [...links];
  return `collected ${links.size} links`;
})()
```

3. Read them out in chunks of 200: `window.__srd.slice(0, 200).join('\n')`, then
   `slice(200, 400)` and so on. Write them all to a text file, one per line.
4. `PY SCRIPTS/collect.py urls that_file.txt`, and continue with Step 2 of the skill.

If the page shows a login wall or a "try again later" notice, stop and tell the user.
