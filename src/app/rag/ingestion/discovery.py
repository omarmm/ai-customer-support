"""Deterministic discovery of knowledge documents.

Discovery never reads file content. It walks the source tree in a deterministic
order, classifies entries, applies the per-run document limit to the sorted
candidates, and reports every discovered file exactly once as either a
candidate or a skipped entry.

Structural failures (missing, non-directory, or unreadable source root, and
directory traversal failures at any level) raise ``SourceRootError`` and abort
discovery. Per-file problems are not this component's responsibility; they are
classified while loading.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from app.rag.ingestion.contracts import (
    SKIPPED_DOCUMENT_LIMIT_EXCEEDED,
    SKIPPED_UNSUPPORTED_FORMAT,
    SkippedEntry,
)
from app.rag.ingestion.exceptions import SourceRootError

_MARKDOWN_SUFFIX = ".md"
_TEXT_SUFFIX = ".txt"


@dataclass(frozen=True)
class DiscoveryPlan:
    """Discovery outcome.

    ``candidates`` is the processed set: relative POSIX paths of supported
    documents that are within the per-run limit, sorted ascending. ``skipped``
    reports unsupported files and candidates excluded by the limit, sorted
    ascending by path.
    """

    candidates: tuple[str, ...]
    skipped: tuple[SkippedEntry, ...]


def discover(source_root: Path, max_documents_per_run: int) -> DiscoveryPlan:
    """Discover knowledge documents beneath ``source_root``.

    The source root is checked structurally before traversal. Candidates are
    sorted before the limit is applied, so the same tree and configuration
    always produce the same plan. Content is never read here.
    """
    root = Path(source_root)
    _require_readable_root(root)

    candidates: list[str] = []
    skipped: list[SkippedEntry] = []
    _walk(root, root, candidates, skipped)

    candidates.sort()
    skipped.sort(key=lambda entry: entry.path)

    processed = candidates[:max_documents_per_run]
    excluded = candidates[max_documents_per_run:]
    skipped.extend(
        SkippedEntry(path=path, reason=SKIPPED_DOCUMENT_LIMIT_EXCEEDED)
        for path in excluded
    )
    skipped.sort(key=lambda entry: entry.path)

    return DiscoveryPlan(candidates=tuple(processed), skipped=tuple(skipped))


def _require_readable_root(root: Path) -> None:
    if not root.exists():
        raise SourceRootError(str(root))
    if not root.is_dir():
        raise SourceRootError(str(root))

    try:
        with os.scandir(root) as entries:
            next(entries, None)
    except OSError as exc:
        raise SourceRootError(str(root)) from exc


def _walk(
    directory: Path,
    root: Path,
    candidates: list[str],
    skipped: list[SkippedEntry],
) -> None:
    try:
        with os.scandir(directory) as raw_entries:
            entries = sorted(raw_entries, key=lambda entry: entry.name)
    except OSError as exc:
        raise SourceRootError(_relative(directory, root)) from exc

    for entry in entries:
        try:
            is_directory = entry.is_dir(follow_symlinks=False)
            is_symlink = entry.is_symlink()

            if is_directory:
                _walk(Path(entry.path), root, candidates, skipped)
                continue

            if is_symlink and entry.is_dir(follow_symlinks=True):
                # Directory symlinks are never traversed or reported.
                continue

            if not is_symlink and not entry.is_file(follow_symlinks=False):
                # FIFO, socket, or device: outside the file contract.
                continue
        except OSError as exc:
            raise SourceRootError(_relative(Path(entry.path), root)) from exc

        relative_path = _relative(Path(entry.path), root)
        name = entry.name.lower()
        if name.endswith(_MARKDOWN_SUFFIX) or name.endswith(_TEXT_SUFFIX):
            candidates.append(relative_path)
        else:
            skipped.append(
                SkippedEntry(
                    path=relative_path,
                    reason=SKIPPED_UNSUPPORTED_FORMAT,
                )
            )


def _relative(path: Path, root: Path) -> str:
    if path == root:
        return str(root)
    return path.relative_to(root).as_posix()
