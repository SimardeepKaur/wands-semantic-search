"""The spell rule: words the catalogue knows are never changed.

No Elasticsearch. The client is a mock whose term suggester always offers a
different word, so any known word that reached it would come back changed.
Run: python -m pytest tests/test_spell_rule.py
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from patch import correct

# "wishbone" stands for a word seen only in descriptions (the v1 bug).
RES = {"vocab": ["sofa", "chair", "wishbone", "velvet"]}


def suggester_that_always_changes():
    es = MagicMock()
    es.search.side_effect = lambda **kw: {"suggest": {"fix": [{"options": [
        {"text": "changed_" + kw["suggest"]["fix"]["text"]}]}]}}
    return es


def test_known_words_are_never_changed():
    es = suggester_that_always_changes()
    known = ["velvet", "sofa", "wishbone", "chair"]
    assert correct(es, dict(RES), known) == known
    es.search.assert_not_called()


def test_only_the_unknown_word_is_changed():
    es = suggester_that_always_changes()
    assert correct(es, dict(RES), ["velvet", "sofaa", "chair"]) == \
        ["velvet", "changed_sofaa", "chair"]
    assert es.search.call_count == 1


def test_short_unknown_words_are_left_alone():
    es = suggester_that_always_changes()
    assert correct(es, dict(RES), ["xl", "4"]) == ["xl", "4"]
    es.search.assert_not_called()
