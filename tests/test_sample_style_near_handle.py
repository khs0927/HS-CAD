from __future__ import annotations

from tools import sample_style_near_handle as sampler


class MockEntity:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class MockDoc:
    def __init__(self, entities):
        self.Name = "mock.dwg"
        self.FullName = "C:/cad/mock.dwg"
        self.ModelSpace = entities
        self._by_handle = {entity.Handle: entity for entity in entities}

    def HandleToObject(self, handle):
        return self._by_handle[handle]


def test_sample_style_near_handle_with_mocked_active_doc(monkeypatch):
    source = MockEntity(
        ObjectName="AcDbLine",
        Handle="A1",
        Layer="A-WALL",
        Color=256,
        Linetype="ByLayer",
        Lineweight=-1,
        StartPoint=[0, 0, 0],
        EndPoint=[1000, 0, 0],
    )
    nearby_text = MockEntity(
        ObjectName="AcDbText",
        Handle="T1",
        Layer="A-TEXT",
        Color=7,
        Linetype="ByLayer",
        Lineweight=-1,
        InsertionPoint=[100, 100, 0],
        Height=250.0,
        StyleName="지움EB",
    )
    nearby_block = MockEntity(
        ObjectName="AcDbBlockReference",
        Handle="B1",
        Layer="A-FORM",
        Color=256,
        Linetype="ByLayer",
        Lineweight=-1,
        InsertionPoint=[200, 200, 0],
        Name="*U123",
        EffectiveName="ZIUM_sheet_architect",
    )
    far_line = MockEntity(
        ObjectName="AcDbLine",
        Handle="F1",
        Layer="FAR",
        Color=1,
        Linetype="Hidden",
        Lineweight=0,
        StartPoint=[10000, 10000, 0],
        EndPoint=[11000, 10000, 0],
    )
    doc = MockDoc([source, nearby_text, nearby_block, far_line])
    monkeypatch.setattr(sampler, "connect_active_document", lambda: (None, doc))

    result = sampler.sample_style_near_handle("A1", active_selection=False, radius=1000, out_dir=None)

    assert result["source_handle"] == "A1"
    assert result["nearby_entity_count"] == 3
    assert ["A-WALL", 1] in result["dominant_layers"]
    assert ["TEXT", 1] in result["dominant_entity_types"]
    assert ["ZIUM_sheet_architect", 1] in result["block_effective_names"]
    assert result["recommended_generation_style"]["line_layer"] in {"A-WALL", "A-TEXT", "A-FORM"}
    assert result["recommended_generation_style"]["leader_style"] == "qleader_l_route"
    contract = result["grammar_contract"]
    assert contract["schema"] == "cad-drawing-grammar/1"
    assert contract["anchor"]["handle"] == "A1"
    assert contract["evidence"]["nearby_entity_count"] == 3
    assert len(contract["contract_digest"]) == 64
    assert contract["execution_authorized"] is False
    assert contract["may_execute_mutation"] is False
