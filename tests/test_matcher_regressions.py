import random

import pytest

from proofcheck.matcher import PreparedMatcher, match_value
from proofcheck.models import Status
from proofcheck.normalize import normalize, normalize_with_spans


def test_exact_skips_fuzzy_scoring(monkeypatch):
    def fail(*a, **kw):
        raise AssertionError('Exact matches must not do fuzzy work')
    monkeypatch.setattr('proofcheck.matcher.fuzz.partial_ratio', fail)
    assert match_value('John', {7: 'John', 2: 'John'}).page == 2


def test_document_normalized_once_and_duplicate_results_independent(monkeypatch):
    import proofcheck.matcher as module
    calls = []
    original = module.normalize
    def counted(text, **kw):
        calls.append(text)
        return original(text, **kw)
    monkeypatch.setattr(module, 'normalize', counted)
    m = PreparedMatcher({1: 'Alice Smith', 2: 'Bob Jones'})
    a = m.match('Alice Smith', row=2)
    b = m.match('Alice Smith', row=8)
    a.diff.append(('insert', 'changed'))
    assert b.row == 8 and not b.diff
    assert calls.count('Bob Jones') == 1
    assert len(calls) == 3


@pytest.mark.parametrize('value', ['!!!', '€—', '\u0301'])
def test_normalized_empty_is_skipped(value):
    assert match_value(value, {1: 'someone'}, strip_punctuation=True,
                       fold_diacritics=True, fuzzy_threshold=0).status is Status.SKIPPED


def test_no_text_or_similarity_never_passes_at_zero_threshold():
    for pages in ({}, {1: ''}, {1: 'zzz'}):
        assert match_value('abc', pages, fuzzy_threshold=0).status is Status.MISSING


def test_fuzzy_ties_choose_lowest_page():
    assert match_value('Gauttam Sharma', {9: 'Gautam Sharma', 2: 'Gautam Sharma'}).page == 2


def test_threshold_uses_unrounded_score(monkeypatch):
    monkeypatch.setattr('proofcheck.matcher.fuzz.partial_ratio', lambda *a, **kw: 89.6)
    assert match_value('abce', {1: 'abcd'}, fuzzy_threshold=90).status is Status.MISSING


def test_snippet_offsets_after_whitespace_and_ligatures():
    raw = 'Header' + (' ' * 300) + 'ﬃ Straße Café\nGautam Sharma'
    result = match_value('Gauttam Sharma', {1: raw}, fold_diacritics=True)
    assert result.best_match == 'Gautam Sharma'


@pytest.mark.parametrize('options', [{}, {'strip_punctuation': True},
    {'fold_diacritics': True}, {'normalize_digits': True, 'fold_diacritics': True, 'strip_punctuation': True}])
def test_unicode_span_map_matches_authoritative_normalization(options):
    rng = random.Random(23)
    for _ in range(60):
        raw = ''.join(rng.choices('Aéßﬃİ \t\n\u0301١—가가', k=50))
        actual, spans = normalize_with_spans(raw, **options)
        assert actual == normalize(raw, **options)
        assert len(spans) == len(actual)
        assert all(0 <= a <= b <= len(raw) for a, b in spans)
