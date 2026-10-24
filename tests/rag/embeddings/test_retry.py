"""Offline tests for the embeddings-local retry policy (approved D-3)."""

import ast
import inspect
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from app.rag.embeddings import retry as retry_module
from app.rag.embeddings.retry import EmbeddingRetryPolicy


def test_defaults_match_the_approved_specification():
    policy = EmbeddingRetryPolicy()

    assert policy.max_retries == 2
    assert policy.base_delay == 0.5
    assert policy.max_delay == 8.0
    assert policy.jitter == 0.0


def test_custom_values_are_accepted():
    policy = EmbeddingRetryPolicy(
        max_retries=4,
        base_delay=0.25,
        max_delay=2.0,
        jitter=0.1,
    )

    assert policy.max_retries == 4
    assert policy.base_delay == 0.25
    assert policy.max_delay == 2.0
    assert policy.jitter == 0.1


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_retries": -1},
        {"base_delay": -0.1},
        {"max_delay": -0.1},
        {"max_delay": 0.25, "base_delay": 0.5},
        {"jitter": -0.1},
    ],
)
def test_invalid_policies_are_rejected(overrides):
    with pytest.raises(ValueError):
        EmbeddingRetryPolicy(**overrides)


def test_policy_is_frozen():
    policy = EmbeddingRetryPolicy()

    with pytest.raises(FrozenInstanceError):
        policy.max_retries = 3  # type: ignore[misc]


def test_backoff_grows_exponentially_and_is_capped():
    policy = EmbeddingRetryPolicy(base_delay=0.5, max_delay=2.0)

    assert policy.delay_for_attempt(0) == 0.5
    assert policy.delay_for_attempt(1) == 1.0
    assert policy.delay_for_attempt(2) == 2.0
    assert policy.delay_for_attempt(3) == 2.0
    assert policy.delay_for_attempt(10) == 2.0


def test_zero_base_delay_produces_zero_backoff():
    policy = EmbeddingRetryPolicy(base_delay=0.0, max_delay=0.0)

    assert policy.delay_for_attempt(0) == 0.0
    assert policy.delay_for_attempt(5) == 0.0


def test_negative_attempt_is_rejected():
    with pytest.raises(ValueError):
        EmbeddingRetryPolicy().delay_for_attempt(-1)


def test_jitter_is_non_negative_and_bounded(monkeypatch):
    monkeypatch.setattr(retry_module.random, "uniform", lambda low, high: high)

    policy = EmbeddingRetryPolicy(base_delay=1.0, max_delay=4.0, jitter=0.5)

    # Capped delay 2.0 plus at most 50% jitter.
    assert policy.delay_for_attempt(1) == 3.0
    assert policy.delay_for_attempt(10) == 6.0


def test_no_jitter_keeps_the_exact_capped_delay(monkeypatch):
    def fail(*args):
        raise AssertionError("jitter must not be evaluated when jitter is 0")

    monkeypatch.setattr(retry_module.random, "uniform", fail)

    assert EmbeddingRetryPolicy(base_delay=1.0, max_delay=8.0).delay_for_attempt(3) == 8.0


def test_from_settings_reads_embedding_settings_only():
    settings = SimpleNamespace(
        embedding_max_retries=3,
        embedding_retry_base_delay=0.1,
        embedding_retry_max_delay=1.5,
        embedding_retry_jitter=0.2,
    )

    policy = EmbeddingRetryPolicy.from_settings(settings)

    assert policy == EmbeddingRetryPolicy(
        max_retries=3,
        base_delay=0.1,
        max_delay=1.5,
        jitter=0.2,
    )


def test_policy_does_not_import_the_llm_retry_module():
    tree = ast.parse(inspect.getsource(retry_module))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    assert not any(module.startswith("app.llm") for module in modules)
