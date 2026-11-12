//! `reels-similar`: the duplicate groups of a reels.json, as JSON.
//!
//! ```text
//! reels-similar [PATH | -] [--threshold 0.3] [--ngram-threshold 0.1] [--collection NAME]
//! ```
//!
//! PATH defaults to the same database db.py uses ($SRD_HOME/reels.json, or
//! ~/saved-reels-digest/reels.json); `-` reads it from standard input. Only reels marked
//! relevant and with some text are compared, as in `db.py similar`. The output is
//!
//! ```json
//! {"reels": 120, "groups": [["CODE1", "CODE2"]], "cross": [["CODE3", "CODE4"]]}
//! ```

use std::io::Read;
use std::path::PathBuf;
use std::process::ExitCode;

use reels_core::{find_similar, Doc};
use serde_json::{json, Value};

const USAGE: &str =
    "usage: reels-similar [PATH | -] [--threshold 0.3] [--ngram-threshold 0.1] [--collection NAME]";

struct Args {
    path: Option<String>,
    threshold: f64,
    ngram_threshold: f64,
    collection: Option<String>,
}

fn parse_args(raw: &[String]) -> Result<Args, String> {
    let mut a = Args {
        path: None,
        threshold: 0.3,
        ngram_threshold: 0.1,
        collection: None,
    };
    let mut it = raw.iter();
    while let Some(arg) = it.next() {
        let mut value = |name: &str| it.next().cloned().ok_or(format!("{name} needs a value"));
        let number = |name: &str, v: String| {
            v.parse::<f64>()
                .map_err(|_| format!("{name}: not a number: {v}"))
        };
        match arg.as_str() {
            "-h" | "--help" => return Err(String::new()),
            "--threshold" => a.threshold = number(arg, value(arg)?)?,
            "--ngram-threshold" => a.ngram_threshold = number(arg, value(arg)?)?,
            "--collection" => a.collection = Some(value(arg)?),
            s if s.starts_with("--") => return Err(format!("unknown option {s}")),
            s if a.path.is_none() => a.path = Some(s.to_string()),
            s => return Err(format!("unexpected argument {s}")),
        }
    }
    Ok(a)
}

/// Same place as DB_PATH in common.py.
fn default_db() -> PathBuf {
    if let Some(h) = std::env::var_os("SRD_HOME") {
        return PathBuf::from(h).join("reels.json");
    }
    let home = std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .unwrap_or_default();
    PathBuf::from(home)
        .join("saved-reels-digest")
        .join("reels.json")
}

fn read_input(path: Option<&str>) -> Result<String, String> {
    match path {
        Some("-") => {
            let mut s = String::new();
            std::io::stdin()
                .read_to_string(&mut s)
                .map_err(|e| format!("cannot read standard input: {e}"))?;
            Ok(s)
        }
        p => {
            let p = p.map(PathBuf::from).unwrap_or_else(default_db);
            std::fs::read_to_string(&p).map_err(|e| format!("cannot read {}: {e}", p.display()))
        }
    }
}

/// `_full_text` in db.py.
fn full_text(r: &Value) -> String {
    let parts: Vec<&str> = ["caption", "transcript", "slides_text"]
        .iter()
        .map(|k| r.get(*k).and_then(Value::as_str).unwrap_or(""))
        .collect();
    parts.join(" ").trim().to_string()
}

/// `in_collection` in common.py (case-insensitive, surrounding spaces ignored).
fn in_collection(r: &Value, name: Option<&str>) -> bool {
    match name {
        None => true,
        Some(n) => {
            let c = r.get("collection").and_then(Value::as_str).unwrap_or("");
            c.trim().to_lowercase() == n.trim().to_lowercase()
        }
    }
}

fn run(a: &Args) -> Result<Value, String> {
    let text = read_input(a.path.as_deref())?;
    let db: Value =
        serde_json::from_str(&text).map_err(|e| format!("reels.json is damaged: {e}"))?;
    let reels = db
        .get("reels")
        .and_then(Value::as_object)
        .ok_or("reels.json is damaged: no \"reels\" table")?;
    let mut codes = Vec::new();
    let mut docs = Vec::new();
    for (code, r) in reels {
        let body = full_text(r);
        if r.get("relevant") == Some(&Value::Bool(true))
            && !body.is_empty()
            && in_collection(r, a.collection.as_deref())
        {
            let lang = r
                .get("lang")
                .and_then(Value::as_str)
                .filter(|l| !l.is_empty())
                .map(String::from);
            codes.push(
                r.get("shortcode")
                    .and_then(Value::as_str)
                    .unwrap_or(code)
                    .to_string(),
            );
            docs.push(Doc { text: body, lang });
        }
    }
    let s = find_similar(&docs, a.threshold, a.ngram_threshold);
    let names = |ix: &[usize]| ix.iter().map(|&i| codes[i].clone()).collect::<Vec<_>>();
    Ok(json!({
        "reels": docs.len(),
        "groups": s.groups.iter().map(|g| names(g)).collect::<Vec<_>>(),
        "cross": s.cross.iter().map(|&(i, j)| names(&[i, j])).collect::<Vec<_>>(),
    }))
}

fn main() -> ExitCode {
    let raw: Vec<String> = std::env::args().skip(1).collect();
    let args = match parse_args(&raw) {
        Ok(a) => a,
        Err(e) if e.is_empty() => {
            println!("{USAGE}");
            return ExitCode::SUCCESS;
        }
        Err(e) => {
            eprintln!("reels-similar: {e}\n{USAGE}");
            return ExitCode::from(2);
        }
    };
    match run(&args) {
        Ok(out) => {
            println!("{out}");
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("reels-similar: {e}");
            ExitCode::FAILURE
        }
    }
}
