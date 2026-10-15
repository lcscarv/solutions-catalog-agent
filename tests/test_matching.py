from catalog_action.matching import field_contains, normalize


def test_normalize_strips_case_accents_and_spaces():
    assert normalize("  Saúde   Pública ") == "saude publica"


def test_field_contains_text_is_partial():
    assert field_contains("Financial Services", normalize("financial"))


def test_field_contains_list_matches_any_element():
    assert field_contains(["first-call", "databricks"], normalize("DataBricks"))


def test_field_contains_ignores_missing_and_non_text():
    assert not field_contains(None, "x")
    assert not field_contains(42, "4")
