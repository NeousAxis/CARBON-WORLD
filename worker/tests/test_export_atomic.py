"""
test_export_atomic.py: exported JSON files are replaced atomically.

The web build prerenders 8000+ event pages, each reading web/data/export.json.
The exporter's plain write and copy let a reader see a half-written 17 MB file
when the hourly drain exported mid-build ("Unterminated string in JSON"), which
made the builds of 2026-10-13 20:00 and 2026-10-16 16:13 fail.

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_export_atomic.py -v -p no:anchorpy
"""

import json
import os
import sys

# Allow importing from worker/ when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import exporter  # noqa: E402


def test_write_replaces_the_file_in_one_step(tmp_path):
    target = tmp_path / "export.json"
    target.write_text('{"old": true}', encoding="utf-8")
    with open(target, encoding="utf-8") as reader:
        exporter._atomic_write_text(target, json.dumps({"new": True}))
        # A reader that opened the old file keeps reading a complete old file
        assert json.loads(reader.read()) == {"old": True}
    assert json.loads(target.read_text(encoding="utf-8")) == {"new": True}
    assert [p.name for p in tmp_path.iterdir()] == ["export.json"]


def test_copy_replaces_the_destination_in_one_step(tmp_path):
    src, dst = tmp_path / "a.json", tmp_path / "b.json"
    src.write_text('{"v": 2}', encoding="utf-8")
    dst.write_text('{"v": 1}', encoding="utf-8")
    old_inode = dst.stat().st_ino
    exporter._atomic_copy(src, dst)
    assert json.loads(dst.read_text(encoding="utf-8")) == {"v": 2}
    assert dst.stat().st_ino != old_inode  # a new file, swapped in by rename
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.json", "b.json"]


def test_no_plain_write_left_in_the_exporter():
    source = open(exporter.__file__, encoding="utf-8").read()
    assert "shutil.copy2(EXPORT_PATH" not in source
    assert "shutil.copy2(REVIEW_EXPORT_PATH" not in source
    assert ".write_text(json.dumps" not in source
