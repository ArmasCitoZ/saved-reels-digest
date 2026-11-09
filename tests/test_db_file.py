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


@pytest.mark.parametrize("content", ['{"version": 1, "reels": {"AAA', "[1, 2]", '{"version": 1}'])
def test_damaged_database_points_to_the_backup(home, content):
    common.BACKUP_PATH.write_text('{"reels": {}}', "utf-8")
    common.DB_PATH.write_text(content, "utf-8")
    with pytest.raises(SystemExit) as e:
        common.load_db()
    assert "damaged" in str(e.value) and str(common.BACKUP_PATH) in str(e.value)
    assert common.DB_PATH.read_text("utf-8") == content  # left alone for the user to inspect


def test_damaged_database_without_a_backup_says_so(home):
    common.DB_PATH.write_bytes(b"\xff\xfe not text")
    with pytest.raises(SystemExit) as e:
        common.load_db()
    assert "no backup" in str(e.value)


def test_missing_database_is_still_an_empty_one(home):
    assert common.load_db() == {"version": 1, "reels": {}}


def disk_full(*_args, **_kwargs):
    raise OSError(28, "No space left on device")


def test_full_disk_leaves_no_temporary_files(home, monkeypatch):
    common.save_db(db_with("first"))
    monkeypatch.setattr(common.json, "dump", disk_full)
    with pytest.raises(SystemExit) as e:
        common.save_db(db_with("second"))
    assert "No space left" in str(e.value) and "not changed" in str(e.value)
    assert caption_in(common.DB_PATH) == "first"
    assert sorted(p.name for p in home.iterdir()) == ["reels.backup.json", "reels.json"]


def test_interrupted_save_leaves_no_temporary_files(home, monkeypatch):
    def interrupted(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(common.json, "dump", interrupted)
    with pytest.raises(KeyboardInterrupt):
        common.save_db(db_with("first"))
    assert list(home.iterdir()) == []


def test_full_disk_during_backup_leaves_no_partial_copy(home, monkeypatch):
    common.save_db(db_with("first"))

    def half_copy(src, dst):
        Path(dst).write_text("{half", "utf-8")
        disk_full()

    monkeypatch.setattr(common.shutil, "copyfile", half_copy)
    common.save_db(db_with("second"))
    assert caption_in(common.DB_PATH) == "second"
    assert sorted(p.name for p in home.iterdir()) == ["reels.json"]
