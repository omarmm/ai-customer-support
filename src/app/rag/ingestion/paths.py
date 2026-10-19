"""Repository-root and source-root resolution for knowledge ingestion.

Resolution is derived from the imported ``app`` package location rather than the
process working directory, so local runs and the Docker Compose layout
(``/app`` with ``PYTHONPATH=/app/src``) agree.

No file system I/O is performed here: paths are only joined and returned. The
effective source root is resolved once by the caller and reused unchanged for
every containment check.
"""

from pathlib import Path

import app


def default_repo_root() -> Path:
    """Return the repository root containing the ``src`` package.

    ``app.__file__`` is ``<repo>/src/app/__init__.py``, so parents are
    ``app``, ``src``, and then the repository root.
    """
    return Path(app.__file__).resolve().parents[2]


def resolve_source_root(configured: str, repo_root: Path | None = None) -> Path:
    """Resolve a configured source root.

    Absolute values are used unchanged. Relative values resolve against
    ``repo_root``, which defaults to :func:`default_repo_root`, never against
    the process working directory.
    """
    path = Path(configured)
    if path.is_absolute():
        return path

    root = default_repo_root() if repo_root is None else Path(repo_root)
    return root / path
