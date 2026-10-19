import os
from pathlib import Path

import pytest

from app.rag.ingestion.contracts import (
    SKIPPED_DOCUMENT_LIMIT_EXCEEDED,
    SKIPPED_UNSUPPORTED_FORMAT,
)
from app.rag.ingestion.discovery import DiscoveryPlan, discover
from app.rag.ingestion.exceptions import SourceRootError

RUNNING_AS_ROOT = getattr(os, "geteuid", lambda: -1)() == 0
SYMLINKS_SUPPORTED = hasattr(os, "symlink")
FIFOS_SUPPORTED = hasattr(os, "mkfifo")


def write(root: Path, relative: str, content: str = "content") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def entries(plan: DiscoveryPlan) -> list[tuple[str, str]]:
    return [(entry.path, entry.reason) for entry in plan.skipped]


def test_discovers_supported_files_recursively_with_posix_relative_paths(tmp_path):
    write(tmp_path, "a.md")
    write(tmp_path, "nested/b.txt")
    write(tmp_path, "nested/deeper/c.md")
    write(tmp_path, "notes.pdf")

    plan = discover(tmp_path, 100)

    assert plan.candidates == ("a.md", "nested/b.txt", "nested/deeper/c.md")
    assert entries(plan) == [("notes.pdf", SKIPPED_UNSUPPORTED_FORMAT)]


def test_extension_matching_is_case_insensitive(tmp_path):
    write(tmp_path, "UPPER.MD")
    write(tmp_path, "Mixed.Txt")

    assert discover(tmp_path, 100).candidates == ("Mixed.Txt", "UPPER.MD")


def test_unsupported_extensions_are_reported_case_insensitively(tmp_path):
    write(tmp_path, "notes.PDF")

    assert entries(discover(tmp_path, 100)) == [
        ("notes.PDF", SKIPPED_UNSUPPORTED_FORMAT)
    ]


def test_candidate_ordering_is_codepoint_ascending_and_case_sensitive(tmp_path):
    for name in ("a.md", "B.md", "A.md"):
        write(tmp_path, name)

    assert discover(tmp_path, 100).candidates == ("A.md", "B.md", "a.md")


def test_deep_nesting_uses_posix_separators(tmp_path):
    write(tmp_path, "a/b/c/d.md")

    assert discover(tmp_path, 100).candidates == ("a/b/c/d.md",)


def test_discovery_never_reads_file_content(tmp_path, monkeypatch):
    write(tmp_path, "a.md", "# A")
    write(tmp_path, "skip.pdf", "not a document")

    def fail(*args, **kwargs):
        raise AssertionError("discovery must not read file content")

    monkeypatch.setattr(Path, "open", fail)
    monkeypatch.setattr(Path, "read_bytes", fail)
    monkeypatch.setattr(Path, "read_text", fail)

    plan = discover(tmp_path, 100)

    assert plan.candidates == ("a.md",)
    assert entries(plan) == [("skip.pdf", SKIPPED_UNSUPPORTED_FORMAT)]


