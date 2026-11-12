//! Duplicate finder for saved reels.
//!
//! This is a port of `db.py similar` (skills/digest/scripts/db.py). It keeps the exact same
//! steps so both give the same groups:
//!
//! 1. words of any alphabet, minus common Spanish/English words, as TF-IDF vectors;
//!    reels whose cosine similarity reaches `threshold` end up in the same group;
//! 2. a second pass only between reels in different languages, comparing pieces of words
//!    (character 4-grams without accents), so "automatización" can meet "automation".
//!
//! Python stays the reference: when the two disagree, Python is right and this is a bug.

use std::collections::HashMap;

use unicode_general_category::{get_general_category, GeneralCategory as Gc};
use unicode_normalization::{char::canonical_combining_class, UnicodeNormalization};

/// Same list as `STOP` in db.py.
const STOP: &str =
    "a al algo como con de del el ella en es esa ese esta este esto hay la las le lo los
mas me mi muy no o para pero por que se si sin su sus te tu un una y ya yo the a an and are as at be
but by can do for from has have how i if in is it its just me my not of on or so that the this to up
was we what when with you your youre im dont like get got one all out more about now here there
will then them they their which who really very want need make use using";

const NGRAM: usize = 4;
const EN_MARKERS: &[&str] = &[
    "the", "and", "with", "this", "that", "you", "your", "for", "from", "have", "how", "what",
];
const ES_MARKERS: &[&str] = &[
    "el", "la", "los", "las", "con", "este", "esta", "que", "para", "por", "una", "como", "pero",
    "del",
];

/// One reel as the duplicate finder sees it.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Doc {
    /// Caption, transcript and slide text joined (`_full_text` in db.py).
    pub text: String,
    /// Language Whisper detected, if the reel was transcribed.
    pub lang: Option<String>,
}

impl Doc {
    pub fn new(text: &str) -> Self {
        Doc {
            text: text.to_string(),
            lang: None,
        }
    }

    pub fn with_lang(text: &str, lang: &str) -> Self {
        Doc {
            text: text.to_string(),
            lang: Some(lang.to_string()),
        }
    }
}

/// Result of [`find_similar`], as indexes into the input slice.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Similar {
    /// Groups of 2+ reels with the same wording, biggest first (ties keep input order).
    pub groups: Vec<Vec<usize>>,
    /// Pairs in different languages with similar spellings, not already grouped together.
    pub cross: Vec<(usize, usize)>,
}

/// Python's `\w`: letters, numbers and the underscore.
fn is_word(c: char) -> bool {
    c == '_'
        || matches!(
            get_general_category(c),
            Gc::UppercaseLetter
                | Gc::LowercaseLetter
                | Gc::TitlecaseLetter
                | Gc::ModifierLetter
                | Gc::OtherLetter
                | Gc::DecimalNumber
                | Gc::LetterNumber
                | Gc::OtherNumber
        )
}

/// Python's `str.isdigit()` for the words we keep: every character a decimal digit.
fn is_digits(w: &str) -> bool {
    !w.is_empty()
        && w.chars()
            .all(|c| get_general_category(c) == Gc::DecimalNumber)
}

/// Words worth comparing, like `_tokens` in db.py: the regex `[^\W_][\w+#.-]+` on the
/// lower-cased text, without stop words or plain numbers, and with `.`/`-` trimmed.
pub fn tokens(text: &str) -> Vec<String> {
    let stop: std::collections::HashSet<&str> = STOP.split_whitespace().collect();
    let low: Vec<char> = text.to_lowercase().chars().collect();
    let in_body = |c: char| is_word(c) || matches!(c, '+' | '#' | '.' | '-');
    let mut out = Vec::new();
    let mut i = 0;
    while i < low.len() {
        let c = low[i];
        if is_word(c) && c != '_' && i + 1 < low.len() && in_body(low[i + 1]) {
            let mut j = i + 1;
            while j < low.len() && in_body(low[j]) {
                j += 1;
            }
            let w: String = low[i..j].iter().collect();
            if !stop.contains(w.as_str()) && !is_digits(&w) {
                out.push(w.trim_matches(|c| c == '.' || c == '-').to_string());
            }
            i = j;
        } else {
            i += 1;
        }
    }
    out
}

/// Counts that remember the order in which each item first appeared (like Python's Counter).
pub type Counts = Vec<(String, u32)>;

fn count<I: IntoIterator<Item = String>>(items: I) -> Counts {
    let mut pos: HashMap<String, usize> = HashMap::new();
    let mut out: Counts = Vec::new();
    for it in items {
        match pos.get(&it) {
            Some(&k) => out[k].1 += 1,
            None => {
                pos.insert(it.clone(), out.len());
                out.push((it, 1));
            }
        }
    }
    out
}

