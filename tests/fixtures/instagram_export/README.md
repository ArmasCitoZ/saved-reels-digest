# Instagram export fixture

A trimmed, fully invented copy of the folder layout Instagram produces with
*Download your information → Saved → JSON*. Every username and shortcode is
made up (`demo_*`, `DFix*`); no real account data is stored here.

What it covers:

- `saved/saved_posts.json`: five saved links, including `/p/`, `/reel/`, a
  `?igsh=` tracking parameter and the `/<user>/reel/<code>` form.
- `saved/saved_collections.json`: one collection with English keys (`IA`) and
  one exported with Spanish keys (`Colección` / `Nombre`, `Recetas`).
- `likes/liked_posts.json`: a liked (not saved) post that must be ignored.

If Instagram changes its export format, update these files with the new shape
(anonymized the same way) and the tests will show what broke.