def test_candidates_are_sorted_before_the_limit_is_applied(tmp_path):
    for name in ("d.md", "b.md", "a.md", "c.md"):
        write(tmp_path, name)

    plan = discover(tmp_path, 2)

    assert plan.candidates == ("a.md", "b.md")
    assert entries(plan) == [
        ("c.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED),
        ("d.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED),
    ]


def test_limit_excluded_candidates_are_never_read(tmp_path, monkeypatch):
    write(tmp_path, "a.md")
    (tmp_path / "b.md").write_bytes(b"\xff\xfe")

    def fail(*args, **kwargs):
        raise AssertionError("excluded candidates must not be read")

    monkeypatch.setattr(Path, "open", fail)
    monkeypatch.setattr(Path, "read_bytes", fail)

    plan = discover(tmp_path, 1)

    assert plan.candidates == ("a.md",)
    assert entries(plan) == [("b.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED)]


def test_limit_excludes_only_after_sorting_across_directories(tmp_path):
    write(tmp_path, "b/one.md")
    write(tmp_path, "a/two.md")
    write(tmp_path, "c/three.md")

    plan = discover(tmp_path, 1)

    assert plan.candidates == ("a/two.md",)
    assert entries(plan) == [
        ("b/one.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED),
        ("c/three.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED),
    ]


def test_skipped_entries_are_sorted_across_reasons(tmp_path):
    write(tmp_path, "0.bin")
    for name in ("a.md", "b.md", "c.md"):
        write(tmp_path, name)

    plan = discover(tmp_path, 1)

    assert entries(plan) == [
        ("0.bin", SKIPPED_UNSUPPORTED_FORMAT),
        ("b.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED),
        ("c.md", SKIPPED_DOCUMENT_LIMIT_EXCEEDED),
    ]


def test_empty_root_returns_an_empty_plan(tmp_path):
    assert discover(tmp_path, 100) == DiscoveryPlan(candidates=(), skipped=())


def test_repeated_runs_produce_equivalent_plans(tmp_path):
    write(tmp_path, "b.md")
    write(tmp_path, "a.txt")
    write(tmp_path, "z.bin")

    assert discover(tmp_path, 1) == discover(tmp_path, 1)


def test_missing_root_raises_source_root_error(tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(SourceRootError) as excinfo:
        discover(missing, 100)

    assert excinfo.value.path == str(missing)


def test_root_that_is_not_a_directory_raises_source_root_error(tmp_path):
    root = write(tmp_path, "not-a-directory")

    with pytest.raises(SourceRootError) as excinfo:
        discover(root, 100)

    assert excinfo.value.path == str(root)


@pytest.mark.skipif(RUNNING_AS_ROOT, reason="root bypasses permission checks")
def test_unreadable_root_raises_source_root_error(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()
    root.chmod(0)
    try:
        with pytest.raises(SourceRootError):
            discover(root, 100)
    finally:
        root.chmod(0o700)


@pytest.mark.skipif(RUNNING_AS_ROOT, reason="root bypasses permission checks")
def test_unreadable_subdirectory_is_structural(tmp_path):
    root = tmp_path / "knowledge"
    subdirectory = root / "private"
    subdirectory.mkdir(parents=True)
    (subdirectory / "inside.md").write_text("content", encoding="utf-8")
    subdirectory.chmod(0)
    try:
        with pytest.raises(SourceRootError) as excinfo:
            discover(root, 100)
    finally:
        subdirectory.chmod(0o700)

    assert excinfo.value.path == "private"


@pytest.mark.skipif(not SYMLINKS_SUPPORTED, reason="symlinks unavailable")
def test_directory_symlinks_are_not_traversed_or_reported(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "hidden.md").write_text("content", encoding="utf-8")
    root = tmp_path / "knowledge"
    root.mkdir()
    os.symlink(outside, root / "linked")

    plan = discover(root, 100)

    assert plan.candidates == ()
    assert plan.skipped == ()


@pytest.mark.skipif(not SYMLINKS_SUPPORTED, reason="symlinks unavailable")
def test_symlink_to_directory_is_ignored_even_with_supported_name(tmp_path):
    real_directory = tmp_path / "real"
    real_directory.mkdir()
    (real_directory / "inside.md").write_text("content", encoding="utf-8")
    root = tmp_path / "knowledge"
    root.mkdir()
    os.symlink(real_directory, root / "folder.md")

    assert discover(root, 100).candidates == ()


@pytest.mark.skipif(not SYMLINKS_SUPPORTED, reason="symlinks unavailable")
def test_file_symlinks_are_classified_by_entry_name(tmp_path):
    target = write(tmp_path, "target.txt")
    os.symlink(target, tmp_path / "alias.md")

    assert discover(tmp_path, 100).candidates == ("alias.md", "target.txt")


@pytest.mark.skipif(not SYMLINKS_SUPPORTED, reason="symlinks unavailable")
def test_broken_symlinks_are_left_for_the_loader_to_classify(tmp_path):
    os.symlink(tmp_path / "missing.txt", tmp_path / "broken.md")

    plan = discover(tmp_path, 100)

    assert plan.candidates == ("broken.md",)
    assert plan.skipped == ()


@pytest.mark.skipif(not FIFOS_SUPPORTED, reason="FIFOs unavailable")
def test_non_regular_entries_are_ignored(tmp_path):
    os.mkfifo(tmp_path / "pipe")
    write(tmp_path, "doc.md")

    plan = discover(tmp_path, 100)

    assert plan.candidates == ("doc.md",)
    assert plan.skipped == ()
