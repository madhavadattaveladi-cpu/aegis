"""Tests for local file storage."""

from __future__ import annotations

import json

from aegis.storage.store import Storage, _slugify


def test_slugify():
    assert _slugify("Hello, World!") == "hello-world"
    assert _slugify("") == "untitled"


def test_save_json_roundtrip():
    storage = Storage(run_name="unit test")
    records = [{"url": "https://a.com", "ok": True}]
    path = storage.save_json(records, name="results")
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == records


def test_save_csv_uses_union_of_keys():
    storage = Storage(run_name="csv-test")
    records = [{"a": 1}, {"b": 2}]
    path = storage.save_csv(records, name="r")
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert "a" in header and "b" in header


def test_save_jsonl_one_line_per_record():
    storage = Storage()
    records = [{"i": 1}, {"i": 2}, {"i": 3}]
    path = storage.save_jsonl(records)
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == 3
    assert json.loads(lines[1]) == {"i": 2}
