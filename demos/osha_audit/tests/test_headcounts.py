import pytest

from osha_audit.src.headcounts import SOURCES, parse_count


@pytest.mark.parametrize("phrase,value", [("639,000", 639000), ("1.6 million", 1600000), ("133,300", 133300)])
def test_parse_count(phrase, value):
    assert parse_count(phrase) == value


def test_parse_count_rejects_text():
    with pytest.raises(ValueError):
        parse_count("about 5 thousand")


def test_every_phrase_is_inside_its_quote():
    for label, _, _, quotes, phrases, _, _ in SOURCES:
        for p in phrases:
            assert any(p in q for q in quotes), label
