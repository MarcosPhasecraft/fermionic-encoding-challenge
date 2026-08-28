"""Tests for scripts/update_leaderboard.py's caching layer -- the actual
correctness of a baseline's score is already covered by each baseline's
own tests (via harness.evaluate); these tests only cover the cache-hit/
miss/invalidate decisions, using a call-counting fake evaluate_baseline
so a cache hit can be proven by "the expensive function was never called
again", not just by the returned numbers matching.
"""

import scripts.update_leaderboard as update_leaderboard


def _counting_fake(monkeypatch):
    calls = []

    def fake_evaluate_baseline(encode_fn, order_fn, lx, ly):
        calls.append(lx)
        return (100 + lx, 10 + lx)

    monkeypatch.setattr(update_leaderboard, "evaluate_baseline", fake_evaluate_baseline)
    return calls


# --- scored_with_cache ---


def test_first_call_computes_everything_and_populates_cache(monkeypatch):
    calls = _counting_fake(monkeypatch)
    cache_entries = {}

    totals, maxes, any_recomputed = update_leaderboard.scored_with_cache(
        "fake", None, None, [3, 4], "fp1", cache_entries,
    )

    assert any_recomputed is True
    assert calls == [3, 4]
    assert cache_entries["fake"]["fingerprint"] == "fp1"
    assert cache_entries["fake"]["scores"]["3"] == {"total": 103, "max": 13}
    assert cache_entries["fake"]["scores"]["4"] == {"total": 104, "max": 14}


def test_second_call_same_fingerprint_never_calls_evaluate_baseline_again(monkeypatch):
    calls = _counting_fake(monkeypatch)
    cache_entries = {}
    update_leaderboard.scored_with_cache("fake", None, None, [3, 4], "fp1", cache_entries)
    calls.clear()

    totals, maxes, any_recomputed = update_leaderboard.scored_with_cache(
        "fake", None, None, [3, 4], "fp1", cache_entries,
    )

    assert any_recomputed is False
    assert calls == []  # the whole point: the expensive function never ran again
    assert totals == {update_leaderboard.SIZES.index(3): 103, update_leaderboard.SIZES.index(4): 104}


def test_fingerprint_change_forces_full_recompute(monkeypatch):
    # A baseline's own file changed -- every previously cached score for
    # it is potentially stale, so all of its sizes recompute, not just the
    # ones that happen to differ.
    calls = _counting_fake(monkeypatch)
    cache_entries = {}
    update_leaderboard.scored_with_cache("fake", None, None, [3, 4], "fp1", cache_entries)
    calls.clear()

    _, _, any_recomputed = update_leaderboard.scored_with_cache(
        "fake", None, None, [3, 4], "fp2", cache_entries,
    )

    assert any_recomputed is True
    assert calls == [3, 4]


def test_new_size_under_same_fingerprint_only_computes_the_new_one(monkeypatch):
    calls = _counting_fake(monkeypatch)
    cache_entries = {}
    update_leaderboard.scored_with_cache("fake", None, None, [3], "fp1", cache_entries)
    calls.clear()

    _, _, any_recomputed = update_leaderboard.scored_with_cache(
        "fake", None, None, [3, 4], "fp1", cache_entries,
    )

    assert any_recomputed is True
    assert calls == [4]  # size 3 reused, not recomputed


# --- _hash_file ---


def test_hash_file_same_content_same_hash(tmp_path):
    f1, f2 = tmp_path / "a.py", tmp_path / "b.py"
    f1.write_text("x = 1\n")
    f2.write_text("x = 1\n")
    assert update_leaderboard._hash_file(f1) == update_leaderboard._hash_file(f2)


def test_hash_file_different_content_different_hash(tmp_path):
    f1, f2 = tmp_path / "a.py", tmp_path / "b.py"
    f1.write_text("x = 1\n")
    f2.write_text("x = 2\n")
    assert update_leaderboard._hash_file(f1) != update_leaderboard._hash_file(f2)


# --- _harness_fingerprint ---