/// Pieces of words, so cognates match (`_char_ngrams` in db.py). Accents are removed first.
pub fn char_ngrams(tokens: &[String]) -> Counts {
    let mut grams = Vec::new();
    for t in tokens {
        let mut w: Vec<char> = vec!['_'];
        w.extend(t.nfd().filter(|&c| canonical_combining_class(c) == 0));
        w.push('_');
        let n = w.len().saturating_sub(NGRAM - 1).max(1);
        for i in 0..n {
            grams.push(w[i..(i + NGRAM).min(w.len())].iter().collect());
        }
    }
    count(grams)
}

/// Whisper's language if there is one, else a guess from common words (`_language` in db.py).
pub fn language(doc: &Doc) -> Option<String> {
    if let Some(l) = doc.lang.as_deref().filter(|l| !l.is_empty()) {
        return Some(l.to_string());
    }
    let low = doc.text.to_lowercase();
    let letter = |c: char| c.is_ascii_lowercase() || "áéíóúñü".contains(c);
    let (mut en, mut es) = (0, 0);
    for w in low.split(|c: char| !letter(c)).filter(|w| !w.is_empty()) {
        en += EN_MARKERS.contains(&w) as i32;
        es += ES_MARKERS.contains(&w) as i32;
    }
    match en.cmp(&es) {
        std::cmp::Ordering::Equal => None,
        std::cmp::Ordering::Greater => Some("en".into()),
        std::cmp::Ordering::Less => Some("es".into()),
    }
}

/// A unit-length TF-IDF vector. `order` keeps Python's dict order so sums add up identically.
struct Vector {
    order: Vec<(u32, f64)>,
    lookup: HashMap<u32, f64>,
}

fn tfidf(docs: &[Counts]) -> Vec<Vector> {
    let mut ids: HashMap<&str, u32> = HashMap::new();
    let mut df: Vec<u32> = Vec::new();
    let docs_ids: Vec<Vec<(u32, u32)>> = docs
        .iter()
        .map(|d| {
            d.iter()
                .map(|(t, c)| {
                    let next = ids.len() as u32;
                    let id = *ids.entry(t.as_str()).or_insert(next);
                    if id as usize == df.len() {
                        df.push(0);
                    }
                    df[id as usize] += 1;
                    (id, *c)
                })
                .collect()
        })
        .collect();
    let n = docs.len() as f64;
    docs_ids
        .into_iter()
        .map(|d| {
            let raw: Vec<(u32, f64)> = d
                .iter()
                .map(|&(t, c)| {
                    (
                        t,
                        (1.0 + (c as f64).ln()) * ((n + 1.0) / (df[t as usize] as f64 + 0.5)).ln(),
                    )
                })
                .collect();
            let sq = raw.iter().fold(0.0, |s, &(_, x)| s + x * x);
            let norm = if sq.sqrt() == 0.0 { 1.0 } else { sq.sqrt() };
            let order: Vec<(u32, f64)> = raw.into_iter().map(|(t, x)| (t, x / norm)).collect();
            let lookup = order.iter().copied().collect();
            Vector { order, lookup }
        })
        .collect()
}

fn cosine(a: &Vector, b: &Vector) -> f64 {
    let (a, b) = if a.order.len() < b.order.len() {
        (a, b)
    } else {
        (b, a)
    };
    a.order.iter().fold(0.0, |s, (t, x)| {
        s + x * b.lookup.get(t).copied().unwrap_or(0.0)
    })
}

fn find(parent: &mut [usize], mut i: usize) -> usize {
    while parent[i] != i {
        parent[i] = parent[parent[i]];
        i = parent[i];
    }
    i
}

