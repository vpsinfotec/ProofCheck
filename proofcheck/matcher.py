"""Deterministic matching of expected values against PDF text.

For each expected value we decide EXACT / FUZZY / MISSING / SKIPPED, find the best
page and snippet, and build a character-level diff. Everything here is deterministic:
rapidfuzz scoring is a pure function of its inputs, and difflib is stdlib.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from rapidfuzz import fuzz
from rapidfuzz.fuzz import partial_ratio_alignment

from .models import DiffOp, MatchResult, Status
from .normalize import normalize, reverse_words


def _is_blank(value: object) -> bool:
    return value is None or str(value).strip() == ""


def build_diff(expected: str, best_match: str) -> list[DiffOp]:
    """Character-level diff describing how to turn ``expected`` into ``best_match``.

    Emits ``equal`` / ``delete`` / ``insert`` pairs. ``replace`` spans are decomposed
    into a delete (of the expected text) followed by an insert (of the match text) so
    any frontend can render <del>/<ins> without special-casing replace.
    """
    sm = SequenceMatcher(a=expected, b=best_match, autojunk=False)
    diff: list[DiffOp] = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            diff.append(("equal", expected[a1:a2]))
        elif op == "delete":
            diff.append(("delete", expected[a1:a2]))
        elif op == "insert":
            diff.append(("insert", best_match[b1:b2]))
        elif op == "replace":
            diff.append(("delete", expected[a1:a2]))
            diff.append(("insert", best_match[b1:b2]))
    return diff


class PreparedMatcher:
    """A run-scoped, normalized document with deterministic ties and result reuse.

    Exact hits never invoke fuzzy scoring. Only the winning fuzzy alignment is
    mapped to the original page, and repeated cells reuse an independent result.
    """

    def __init__(self, pages: dict[int, str], *, fuzzy_threshold: int = 90,
                 normalize_digits: bool = False, strip_punctuation: bool = False,
                 fold_diacritics: bool = False, reverse: bool = False):
        if not 0 <= fuzzy_threshold <= 100:
            raise ValueError("Fuzzy threshold must be between 0 and 100.")
        self.threshold = fuzzy_threshold
        self.reverse = reverse
        self.options = dict(normalize_digits=normalize_digits,
                            strip_punctuation=strip_punctuation,
                            fold_diacritics=fold_diacritics)
        self.pages = [(n, raw, normalize(raw, **self.options))
                      for n, raw in sorted(pages.items())]
        self.cache: dict[str, MatchResult] = {}
        self.spans: dict[int, list[tuple[int, int]]] = {}

    def match(self, expected: object, *, row: int = 0) -> MatchResult:
        from dataclasses import replace
        expected_str = "" if expected is None else str(expected)
        if expected_str not in self.cache:
            self.cache[expected_str] = self._match(expected_str)
        cached = self.cache[expected_str]
        return replace(cached, row=row, diff=list(cached.diff))

    def _match(self, expected: str) -> MatchResult:
        needle = normalize(expected, **self.options)
        if not needle:
            return MatchResult(row=0, expected=expected, status=Status.SKIPPED)
        needles = [needle]
        if self.reverse and (rev := reverse_words(needle)) != needle:
            needles.append(rev)

        # Sorted pages make exact and fuzzy ties stable regardless of dict order.
        for number, raw, hay in self.pages:
            if any(cand in hay for cand in needles):
                return MatchResult(row=0, expected=expected, status=Status.EXACT,
                                   page=number, best_match=expected, score=100)

        best_score = -1.0
        best = None
        for number, raw, hay in self.pages:
            if not hay:
                continue
            for cand in needles:
                score = fuzz.partial_ratio(cand, hay, score_cutoff=max(0, best_score))
                if score > best_score:
                    best_score = score
                    best = (number, raw, hay, cand)
        if best is None or best_score <= 0:
            return MatchResult(row=0, expected=expected, status=Status.MISSING)

        number, raw, hay, cand = best
        align = partial_ratio_alignment(cand, hay)
        snippet = ""
        if align is not None and align.dest_end > align.dest_start:
            if number not in self.spans:
                from .normalize import normalize_with_spans
                mapped, spans = normalize_with_spans(raw, **self.options)
                assert mapped == hay
                self.spans[number] = spans
            spans = self.spans[number]
            start = spans[align.dest_start][0]
            end = spans[align.dest_end - 1][1]
            snippet = raw[start:end].strip()
        return MatchResult(
            row=0, expected=expected,
            status=Status.FUZZY if best_score >= self.threshold else Status.MISSING,
            page=number, best_match=snippet or None, score=int(round(best_score)),
            diff=build_diff(needle, normalize(snippet, **self.options)) if snippet else [],
        )


def match_value(expected: object, pages: dict[int, str], *, fuzzy_threshold: int = 90,
                normalize_digits: bool = False, strip_punctuation: bool = False,
                fold_diacritics: bool = False, reverse: bool = False,
                row: int = 0) -> MatchResult:
    """Compatibility wrapper for single cells; use PreparedMatcher for a whole run."""
    return PreparedMatcher(pages, fuzzy_threshold=fuzzy_threshold,
                           normalize_digits=normalize_digits,
                           strip_punctuation=strip_punctuation,
                           fold_diacritics=fold_diacritics, reverse=reverse).match(expected, row=row)
