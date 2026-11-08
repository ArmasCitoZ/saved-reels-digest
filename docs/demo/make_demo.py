"""Regenerate docs/demo/demo.gif: real output of the real scripts, on invented data.

  python -m pip install pillow
  python docs/demo/make_demo.py [--font PATH_TO_A_MONOSPACE_TTF]

It builds a throwaway database with the reels below (no real accounts: every author
starts with demo_), runs the scripts against it and draws what they print. The digest
shown at the end is examples/digest.md. Re-run it when the output of those commands changes.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "digest" / "scripts"
OUT = Path(__file__).resolve().parent / "demo.gif"
FONTS = ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
         "/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Menlo.ttc", "C:/Windows/Fonts/consola.ttf")

COLUMNS, ROWS, SIZE, PAD = 88, 19, 15, 16
BG, FG, DIM, ACCENT, BAR = "#14171c", "#d7dae0", "#7f8794", "#6fd08c", "#232730"

CLAUDE_MD = ("Pon un CLAUDE.md corto en la raíz del proyecto con los comandos de test y las convenciones "
             "del repo para no repetirlo en cada sesión con Claude Code")
# (shortcode, author, relevant, caption, transcript language)
REELS = [
    ("DEMOclaude01", "demo_devcorner", True, CLAUDE_MD, "es"),
    ("DEMOclaude02", "demo_ana.codes", True, CLAUDE_MD + ", corto y al grano", "es"),
    ("DEMOclaude03", "demo_shipfast", True,
     "Automatización de pruebas con agentes: documentación, configuración y revisión de código", "es"),
    ("DEMOclaude04", "demo_laura.ai", True,
     "Automation of testing with agents: documentation, configuration and code revision", "en"),
    ("DEMOprompt01", "demo_promptlab", True,
     "Dale dos ejemplos de lo que te gusta en vez de adjetivos", "es"),
    ("DEMOtools01", "demo_shipfast", True, "Transcribe tus reuniones en local con Whisper y sin GPU", "es"),
    ("DEMOfood01", "demo_recetas", False, "Tortilla de patata en 10 minutos", "es"),
    ("DEMOfood02", "demo_recetas", False, "El mejor bizcocho de limón", "es"),
    ("DEMOtrip01", "demo_viajes", False, "5 pueblos que ver en otoño", "es"),
    ("DEMOmeme01", "demo_memes", None, "cuando el código funciona a la primera", None),
]


def build_database(home: Path) -> None:
    reels = {}
    for code, author, relevant, caption, lang in REELS:
        reels[code] = {"shortcode": code, "url": f"https://www.instagram.com/reel/{code}/", "author": author,
                       "added_at": 1761600000, "relevant": relevant, "caption": caption}
        if lang:
            reels[code]["lang"] = lang
    (home / "reels.json").write_text(json.dumps({"version": 1, "reels": reels}), "utf-8")


def script_output(home: Path, *args: str) -> list:
    env = {**os.environ, "SRD_HOME": str(home), "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(SCRIPTS / "db.py"), *args], env=env, check=True,
                       capture_output=True, text=True, encoding="utf-8")
    return [ln.replace(str(home), "~/saved-reels-digest") for ln in r.stdout.splitlines()]


def digest_top() -> list:
    lines = (ROOT / "examples" / "digest.md").read_text("utf-8").splitlines()
    end = next(n for n, ln in enumerate(lines) if ln.startswith("## Guardado"))
    return [ln for ln in lines[:end] if not ln.startswith(">")]


class Screen:
    def __init__(self, font_path: str):
        from PIL import ImageFont
        self.font = ImageFont.truetype(font_path, SIZE)
        self.cell = int(self.font.getlength("M"))
        self.row = SIZE + 6
        self.size = (self.cell * COLUMNS + PAD * 2, self.row * ROWS + PAD * 2 + 28)
        self.frames, self.times = [], []

    def draw(self, lines: list, ms: int) -> None:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", self.size, BG)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, self.size[0], 28), fill=BAR)
        d.text((PAD, 6), "saved-reels-digest · salida real de los scripts · datos inventados",
               font=self.font, fill=DIM)
        for n, (text, color) in enumerate(lines[-ROWS:]):
            shown = text if len(text) <= COLUMNS else text[: COLUMNS - 1] + "…"
            d.text((PAD, 28 + PAD + n * self.row), shown, font=self.font, fill=color)
        self.frames.append(img.quantize(colors=16, dither=0))
        self.times.append(ms)

    def command(self, cmd: str, output: list, hold: int) -> None:
        for end in range(0, len(cmd) + 1, max(1, len(cmd) // 4)):
            self.draw([("$ " + cmd[:end], ACCENT)], 90)
        self.draw([("$ " + cmd, ACCENT), *[(ln, FG) for ln in output]], hold)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--font", help="a monospace .ttf with accents, if none of the usual ones is found")
    a = ap.parse_args()
    font = a.font or next((f for f in FONTS if Path(f).exists()), None)
    if not font:
        sys.exit("No monospace font found: pass one with --font.")
    screen = Screen(font)
    with tempfile.TemporaryDirectory() as tmp:
        build_database(Path(tmp))
        screen.command("db.py status", script_output(Path(tmp), "status"), 3200)
        screen.command("db.py similar", script_output(Path(tmp), "similar"), 4200)
    screen.command("cat digest.md", digest_top(), 6000)
    screen.frames[0].save(OUT, save_all=True, append_images=screen.frames[1:],
                          duration=screen.times, loop=0)
    print(f"{OUT} ({OUT.stat().st_size // 1024} KB, {len(screen.frames)} frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
