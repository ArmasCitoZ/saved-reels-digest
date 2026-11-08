"""Backups and damaged files: reels.json holds hours of transcription work."""
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"))
import common  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "HOME", tmp_path)
    monkeypatch.setattr(common, "DB_PATH", tmp_path / "reels.json")
    monkeypatch.setattr(common, "BACKUP_PATH", tmp_path / "reels.backup.json")
    return tmp_path


def db_with(marker):
    return {"version": 1, "reels": {"AAAAA1": {"shortcode": "AAAAA1", "caption": marker}}}


def caption_in(path):
    return json.loads(path.read_text("utf-8"))["reels"]["AAAAA1"]["caption"]


def test_first_save_has_nothing_to_back_up(home):
    common.save_db(db_with("first"))
    assert not common.BACKUP_PATH.exists()


def test_save_keeps_the_previous_version(home):
    common.save_db(db_with("first"))
    common.save_db(db_with("second"))
    assert caption_in(common.BACKUP_PATH) == "first"
    assert caption_in(common.DB_PATH) == "second"


def test_backup_is_not_refreshed_within_the_day(home):
    common.save_db(db_with("first"))
    common.save_db(db_with("second"))
    common.save_db(db_with("third"))
    assert caption_in(common.BACKUP_PATH) == "first"


def test_backup_is_refreshed_after_a_day(home):
    common.save_db(db_with("first"))
    common.save_db(db_with("second"))
    old = time.time() - common.BACKUP_EVERY - 60
    os.utime(common.BACKUP_PATH, (old, old))
    common.save_db(db_with("third"))
    assert caption_in(common.BACKUP_PATH) == "second"


def test_a_failed_backup_does_not_block_the_save(home, monkeypatch):
    common.save_db(db_with("first"))

    def broken(*_):
        raise OSError("disk says no")

    monkeypatch.setattr(common.shutil, "copyfile", broken)
    common.save_db(db_with("second"))
    assert caption_in(common.DB_PATH) == "second"
