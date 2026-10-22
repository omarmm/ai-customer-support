"""Token-aware chunk assembly for knowledge documents.

The algorithm follows §6: a token window of at most ``max_tokens`` is cut at the
rightmost preferred boundary, then emitted as an exact source slice. Boundaries
are preferred in paragraph, sentence, then word order, with a hard cut at the
window limit when none applies. Consecutive windows overlap by at most
``overlap_tokens`` and always advance by at least one token.

The module is pure: it performs no I/O and never mutates input documents.
"""

from __future__ import annotations

from app.rag.chunking.contracts import Chunk, ChunkingConfig, DocumentChunking
from app.rag.chunking.tokenizer import TokenSpan, Tokenizer, normalize_spans
from app.rag.ingestion.contracts import KnowledgeDocument

__all__ = [
    "choose_cut",
    "chunk_document",
    "is_paragraph_boundary",
    "is_sentence_boundary",
    "is_word_boundary",
]


def is_paragraph_boundary(text: str, p: int) -> bool:
    """Return whether ``text[:p]`` ends with a blank-line run.

    The suffix is ``\\n[ \\t]*\\n[ \\t]*``, so only LF is recognized. This is
    an equivalent local suffix check to the regular expression in §6.3; it
    avoids materializing the entire prefix for every candidate boundary.
    """
    index = p
    while index > 0 and text[index - 1] in " \t":
        index -= 1

    if index == 0 or text[index - 1] != "\n":
        return False

    index -= 1
    while index > 0 and text[index - 1] in " \t":
        index -= 1

    return index > 0 and text[index - 1] == "\n"


def is_sentence_boundary(text: str, p: int) -> bool:
    """Return whether ``text[:p]`` ends with ``.``, ``!``, or ``?``.

    The punctuation must be followed by whitespace or end of text. Trailing
    whitespace before ``p`` is skipped, so the boundary identifies the sentence
    terminator rather than the whitespace itself.
    """
    r = p
    while r > 0 and text[r - 1].isspace():
        r -= 1

    return (
        r > 0
        and text[r - 1] in ".!?"
        and (r == len(text) or text[r].isspace())
    )


def is_word_boundary(text: str, p: int) -> bool:
    """Return whether ``p`` is adjacent to Unicode whitespace or end of text."""
    return (
        p == len(text)
        or text[p - 1].isspace()
        or text[p].isspace()
    )


def choose_cut(
    text: str,
    spans: tuple[TokenSpan, ...],
    i: int,
    j: int,
) -> int:
    """Choose the rightmost boundary of the highest available class.

    ``i`` is the current start token index and ``j`` the exclusive window end.
    Paragraph boundaries take priority over sentence boundaries, which take
    priority over word boundaries. When no predicate qualifies, the hard cut
    ``j`` is returned.
    """
    for predicate in (
        is_paragraph_boundary,
        is_sentence_boundary,
        is_word_boundary,
    ):
        for k in range(j, i, -1):
            if predicate(text, spans[k - 1].end_offset):
                return k

    return j


def chunk_document(
    document: KnowledgeDocument,
    tokenizer: Tokenizer,
    config: ChunkingConfig,
) -> DocumentChunking:
    """Split one knowledge document into token-bounded source slices."""
    content = document.content

    if not content.strip():
        return DocumentChunking(
            document_id=document.document_id,
            source_path=document.source_path,
            title=document.title,
            format=document.format,
            content_length=len(content),
            token_count=0,
            chunks=(),
        )

    spans = normalize_spans(content, tokenizer.tokenize(content))
    token_count = len(spans)

    chunks: list[Chunk] = []
    start = 0

    while True:
        window_end = min(start + config.max_tokens, token_count)
        cut = (
            choose_cut(content, spans, start, window_end)
            if window_end < token_count
            else window_end
        )

        chunks.append(
            Chunk.build(
                document_id=document.document_id,
                source_path=document.source_path,
                title=document.title,
                format=document.format,
                content=content[spans[start].start_offset : spans[cut - 1].end_offset],
                start_offset=spans[start].start_offset,
                end_offset=spans[cut - 1].end_offset,
                token_start=start,
                token_end=cut,
                chunk_index=len(chunks),
                chunking_config_id=config.config_id,
            )
        )

        if cut == token_count:
            break

        start = max(cut - config.overlap_tokens, start + 1)

    return DocumentChunking(
        document_id=document.document_id,
        source_path=document.source_path,
        title=document.title,
        format=document.format,
        content_length=len(content),
        token_count=token_count,
        chunks=tuple(chunks),
    )
