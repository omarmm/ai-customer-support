"""Tokenizer protocol and span validation for document chunking.

A ``TokenSpan`` is the normalized source region assigned to exactly one token.
The tokenizer adapter is responsible for obtaining raw offsets from the
underlying tokenizer; ``validate_raw_spans`` and ``normalize_spans`` enforce the
contract in §5 without adding, removing, reordering, or merging tokens.

Byte offsets are converted explicitly. A byte boundary that falls inside a
multi-byte code point is rejected rather than rounded to a neighbouring
character.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from app.rag.chunking.exceptions import TokenizerContractError

__all__ = [
    "TokenSpan",
    "Tokenizer",
    "convert_byte_spans",
    "normalize_byte_spans",
    "normalize_spans",
    "validate_identity",
    "validate_raw_spans",
]


@dataclass(frozen=True)
class TokenSpan:
    """A source region assigned to one token.

    Offsets are Unicode code-point indexes into the original source text.
    ``start_offset`` is inclusive and ``end_offset`` is exclusive. Validation
    is performed by :func:`validate_raw_spans` so that invalid raw spans are
    reported through the typed tokenizer contract error.
    """

    start_offset: int
    end_offset: int


class Tokenizer(Protocol):
    """Injected tokenizer contract.

    ``identity`` must be stable and identify the implementation, library
    version, model or encoding, pinned revision, and any flags that affect
    tokenization output. ``tokenize`` must be deterministic, offline, and
    side-effect free.
    """

    @property
    def identity(self) -> str: ...

    def tokenize(self, text: str) -> tuple[TokenSpan, ...]: ...


def validate_identity(identity: str) -> str:
    """Return a non-empty tokenizer identity or raise ``TokenizerContractError``."""
    if not isinstance(identity, str) or not identity.strip():
        raise TokenizerContractError("empty_identity")
    return identity


def validate_raw_spans(
    text: str, raw_spans: Iterable[TokenSpan]
) -> tuple[TokenSpan, ...]:
    """Validate raw code-point spans against §5.2.

    Rejects out-of-bounds, zero-width, out-of-order, and overlapping spans, as
    well as any non-whitespace source character not covered by a span. Returns
    the spans unchanged in token order.
    """
    spans = tuple(raw_spans)
    length = len(text)

    previous: TokenSpan | None = None
    for index, span in enumerate(spans):
        if not isinstance(span, TokenSpan):
            raise TypeError("raw spans must be TokenSpan instances")

        if (
            span.start_offset < 0
            or span.start_offset > length
            or span.end_offset < 0
            or span.end_offset > length
        ):
            position = (
                span.start_offset
                if span.start_offset < 0 or span.start_offset > length
                else span.end_offset
            )
            raise TokenizerContractError(
                "span_out_of_bounds", token_index=index, position=position
            )

        if span.start_offset >= span.end_offset:
            raise TokenizerContractError(
                "zero_width_span", token_index=index, position=span.start_offset
            )

        if previous is not None:
            if span.start_offset < previous.start_offset:
                raise TokenizerContractError(
                    "spans_out_of_order", token_index=index, position=span.start_offset
                )
            if span.start_offset < previous.end_offset:
                raise TokenizerContractError(
                    "overlapping_spans", token_index=index, position=span.start_offset
                )

        previous = span

    if not spans:
        if text.strip():
            raise TokenizerContractError("missing_tokens", position=0)
        return ()

    cursor = 0
    for index, span in enumerate(spans):
        if text[cursor : span.start_offset].strip():
            raise TokenizerContractError(
                "non_whitespace_gap", token_index=index, position=cursor
            )
        cursor = span.end_offset

    if text[cursor:].strip():
        raise TokenizerContractError(
            "non_whitespace_gap", token_index=len(spans), position=cursor
        )

    return spans


def normalize_spans(
    text: str, raw_spans: Iterable[TokenSpan]
) -> tuple[TokenSpan, ...]:
    """Validate and normalize raw code-point spans against §5.3.

    Leading whitespace is assigned to the first token. Internal and trailing
    whitespace gaps are assigned to the preceding token, so the returned spans
    form a contiguous partition of the complete source text. The token count is
    never changed.
    """
    spans = validate_raw_spans(text, raw_spans)
    if not spans:
        return ()

    length = len(text)
    last_index = len(spans) - 1
    normalized: list[TokenSpan] = []

    for index, span in enumerate(spans):
        start_offset = 0 if index == 0 else span.start_offset
        end_offset = length if index == last_index else spans[index + 1].start_offset
        normalized.append(
            TokenSpan(start_offset=start_offset, end_offset=end_offset)
        )

    return tuple(normalized)


def convert_byte_spans(
    text: str, raw_spans: Iterable[TokenSpan]
) -> tuple[TokenSpan, ...]:
    """Convert raw UTF-8 byte spans to Unicode code-point spans.

    Byte boundaries that do not coincide with a code-point boundary, and byte
    offsets outside the encoded text, raise ``TokenizerContractError``.
    """
    spans = tuple(raw_spans)
    encoded_length = len(text.encode("utf-8"))

    byte_to_code_point = [-1] * (encoded_length + 1)
    byte_to_code_point[0] = 0

    byte_position = 0
    for code_point, character in enumerate(text):
        byte_position += len(character.encode("utf-8"))
        byte_to_code_point[byte_position] = code_point + 1

    def convert_boundary(index: int, value: int) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("span offsets must be integers")
        if value < 0 or value > encoded_length:
            raise TokenizerContractError(
                "span_out_of_bounds", token_index=index, position=value
            )
        code_point = byte_to_code_point[value]
        if code_point < 0:
            raise TokenizerContractError(
                "invalid_byte_boundary", token_index=index, position=value
            )
        return code_point

    converted: list[TokenSpan] = []
    for index, span in enumerate(spans):
        if not isinstance(span, TokenSpan):
            raise TypeError("raw spans must be TokenSpan instances")
        converted.append(
            TokenSpan(
                start_offset=convert_boundary(index, span.start_offset),
                end_offset=convert_boundary(index, span.end_offset),
            )
        )

    return tuple(converted)


def normalize_byte_spans(
    text: str, raw_spans: Iterable[TokenSpan]
) -> tuple[TokenSpan, ...]:
    """Convert UTF-8 byte spans, then validate and normalize them."""
    return normalize_spans(text, convert_byte_spans(text, raw_spans))
