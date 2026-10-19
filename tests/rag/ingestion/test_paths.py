from pathlib import Path

import app

from app.rag.ingestion.paths import default_repo_root, resolve_source_root


def test_default_repo_root_is_the_directory_containing_src():
    root = default_repo_root()

    assert (root / "src" / "app").is_dir()
    assert root == Path(app.__file__).resolve().parents[2]


def test_relative_paths_resolve_against_the_injected_repo_root(tmp_path):
    assert resolve_source_root("knowledge", repo_root=tmp_path) == (
        tmp_path / "knowledge"
    )
    assert resolve_source_root("docs/policies", repo_root=tmp_path) == (
        tmp_path / "docs" / "policies"
    )


def test_default_relative_path_resolves_against_the_repository_root(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    assert resolve_source_root("knowledge") == default_repo_root() / "knowledge"
    assert resolve_source_root("knowledge") != tmp_path / "knowledge"


def test_resolution_is_independent_of_the_working_directory(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    monkeypatch.chdir(first)
    from_first = resolve_source_root("knowledge")
    monkeypatch.chdir(second)
    from_second = resolve_source_root("knowledge")

    assert from_first == from_second == default_repo_root() / "knowledge"


def test_absolute_paths_are_returned_unchanged(tmp_path):
    absolute = tmp_path / "custom-root"

    assert resolve_source_root(str(absolute)) == absolute
    assert resolve_source_root(str(absolute), repo_root=tmp_path / "other") == absolute


def test_docker_layout_is_simulated_by_the_injected_repo_root():
    assert resolve_source_root("knowledge", repo_root=Path("/app")) == Path(
        "/app/knowledge"
    )
    assert resolve_source_root("/app/knowledge", repo_root=Path("/app")) == Path(
        "/app/knowledge"
    )
