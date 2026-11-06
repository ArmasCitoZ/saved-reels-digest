"""Tests for choosing the Whisper model from the computer's RAM (common.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "digest" / "scripts"))
from common import pick_whisper_model, total_ram_bytes  # noqa: E402

GB = 1024 ** 3


def test_small_machines_get_lighter_models():
    assert pick_whisper_model(2 * GB) == "tiny"
    assert pick_whisper_model(int(3.9 * GB)) == "tiny"
    assert pick_whisper_model(4 * GB) == "base"
    assert pick_whisper_model(int(7.8 * GB)) == "base"


def test_normal_and_big_machines_stay_on_small_on_cpu():
    assert pick_whisper_model(8 * GB) == "small"
    assert pick_whisper_model(64 * GB) == "small"


def test_gpu_with_enough_ram_uses_medium():
    assert pick_whisper_model(16 * GB, cuda=True) == "medium"
    assert pick_whisper_model(6 * GB, cuda=True) == "base"


def test_unknown_ram_falls_back_to_default():
    assert pick_whisper_model(None) == "small"


def test_ram_is_detected_on_this_machine():
    ram = total_ram_bytes()
    assert ram is not None and ram > 256 * 1024 ** 2
