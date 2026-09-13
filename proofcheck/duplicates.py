"""Review repeated words and full-value occurrences without changing match verdicts.

All inputs have already been normalized. Counts describe extracted text, not people
or records. Adjacent equal words are collapsed only in a separate review index;
the authoritative exact/fuzzy comparison always uses the unmodified text.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import re

from .models import PageOccurrences, RepeatedWord


_REPEATED = re.compile(
    r"(?<![\w'’\-])(?P<word>\w+(?:['’\-]\w+)*)(?:\s+(?P=word))+(?![\w'’\-])"
)


def _word_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def full_occurrences(text: str, value: str):
    """Non-overlapping phrase spans; never count Ann inside Joanna or Annette."""
    if not value:
        return
    start = 0
    while (at := text.find(value, start)) >= 0:
        end = at + len(value)
        if (not at or not (_word_char(value[0]) and _word_char(text[at - 1]))) and (
            end == len(text) or not (_word_char(value[-1]) and _word_char(text[end]))
        ):
            yield at, end
            start = end
        else:
            start = at + 1


@dataclass(frozen=True)
class _Run:
    start: int
    end: int
    word: str
    count: int


def _collapse(text: str) -> tuple[str, list[_Run]]:
    pieces, runs = [], []
    cursor = length = 0
    for match in _REPEATED.finditer(text):
        prefix, word = text[cursor:match.start()], match.group("word")
        pieces.extend((prefix, word))
        length += len(prefix)
        runs.append(_Run(length, length + len(word), word, len(match.group().split())))
        length += len(word)
        cursor = match.end()
    if not runs:
        return text, []
    pieces.append(text[cursor:])
    return "".join(pieces), runs


class DuplicateAuditor:
    """Run-scoped review index; no fuzzy scoring or repeated page normalization."""

    def __init__(self, pages: list[tuple[int, str]]):
        self.pages = pages
        self.repeated_pages = []
        for number, text in pages:
            collapsed, runs = _collapse(text)
            if runs:
                self.repeated_pages.append((number, collapsed, runs, [r.start for r in runs]))

    def inspect(self, needle: str, needles: list[str]) -> tuple[list[PageOccurrences], list[RepeatedWord]]:
        occurrences = []
        for number, text in self.pages:
            if len(needles) == 1:
                count = sum(1 for _ in full_occurrences(text, needle))
            else:
                # Forward/reversed hits can overlap. Such a span represents one
                # occurrence; pick the earliest non-overlapping spans consistently.
                spans = sorted({span for cand in needles for span in full_occurrences(text, cand)})
                count, previous_end = 0, -1
                for start, end in spans:
                    if start >= previous_end:
                        count += 1
                        previous_end = end
            if count:
                occurrences.append(PageOccurrences(page=number, count=count))

        _, expected_runs = _collapse(needle)
        # At most one finding per word/location, with its largest consecutive run.
        findings: dict[tuple[int | None, str], int] = {}
        for run in expected_runs:
            findings[None, run.word] = max(findings.get((None, run.word), 0), run.count)
        candidates = list(dict.fromkeys(_collapse(cand)[0] for cand in needles))
        for number, text, runs, starts in self.repeated_pages:
            for cand in candidates:
                for start, end in full_occurrences(text, cand):
                    for i in range(bisect_left(starts, start), bisect_left(starts, end)):
                        run = runs[i]
                        if run.end <= end:
                            key = (number, run.word)
                            findings[key] = max(findings.get(key, 0), run.count)
        words = [RepeatedWord(word=word, count=count, page=page)
                 for (page, word), count in findings.items()]
        return occurrences, words
