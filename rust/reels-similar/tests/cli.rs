use std::io::Write;
use std::process::{Command, Output, Stdio};

use serde_json::{json, Value};

const ES: &str =
    "Cómo automatizar la transcripción de reuniones con inteligencia artificial y un modelo local";
const EN: &str =
    "How to automate meeting transcription with artificial intelligence and a free local model";
const OTHER_EN: &str =
    "Five quick workouts for building shoulder strength at home with resistance bands";

fn run(db: &Value, args: &[&str]) -> Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_reels-similar"))
        .arg("-")
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    child
        .stdin
        .take()
        .unwrap()
        .write_all(db.to_string().as_bytes())
        .unwrap();
    child.wait_with_output().unwrap()
}

fn json_out(db: &Value, args: &[&str]) -> Value {
    let out = run(db, args);
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    serde_json::from_slice(&out.stdout).unwrap()
}

fn reel(code: &str, caption: &str) -> Value {
    json!({"shortcode": code, "relevant": true, "caption": caption})
}

#[test]
fn prints_groups_by_shortcode() {
    let db = json!({"version": 1, "reels": {
        "AAA": reel("AAA", EN), "GYM": reel("GYM", OTHER_EN), "BBB": reel("BBB", EN), "ESP": reel("ESP", ES),
    }});
    let out = json_out(&db, &[]);
    assert_eq!(out["reels"], 4);
    assert_eq!(out["groups"], json!([["AAA", "BBB"]]));
    // ESP is a cross-language match for both English copies, which share a group
    assert_eq!(out["cross"], json!([["AAA", "ESP"], ["BBB", "ESP"]]));
}

#[test]
fn only_relevant_reels_with_text_count() {
    let mut not_relevant = reel("NOPE", EN);
    not_relevant["relevant"] = json!(null);
    let db = json!({"reels": {
        "AAA": reel("AAA", EN), "NOPE": not_relevant, "EMPTY": reel("EMPTY", "   "),
    }});
    let out = json_out(&db, &[]);
    assert_eq!(out["reels"], 1);
    assert_eq!(out["groups"], json!([]));
}

#[test]
fn collection_filter_ignores_case_and_spaces() {
    let mut a = reel("AAA", EN);
    a["collection"] = json!(" IA ");
    let mut b = reel("BBB", EN);
    b["collection"] = json!("Gym");
    let db = json!({"reels": {"AAA": a, "BBB": b}});
    assert_eq!(json_out(&db, &["--collection", "ia"])["reels"], 1);
    assert_eq!(json_out(&db, &[])["groups"], json!([["AAA", "BBB"]]));
}

#[test]
fn thresholds_are_options() {
    let db = json!({"reels": {"ESP": reel("ESP", ES), "ENG": reel("ENG", EN)}});
    assert_eq!(
        json_out(&db, &["--ngram-threshold", "0"])["cross"],
        json!([])
    );
    assert_eq!(
        json_out(&db, &["--threshold", "0.01"])["groups"],
        json!([["ESP", "ENG"]])
    );
}

#[test]
fn damaged_database_is_a_clear_error() {
    let out = run(&json!({"version": 1}), &[]);
    assert!(!out.status.success());
    assert!(String::from_utf8_lossy(&out.stderr).contains("no \"reels\" table"));
}

#[test]
fn bad_option_explains_usage() {
    let out = run(&json!({"reels": {}}), &["--threshold", "high"]);
    assert_eq!(out.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&out.stderr).contains("not a number"));
}