def test_harness_fingerprint_is_deterministic():
    assert update_leaderboard._harness_fingerprint() == update_leaderboard._harness_fingerprint()


def test_harness_fingerprint_changes_when_a_harness_file_changes(tmp_path, monkeypatch):
    harness_dir = tmp_path / "harness"
    harness_dir.mkdir()
    (harness_dir / "a.py").write_text("x = 1\n")
    monkeypatch.setattr(update_leaderboard, "REPO_ROOT", tmp_path)

    fp1 = update_leaderboard._harness_fingerprint()
    (harness_dir / "a.py").write_text("x = 2\n")
    fp2 = update_leaderboard._harness_fingerprint()

    assert fp1 != fp2


# --- _load_cache / _save_cache ---


def test_load_cache_missing_file_returns_empty_dict(tmp_path, monkeypatch):
    monkeypatch.setattr(update_leaderboard, "CACHE_PATH", tmp_path / "nope.json")
    assert update_leaderboard._load_cache() == {}


def test_load_cache_corrupt_json_returns_empty_dict(tmp_path, monkeypatch):
    path = tmp_path / "bad.json"
    path.write_text("not json{{{")
    monkeypatch.setattr(update_leaderboard, "CACHE_PATH", path)
    assert update_leaderboard._load_cache() == {}


def test_save_and_load_cache_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "cache.json"
    monkeypatch.setattr(update_leaderboard, "CACHE_PATH", path)
    data = {"_harness_fingerprint": "abc", "entries": {"jw": {"fingerprint": "x", "scores": {}}}}
    update_leaderboard._save_cache(data)
    assert update_leaderboard._load_cache() == data


# --- collect_memory_entries / write_memory_index ---


def test_collect_memory_entries_only_lists_baselines_with_a_memory_folder(tmp_path):
    (tmp_path / "alice.memory").mkdir()
    (tmp_path / "alice.memory" / "notes.md").write_text("# notes\n")
    (tmp_path / "bob.py").write_text("")  # no bob.memory/ at all

    entries = update_leaderboard.collect_memory_entries(
        tmp_path, [("alice", "Alice's Encoding"), ("bob", "Bob's Encoding")],
    )

    assert entries == [("alice", "Alice's Encoding", ["notes.md"])]


def test_collect_memory_entries_ignores_an_empty_memory_folder(tmp_path):
    (tmp_path / "alice.memory").mkdir()  # exists but no files in it

    entries = update_leaderboard.collect_memory_entries(tmp_path, [("alice", "Alice's Encoding")])

    assert entries == []


def test_collect_memory_entries_lists_multiple_files_sorted(tmp_path):
    memory_dir = tmp_path / "alice.memory"
    memory_dir.mkdir()
    (memory_dir / "z_later.md").write_text("")
    (memory_dir / "a_first.md").write_text("")

    entries = update_leaderboard.collect_memory_entries(tmp_path, [("alice", "Alice's Encoding")])

    assert entries == [("alice", "Alice's Encoding", ["a_first.md", "z_later.md"])]


def test_write_memory_index_links_to_the_right_files(tmp_path):
    memory_dir = tmp_path / "baselines" / "alice.memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "notes.md").write_text("")
    out_path = tmp_path / "MEMORY.md"

    update_leaderboard.write_memory_index(out_path, tmp_path / "baselines", [("alice", "Alice's Encoding")])

    content = out_path.read_text()
    assert "Alice's Encoding" in content
    assert "`alice`" in content
    assert "baselines/alice.memory/notes.md" in content
    assert "leads, not proven fact" in content  # the ECDSA-style caveat


def test_write_memory_index_omits_baselines_without_notes(tmp_path):
    (tmp_path / "baselines").mkdir()
    out_path = tmp_path / "MEMORY.md"

    update_leaderboard.write_memory_index(out_path, tmp_path / "baselines", [("bob", "Bob's Encoding")])

    content = out_path.read_text()
    assert "Bob's Encoding" not in content
    assert "Nothing here yet" in content
