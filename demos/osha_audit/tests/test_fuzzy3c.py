import pandas as pd

from osha_audit.src.fuzzy3c import candidate_pairs, canon, distinctive, generic_tokens, is_match

GEN = {"construction", "industries", "electric", "mechanical", "services", "service", "foods", "meat"}


def test_canon_united_states():
    assert canon("united states postal service") == "us postal service"


def test_generic_tokens_threshold():
    names = ["abc construction", "xyz construction", "def foods"]
    assert generic_tokens(names, min_count=2) == {"construction"}


def test_distinctive():
    assert distinctive("huber construction", GEN) == "huber"


def test_is_match_typos_accepted():
    assert is_match("neptune technolgy group", "neptune technology group", GEN)
    assert is_match("stampede meat", "stamtede meat", GEN)
    assert is_match("schreiber foods", "schrieber foods", GEN)


def test_is_match_generic_word_lookalikes_rejected():
    assert not is_match("ifs industries", "igs industries", GEN)      # short distinctive part differs
    assert not is_match("bear electric", "berg electric", GEN)
    assert not is_match("huber construction", "saber construction", GEN)


def test_candidate_pairs_blocking():
    E = pd.DataFrame({
        "entity": [1, 2, 3, 4],
        "name": ["acme widgets", "acme widget", "acme widgets", "acme widgetz"],
        "states": [frozenset({"TX"}), frozenset({"TX"}), frozenset({"OH"}),
                   frozenset({"OH", "TX", "FL", "GA", "AL"})],
        "nstates": [1, 1, 1, 5],
    })
    pairs = candidate_pairs(E, cutoff=90)
    assert (1, 2) in pairs                  # same state
    assert (1, 3) not in pairs              # different states, neither multi-state
    assert (1, 4) in pairs and (3, 4) in pairs   # multi-state side allows cross-state


def test_initials_no_usps_ups_collision():
    from osha_audit.src.step3c_preview import initials
    assert initials("us postal service") == "usps"
    assert initials("united states postal service") == "usps"
    assert initials("united parcel service") == "ups"
    assert initials("walmart") == ""
