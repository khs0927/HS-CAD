from dataclasses import replace
from types import SimpleNamespace

from image_to_cad.auto.active_analyzer import ActiveDrawingAnalysis
from image_to_cad.auto.auto_layer_mapper import guess_layer_mapping
from image_to_cad.auto.live_preview import apply_live_preview


class FakeAdapter:
    objects = []

    def __init__(self, *args, **kwargs):
        self.doc = SimpleNamespace(ModelSpace=self.objects)
        self.layers = []
        self.regenerated = False

    def connect(self):
        return None

    def get_active_document(self):
        return self.doc

    @staticmethod
    def _safe_get(obj, attr, default=None):
        return getattr(obj, attr, default)

    def _ensure_layer(self, layer):
        self.layers.append(layer)

    def _regen(self):
        self.regenerated = True


def _analysis(candidates):
    return ActiveDrawingAnalysis(
        generated_at="now",
        active_doc="fake.dwg",
        object_count=len(candidates),
        layer_counts={candidate.source_layer: 1 for candidate in candidates},
        entity_counts={},
        layer_entity_counts={},
        block_counts={},
        text_samples=[],
        dimension_count=0,
        candidates=candidates,
        warnings=[],
    )


def test_live_preview_blocks_layer_zero_by_default(monkeypatch):
    FakeAdapter.objects = [SimpleNamespace(Layer="0")]
    monkeypatch.setattr("src.adapters.zwcad_com_adapter.ZWCADCOMAdapter", FakeAdapter)
    monkeypatch.setattr("image_to_cad.auto.live_preview.create_undo_mark", lambda doc: True)

    result = apply_live_preview(_analysis([guess_layer_mapping("0", allow_layer_zero=True)]), allow_layer_zero=False)

    assert result.changed == 0
    assert result.skipped_layers["0"] == "protected_layer"


def test_live_preview_respects_min_confidence(monkeypatch):
    FakeAdapter.objects = [SimpleNamespace(Layer="Layer 1")]
    monkeypatch.setattr("src.adapters.zwcad_com_adapter.ZWCADCOMAdapter", FakeAdapter)
    monkeypatch.setattr("image_to_cad.auto.live_preview.create_undo_mark", lambda doc: True)
    candidate = replace(guess_layer_mapping("Layer 1"), target_layer="ETC", confidence=0.7, apply_by_default=True)

    result = apply_live_preview(_analysis([candidate]), min_confidence=0.82)

    assert result.changed == 0
    assert result.skipped_layers["Layer 1"] == "below_min_confidence"


def test_live_preview_respects_apply_by_default(monkeypatch):
    FakeAdapter.objects = [SimpleNamespace(Layer="DOOR1")]
    monkeypatch.setattr("src.adapters.zwcad_com_adapter.ZWCADCOMAdapter", FakeAdapter)
    monkeypatch.setattr("image_to_cad.auto.live_preview.create_undo_mark", lambda doc: True)
    candidate = replace(guess_layer_mapping("DOOR1"), apply_by_default=False, blocked_reason="manual_review")

    result = apply_live_preview(_analysis([candidate]), min_confidence=0.82)

    assert result.changed == 0
    assert result.skipped_layers["DOOR1"] == "manual_review"


def test_live_preview_changes_layer_without_save(monkeypatch):
    obj = SimpleNamespace(Layer="DOOR1")
    FakeAdapter.objects = [obj]
    monkeypatch.setattr("src.adapters.zwcad_com_adapter.ZWCADCOMAdapter", FakeAdapter)
    monkeypatch.setattr("image_to_cad.auto.live_preview.create_undo_mark", lambda doc: True)

    result = apply_live_preview(_analysis([guess_layer_mapping("DOOR1")]), min_confidence=0.82)

    assert result.changed == 1
    assert obj.Layer == "DOOR"
    assert result.to_dict()["saved"] is False
