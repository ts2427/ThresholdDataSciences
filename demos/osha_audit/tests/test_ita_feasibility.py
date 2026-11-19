import pandas as pd

from osha_audit.src.ita_feasibility import link_employer, parse_state_plans
from osha_audit.src.normalize import name_key


def test_parse_state_plans_asterisks():
    text = "Select a State Alabama Alaska* Connecticut** Texas Wyoming* New York** New Jersey**"
    full, public = parse_state_plans(text)
    assert full == {"AK", "WY"}
    assert public == {"CT", "NY", "NJ"}


def test_link_employer_name_then_ein():
    ita = pd.DataFrame({"company_name": ["Acme Inc", "Other", "Acme Holdings", "Zed"],
                        "establishment_name": ["Plant 1", "ACME, INC.", "Site 9", "Zed"],
                        "ein": ["111", "", "111", "222"]})
    ita["company_key"] = ita.company_name.map(name_key)
    ita["establishment_key"] = ita.establishment_name.map(name_key)
    linked, by_name, by_ein = link_employer(ita, ["Acme, Inc."])
    assert by_name == 2 and by_ein == 1
    assert set(linked.company_name) == {"Acme Inc", "Other", "Acme Holdings"}
