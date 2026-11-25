"""db.py -h: the overview Claude reads first has to name every option of every command."""
import re

from test_db import run

# --collection is described once, for every command that takes it, below the list
SHARED = {"--help", "--collection"}


def overview_blocks(text):
    """{command: its lines in the db.py -h overview}, continuation lines included."""
    blocks, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"  db\.py (\w+)", line)
        if m:
            cur = m.group(1)
            blocks[cur] = blocks.get(cur, "") + line + "\n"
        elif cur and line.startswith(" " * 12):
            blocks[cur] += line + "\n"
        else:
            cur = None
    return blocks


def commands(text):
    return re.search(r"\{([a-z,]+)\}", text).group(1).split(",")


def test_overview_names_every_option_of_each_command(tmp_path):
    top = run(tmp_path, "-h")
    blocks = overview_blocks(top)
    missing = {}
    for cmd in commands(top):
        assert cmd in blocks, f"db.py {cmd} is not in the db.py -h overview"
        options = set(re.findall(r"(?<![\w-])(--[a-z][a-z-]+)", run(tmp_path, cmd, "-h"))) - SHARED
        absent = sorted(o for o in options if o not in blocks[cmd])
        if absent:
            missing[cmd] = absent
    assert not missing, f"options missing from the db.py -h overview: {missing}"


def test_overview_names_every_command_that_takes_collection(tmp_path):
    top = run(tmp_path, "-h")
    takes = [c for c in commands(top) if "--collection" in run(tmp_path, c, "-h")]
    sentence = top.split("accept --collection", 1)[0].rsplit("\n\n", 1)[1]
    for cmd in takes:
        assert re.search(rf"\b{cmd}\b", sentence), f"db.py -h does not say {cmd} takes --collection"
