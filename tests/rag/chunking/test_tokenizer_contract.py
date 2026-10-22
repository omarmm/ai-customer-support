from dataclasses import FrozenInstanceError

import pytest

from app.rag.chunking.exceptions import ChunkingError, TokenizerContractError
from app.rag.chunking.tokenizer import (
    TokenSpan,
    convert_byte_spans,
    normalize_byte_spans,
    normalize_spans,
    validate_identity,
    validate_raw_spans,
)


def spans(*pairs: tuple[int, int]) -> tuple[TokenSpan, ...]:
    return tuple(TokenSpan(start, end) for start, end in pairs)


def assert_normalized(text: str, normalized: tuple[TokenSpan, ...]) -> None:
    assert normalized
    assert normalized[0].start_offset == 0
    assert normalized[-1].end_offset == len(text)
    for left, right in zip(normalized, normalized[1:]):
        assert left.end_offset == right.start_offset
    for span in normalized:
        assert 0 <= span.start_offset < span.end_offset <= len(text)


# --- Test 1: raw span validation -------------------------------------------


def test_empty_text_returns_no_spans():
    assert validate_raw_spans("", ()) == ()
    assert normalize_spans("", ()) == ()


def test_whitespace_only_text_may_return_no_spans():
    assert normalize_spans(" \n\t\r ", ()) == ()


def test_non_whitespace_text_without_spans_is_rejected():
    with pytest.raises(TokenizerContractError) as caught:
        normalize_spans("SECRET customer payload", ())

    assert caught.value.reason == "missing_tokens"
    assert "SECRET customer payload" not in str(caught.value)


@pytest.mark.parametrize(
    ("raw", "position"),
    [
        (spans((-1, 1)), -1),
        (spans((0, 4)), 4),
        (spans((4, 5)), 4),
    ],
)
def test_out_of_bounds_spans_are_rejected(raw, position):
    with pytest.raises(TokenizerContractError) as caught:
        validate_raw_spans("abc", raw)

    assert caught.value.reason == "span_out_of_bounds"
    assert caught.value.position == position


def test_zero_width_spans_are_rejected():
    with pytest.raises(TokenizerContractError) as caught:
        validate_raw_spans("abc", spans((1, 1)))

    assert caught.value.reason == "zero_width_span"
    assert caught.value.token_index == 0


def test_reversed_span_is_rejected_as_zero_width():
    with pytest.raises(TokenizerContractError) as caught:
        validate_raw_spans("abc", spans((2, 1)))

    assert caught.value.reason == "zero_width_span"


def test_out_of_order_spans_are_rejected():
    with pytest.raises(TokenizerContractError) as caught:
        validate_raw_spans("a b", spans((2, 3), (0, 1)))

    assert caught.value.reason == "spans_out_of_order"
    assert caught.value.token_index == 1


def test_overlapping_spans_are_rejected():
    with pytest.raises(TokenizerContractError) as caught:
        validate_raw_spans("abc", spans((0, 2), (1, 3)))

    assert caught.value.reason == "overlapping_spans"
    assert caught.value.token_index == 1


def test_non_whitespace_leading_gap_is_rejected():
    with pytest.raises(TokenizerContractError) as caught:
        validate_raw_spans("Xabc", spans((1, 4)))

    assert caught.value.reason == "non_whitespace_gap"
    assert caught.value.token_index == 0
    assert caught.value.position == 0


def test_non_whitespace_internal_gap_is_rejected():
    with pytest.raises(TokenizerContractError) as caught:
        validate_raw_spans("abXcd", spans((0, 2), (3, 5)))

    assert caught.value.reason == "non_whitespace_gap"
    assert caught.value.token_index == 1


def test_non_whitespace_trailing_gap_is_rejected():
    with pytest.raises(TokenizerContractError) as caught:
        validate_raw_spans("abcX", spans((0, 3)))

    assert caught.value.reason == "non_whitespace_gap"
    assert caught.value.token_index == 1


def test_whitespace_gaps_are_valid_raw_input():
    raw = spans((1, 2), (5, 6))

    assert validate_raw_spans(" a \t b ", raw) == raw


def test_raw_span_validation_reports_no_document_content():
    with pytest.raises(TokenizerContractError) as caught:
        validate_raw_spans("SECRET payload", spans((0, 3)))

    assert "SECRET" not in str(caught.value)
    assert "payload" not in str(caught.value)


