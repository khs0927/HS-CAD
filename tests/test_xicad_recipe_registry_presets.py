from __future__ import annotations

from src.orchestrator.xicad_recipe_registry import get_xicad_recipe


def test_recipe_wal_preconditions():
    recipe = get_xicad_recipe("WAL")
    assert recipe is not None

    # Test missing parameters
    errs = recipe.validate_preconditions({})
    assert "WAL requires either 'thickness' or 'width' parameter." in errs

    # Test valid parameters
    errs = recipe.validate_preconditions({"thickness": 200})
    assert not errs

    # Test valid width parameter
    errs = recipe.validate_preconditions({"width": 150})
    assert not errs

    # Test scan state warning recommendation
    errs = recipe.validate_preconditions({"thickness": 200}, scan_state={"layers": {"A-BEAM": 1}})
    assert any("No existing wall layer" in e for e in errs)

    # Test scan state satisfied (should have no warning)
    errs = recipe.validate_preconditions({"thickness": 200}, scan_state={"layers": {"A-WALL-EXT": 1}})
    assert not errs


def test_recipe_col_preconditions():
    # COL is not registered in recipes but classify classify works. Wait, is COL in _RECIPES?
    # COL was not in _RECIPES, but we can test other registered ones like D1, W1, INS, BE, LC.
    assert get_xicad_recipe("COL") is None


def test_recipe_d1_w1_preconditions():
    recipe_d1 = get_xicad_recipe("D1")
    assert recipe_d1 is not None

    errs = recipe_d1.validate_preconditions({})
    assert "D1 command requires a size or width parameter." in errs
    assert "D1 requires reference target wall ('wall_handle' or 'target_wall') for integration." in errs

    errs = recipe_d1.validate_preconditions({"width": 900, "wall_handle": "H123"})
    assert not errs


def test_recipe_ins_preconditions():
    recipe = get_xicad_recipe("INS")
    assert recipe is not None

    errs = recipe.validate_preconditions({})
    assert "INS requires insulation 'thickness' or 'depth'." in errs

    errs = recipe.validate_preconditions({"thickness": 100})
    assert not errs


def test_recipe_be_preconditions():
    recipe = get_xicad_recipe("BE")
    assert recipe is not None

    errs = recipe.validate_preconditions({})
    assert "BE requires structural steel profile specifications (e.g., 'section' or 'profile')." in errs

    errs = recipe.validate_preconditions({"profile": "H-300x300x10x15"})
    assert not errs


def test_recipe_lc_preconditions():
    recipe = get_xicad_recipe("LC")
    assert recipe is not None

    errs = recipe.validate_preconditions({})
    assert "LC requires 'target_layer' or 'to_layer' parameter." in errs

    errs = recipe.validate_preconditions({"target_layer": "A-WALL"})
    assert not errs