/// Groups of reels that probably say the same thing, plus cross-language candidates.
///
/// `ngram_threshold` of 0 turns the second pass off, like `--ngram-threshold 0`.
pub fn find_similar(docs: &[Doc], threshold: f64, ngram_threshold: f64) -> Similar {
    let toks: Vec<Vec<String>> = docs.iter().map(|d| tokens(&d.text)).collect();
    let vecs = tfidf(
        &toks
            .iter()
            .map(|t| count(t.iter().cloned()))
            .collect::<Vec<_>>(),
    );
    let n = docs.len();
    let mut parent: Vec<usize> = (0..n).collect();
    for i in 0..n {
        for j in i + 1..n {
            if cosine(&vecs[i], &vecs[j]) >= threshold {
                let (ri, rj) = (find(&mut parent, i), find(&mut parent, j));
                parent[ri] = rj;
            }
        }
    }
    let mut roots: Vec<usize> = Vec::new();
    let mut members: HashMap<usize, Vec<usize>> = HashMap::new();
    for i in 0..n {
        let r = find(&mut parent, i);
        members.entry(r).or_insert_with(|| {
            roots.push(r);
            Vec::new()
        });
        members.get_mut(&r).unwrap().push(i);
    }
    let mut groups: Vec<Vec<usize>> = roots
        .iter()
        .map(|r| members.remove(r).unwrap())
        .filter(|g| g.len() > 1)
        .collect();
    groups.sort_by_key(|g| std::cmp::Reverse(g.len())); // stable, like Python's sorted

    let mut cross = Vec::new();
    if ngram_threshold != 0.0 {
        let langs: Vec<Option<String>> = docs.iter().map(language).collect();
        let grams = tfidf(&toks.iter().map(|t| char_ngrams(t)).collect::<Vec<_>>());
        for i in 0..n {
            for j in i + 1..n {
                if let (Some(li), Some(lj)) = (&langs[i], &langs[j]) {
                    if li != lj
                        && find(&mut parent, i) != find(&mut parent, j)
                        && cosine(&grams[i], &grams[j]) >= ngram_threshold
                    {
                        cross.push((i, j));
                    }
                }
            }
        }
    }
    Similar { groups, cross }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Same sentences as tests/test_similar_ngrams.py
    const ES: &str = "Cómo automatizar la transcripción de reuniones con inteligencia artificial y un modelo local";
    const EN: &str =
        "How to automate meeting transcription with artificial intelligence and a free local model";
    const OTHER_EN: &str =
        "Five quick workouts for building shoulder strength at home with resistance bands";
    const OTHER_ES: &str =
        "Cinco recetas de cocina rápidas con pollo y arroz para preparar la comida de la semana";

    fn strs(v: &[&str]) -> Vec<String> {
        v.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn tokens_match_python() {
        // expected values come from db._tokens; "2026..." is not all digits, so it stays
        assert_eq!(
            tokens("Claude Code + n8n: 10 trucos para automatizar TODO en 2026..."),
            strs(&[
                "claude",
                "code",
                "n8n",
                "trucos",
                "automatizar",
                "todo",
                "2026"
            ])
        );
        assert_eq!(
            tokens("Usa C++ y C# con node.js -- ¡ya!"),
            strs(&["usa", "c++", "c#", "node.js"])
        );
        assert_eq!(
            tokens("Привет мир, это тест"),
            strs(&["привет", "мир", "это", "тест"])
        );
        assert_eq!(tokens("snake_case _x a1"), strs(&["snake_case", "a1"]));
    }

    #[test]
    fn ngrams_ignore_accents() {
        assert_eq!(
            char_ngrams(&strs(&["transcripción"])),
            char_ngrams(&strs(&["transcripcion"]))
        );
        assert_eq!(char_ngrams(&strs(&["ia"])), vec![("_ia_".to_string(), 1)]);
        let g = char_ngrams(&strs(&["auto"]));
        assert_eq!(
            g.iter().map(|(t, _)| t.as_str()).collect::<Vec<_>>(),
            ["_aut", "auto", "uto_"]
        );
    }

    #[test]
    fn language_uses_whisper_then_common_words() {
        assert_eq!(
            language(&Doc::with_lang("the and with", "pt")).as_deref(),
            Some("pt")
        );
        assert_eq!(language(&Doc::new(EN)).as_deref(), Some("en"));
        assert_eq!(language(&Doc::new(ES)).as_deref(), Some("es"));
        assert_eq!(language(&Doc::new("Claude Code")), None);
    }

    #[test]
    fn same_wording_is_grouped() {
        let docs = [Doc::new(EN), Doc::new(OTHER_EN), Doc::new(EN)];
        let s = find_similar(&docs, 0.3, 0.1);
        assert_eq!(s.groups, vec![vec![0, 2]]);
        assert!(s.cross.is_empty());
    }

    #[test]
    fn biggest_group_comes_first() {
        let docs = [OTHER_ES, EN, OTHER_ES, EN, EN].map(Doc::new);
        assert_eq!(
            find_similar(&docs, 0.3, 0.0).groups,
            vec![vec![1, 3, 4], vec![0, 2]]
        );
    }

    #[test]
    fn same_idea_in_two_languages_is_a_candidate() {
        let docs = [ES, EN, OTHER_EN, OTHER_ES].map(Doc::new);
        let s = find_similar(&docs, 0.3, 0.1);
        assert!(s.groups.is_empty());
        assert_eq!(s.cross, vec![(0, 1)]);
    }

    #[test]
    fn second_pass_can_be_turned_off() {
        let docs = [ES, EN].map(Doc::new);
        assert!(find_similar(&docs, 0.3, 0.0).cross.is_empty());
    }

    #[test]
    fn unrelated_reels_are_left_alone() {
        let docs = [OTHER_EN, OTHER_ES].map(Doc::new);
        assert_eq!(find_similar(&docs, 0.3, 0.1), Similar::default());
        assert_eq!(find_similar(&[], 0.3, 0.1), Similar::default());
    }
}