# --- Test 2: normalization --------------------------------------------------


def test_leading_whitespace_is_assigned_to_the_first_token():
    normalized = normalize_spans("  ab", spans((2, 3), (3, 4)))

    assert normalized == spans((0, 3), (3, 4))
    assert "  ab"[normalized[0].start_offset : normalized[0].end_offset] == "  a"


def test_internal_whitespace_is_assigned_to_the_preceding_token():
    normalized = normalize_spans("a  b", spans((0, 1), (3, 4)))

    assert normalized == spans((0, 3), (3, 4))


def test_trailing_whitespace_is_assigned_to_the_last_token():
    normalized = normalize_spans("ab  ", spans((0, 1), (1, 2)))

    assert normalized == spans((0, 1), (1, 4))


def test_already_contiguous_spans_are_unchanged():
    raw = spans((0, 1), (1, 2), (2, 3))

    assert normalize_spans("abc", raw) == raw


def test_normalization_preserves_the_raw_token_count():
    raw = spans((1, 2), (3, 4), (5, 6), (7, 8))

    assert len(normalize_spans(" a b c d ", raw)) == len(raw)


@pytest.mark.parametrize(
    ("text", "raw"),
    [
        ("  ab", spans((2, 3), (3, 4))),
        ("a  b", spans((0, 1), (3, 4))),
        ("ab  ", spans((0, 1), (1, 2))),
    ],
)
def test_normalization_produces_a_complete_partition(text, raw):
    normalized = normalize_spans(text, raw)

    assert_normalized(text, normalized)
    assert len(normalized) == len(raw)


def test_span_is_frozen():
    span = TokenSpan(0, 1)

    with pytest.raises(FrozenInstanceError):
        span.start_offset = 1  # type: ignore[misc]


# --- Byte-to-code-point conversion -----------------------------------------


def test_byte_spans_are_converted_to_code_points():
    text = "aé b"

    converted = convert_byte_spans(text, spans((0, 1), (1, 3), (3, 4), (4, 5)))

    assert converted == spans((0, 1), (1, 2), (2, 3), (3, 4))
    assert text[converted[1].start_offset : converted[1].end_offset] == "é"


def test_normalize_byte_spans_handles_leading_whitespace():
    text = "  é"
    normalized = normalize_byte_spans(text, spans((2, 4)))

    assert normalized == spans((0, 3))
    assert text[normalized[0].start_offset : normalized[0].end_offset] == "  é"


def test_byte_spans_handle_four_byte_code_points():
    text = "😀a"

    converted = convert_byte_spans(text, spans((0, 4), (4, 5)))

    assert converted == spans((0, 1), (1, 2))


def test_byte_boundary_inside_a_code_point_is_rejected():
    with pytest.raises(TokenizerContractError) as caught:
        convert_byte_spans("é", spans((0, 1)))

    assert caught.value.reason == "invalid_byte_boundary"
    assert caught.value.position == 1


def test_byte_span_out_of_bounds_is_rejected():
    with pytest.raises(TokenizerContractError) as caught:
        convert_byte_spans("a", spans((0, 2)))

    assert caught.value.reason == "span_out_of_bounds"


def test_empty_text_has_no_byte_spans():
    assert convert_byte_spans("", ()) == ()
    assert normalize_byte_spans("", ()) == ()


# --- Tokenizer identity and error taxonomy ---------------------------------


def test_valid_identity_is_returned_unchanged():
    identity = "fixture-tokenizer|1.0|unicode-codepoints"

    assert validate_identity(identity) == identity


@pytest.mark.parametrize("identity", ["", "   ", "\n\t"])
def test_empty_identity_is_rejected(identity):
    with pytest.raises(TokenizerContractError) as caught:
        validate_identity(identity)

    assert caught.value.reason == "empty_identity"
    assert caught.value.error_type == "tokenizer_contract"


def test_tokenizer_contract_error_derives_from_chunking_error():
    assert issubclass(TokenizerContractError, ChunkingError)
    assert ChunkingError.error_type == "chunking_error"
    assert TokenizerContractError.error_type == "tokenizer_contract"


def test_tokenizer_contract_error_carries_identifiers_only():
    error = TokenizerContractError(
        "span_out_of_bounds", token_index=2, position=17
    )

    assert error.reason == "span_out_of_bounds"
    assert error.token_index == 2
    assert error.position == 17
    assert "token_index=2" in str(error)
    assert "position=17" in str(error)
