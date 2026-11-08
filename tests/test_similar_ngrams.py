"""db.py similar: finding the same idea told in two languages, via character n-grams."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import db  # noqa: E402

ES = "Cómo automatizar la transcripción de reuniones con inteligencia artificial y un modelo local"
EN = "How to automate meeting transcription with artificial intelligence and a free local model"
OTHER_EN = "Five quick workouts for building shoulder strength at home with resistance bands"
OTHER_ES = "Cinco recetas de cocina rápidas con pollo y arroz para preparar la comida de la semana"


def run(home, *reels, args=()):
    home.mkdir(parents=True, exist_ok=True)
    data = {"version": 1, "reels": {c: {"shortcode": c, "url": f"https://www.instagram.com/reel/{c}/",
                                        "relevant": True, "caption": t} for c, t in reels}}
    (home / "reels.json").write_text(json.dumps(data), encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "db.py"), "similar", *args],
                       env={**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"},
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_same_idea_in_two_languages_is_a_candidate(tmp_path):
    out = run(tmp_path, ("ESIDEA", ES), ("ENIDEA", EN), ("GYMVID", OTHER_EN), ("COCINA", OTHER_ES))
    assert "1 possible matches across languages" in out
    line = next(ln for ln in out.splitlines() if ln.startswith("- "))
    assert "ESIDEA" in line and "ENIDEA" in line
    assert "GYMVID" not in out and "COCINA" not in out


def test_unrelated_reels_in_two_languages_are_left_alone(tmp_path):
    out = run(tmp_path, ("GYMVID", OTHER_EN), ("COCINA", OTHER_ES))
    assert "No obvious duplicates" in out


def test_second_pass_can_be_turned_off(tmp_path):
    out = run(tmp_path, ("ESIDEA", ES), ("ENIDEA", EN), args=("--ngram-threshold", "0"))
    assert "across languages" not in out


def test_same_language_stays_with_the_word_comparison(tmp_path):
    out = run(tmp_path, ("ENIDEA", EN), ("ENCOPY", EN), ("GYMVID", OTHER_EN))
    assert "1 candidate groups" in out and "across languages" not in out


def test_ngrams_ignore_accents():
    assert db._char_ngrams(["transcripción"]) == db._char_ngrams(["transcripcion"])
    assert "auto" not in db._char_ngrams(["ia"])  # short words still produce a gram
    assert db._char_ngrams(["ia"]) == {"_ia_": 1}


def test_language_uses_whisper_then_common_words():
    assert db._language({"lang": "pt", "caption": "the and with"}) == "pt"
    assert db._language({"caption": "this is how you use the tool"}) == "en"
    assert db._language({"caption": "esta es la forma de usar la herramienta"}) == "es"
    assert db._language({"caption": "Claude Code MCP"}) is None


def test_duplicates_are_found_in_other_alphabets(tmp_path):
    out = run(tmp_path, ("RU0001", "Как настроить автоматизацию задач с помощью нейросети"),
              ("RU0002", "Настроить автоматизацию задач нейросети очень просто"),
              ("RU0003", "Лучшие рецепты пасты для ужина всей семьи"))
    assert "1 candidate groups" in out
    group = next(ln for ln in out.splitlines() if ln.startswith("- "))
    assert "RU0001" in group and "RU0002" in group and "RU0003" not in group


def test_words_with_other_accents_stay_whole():
    assert "automação" in db._tokens("A automação de tarefas")
    assert "créer" in db._tokens("Créer un agent")
    assert "c++" in db._tokens("Aprende C++ gratis")  # symbols inside tech words still count
