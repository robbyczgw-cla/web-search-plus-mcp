"""Deterministic, query-conditioned passage selection for WSP 3.1."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Dict, List, Union


Span = Dict[str, Union[int, float, str]]
Ranker = Callable[[str, str], float]

_TOKEN_RE = re.compile(r"[^\W_]+(?:['\N{RIGHT SINGLE QUOTATION MARK}][^\W_]+)?", re.UNICODE)
_PARAGRAPH_BREAK_RE = re.compile(r"(?:\r?\n[\t \f\v]*){2,}")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])(?:[\"'\N{RIGHT SINGLE QUOTATION MARK}\)\]]*)\s+")


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int
    text: str


def nfc_text(text: str) -> str:
    """Return the canonical NFC string used for all span offsets."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return unicodedata.normalize("NFC", text)


def _tokens(text: str) -> List[str]:
    return [match.group(0).casefold() for match in _TOKEN_RE.finditer(text)]


def _trimmed_candidate(text: str, start: int, end: int) -> _Candidate | None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start >= end:
        return None
    return _Candidate(start, end, text[start:end])


def _split_long_segment(text: str, start: int, end: int, limit: int) -> List[_Candidate]:
    pieces: List[_Candidate] = []
    cursor = start
    while cursor < end:
        boundary = min(end, cursor + limit)
        if boundary < end:
            whitespace = text.rfind(" ", cursor + max(1, limit // 2), boundary + 1)
            newline = text.rfind("\n", cursor + max(1, limit // 2), boundary + 1)
            boundary = max(whitespace, newline)
            if boundary <= cursor:
                boundary = min(end, cursor + limit)
        candidate = _trimmed_candidate(text, cursor, boundary)
        if candidate is not None:
            pieces.append(candidate)
        cursor = boundary
        while cursor < end and text[cursor].isspace():
            cursor += 1
    return pieces


def _candidates(text: str, max_span_chars: int) -> List[_Candidate]:
    candidates: List[_Candidate] = []
    paragraph_start = 0
    paragraph_ranges = []
    for match in _PARAGRAPH_BREAK_RE.finditer(text):
        paragraph_ranges.append((paragraph_start, match.start()))
        paragraph_start = match.end()
    paragraph_ranges.append((paragraph_start, len(text)))

    for para_start, para_end in paragraph_ranges:
        sentence_start = para_start
        sentence_ranges = []
        for match in _SENTENCE_END_RE.finditer(text, para_start, para_end):
            sentence_ranges.append((sentence_start, match.start()))
            sentence_start = match.end()
        sentence_ranges.append((sentence_start, para_end))

        sentence_candidates: List[_Candidate] = []
        for start, end in sentence_ranges:
            candidate = _trimmed_candidate(text, start, end)
            if candidate is None:
                continue
            if candidate.end - candidate.start <= max_span_chars:
                sentence_candidates.append(candidate)
            else:
                sentence_candidates.extend(
                    _split_long_segment(text, candidate.start, candidate.end, max_span_chars)
                )
        candidates.extend(sentence_candidates)

        # Adjacent sentences make more useful passages when they fit. They are
        # deliberately candidates, not automatic output, so the ranker remains
        # the single selection seam.
        for index in range(len(sentence_candidates) - 1):
            start = sentence_candidates[index].start
            end = sentence_candidates[index + 1].end
            if end - start <= max_span_chars:
                candidates.append(_Candidate(start, end, text[start:end]))

    unique = {(candidate.start, candidate.end): candidate for candidate in candidates}
    return [unique[key] for key in sorted(unique)]


def _lexical_score(candidate_text: str, query: str, *, start: int, total: int) -> float:
    candidate_tokens = _tokens(candidate_text)
    if not candidate_tokens:
        return 0.0

    unique_tokens = set(candidate_tokens)
    lexical_density = min(len(candidate_tokens), 80) / max(1.0, len(candidate_text) / 8.0)
    diversity = len(unique_tokens) / len(candidate_tokens)
    density_score = min(1.0, lexical_density / 4.0) + (0.2 * diversity)
    position_prior = 0.08 * (1.0 - (start / max(1, total)))

    query_tokens = _tokens(query)
    if not query_tokens:
        return density_score + position_prior

    query_unique = set(query_tokens)
    term_overlap = len(query_unique & unique_tokens) / len(query_unique)
    query_shingles = set(zip(query_tokens, query_tokens[1:]))
    candidate_shingles = set(zip(candidate_tokens, candidate_tokens[1:]))
    shingle_overlap = (
        len(query_shingles & candidate_shingles) / len(query_shingles)
        if query_shingles
        else 0.0
    )
    occurrence_bonus = sum(candidate_tokens.count(term) for term in query_unique)
    occurrence_bonus = min(1.0, occurrence_bonus / max(1, len(query_tokens)))
    return (
        (4.0 * term_overlap)
        + (2.0 * shingle_overlap)
        + (0.5 * occurrence_bonus)
        + (0.2 * density_score)
        + position_prior
    )


def select_spans(
    text: str,
    query: str | None,
    *,
    max_spans: int = 3,
    max_span_chars: int = 600,
    ranker: Ranker | None = None,
) -> List[Span]:
    """Select deterministic, non-overlapping spans from NFC-normalized ``text``.

    ``ranker`` is the pluggable semantic-backend seam. When supplied, it is
    called as ``ranker(candidate_text, normalized_query)`` and must return a
    finite numeric score. The default ranker uses only lexical overlap,
    lexical density, and a mild position prior.
    """
    if isinstance(max_spans, bool) or not isinstance(max_spans, int):
        raise TypeError("max_spans must be an integer")
    if isinstance(max_span_chars, bool) or not isinstance(max_span_chars, int):
        raise TypeError("max_span_chars must be an integer")
    if query is not None and not isinstance(query, str):
        raise TypeError("query must be a string or None")
    if ranker is not None and not callable(ranker):
        raise TypeError("ranker must be callable or None")
    if max_spans <= 0 or max_span_chars <= 0:
        return []

    normalized = nfc_text(text)
    normalized_query = nfc_text(query or "").strip()
    ranked = []
    for candidate in _candidates(normalized, max_span_chars):
        if ranker is None:
            score = _lexical_score(
                candidate.text,
                normalized_query,
                start=candidate.start,
                total=len(normalized),
            )
        else:
            score = ranker(candidate.text, normalized_query)
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise TypeError("ranker scores must be numeric")
        score = float(score)
        if not math.isfinite(score):
            raise ValueError("ranker scores must be finite")
        ranked.append((score, candidate))

    ranked.sort(key=lambda item: (-item[0], item[1].start, item[1].end))
    selected: List[tuple[float, _Candidate]] = []
    for score, candidate in ranked:
        if any(
            candidate.start < existing.end and existing.start < candidate.end
            for _, existing in selected
        ):
            continue
        selected.append((score, candidate))
        if len(selected) >= max_spans:
            break

    selected.sort(key=lambda item: item[1].start)
    return [
        {
            "start": candidate.start,
            "end": candidate.end,
            "text": normalized[candidate.start:candidate.end],
            "score": score,
        }
        for score, candidate in selected
    ]
