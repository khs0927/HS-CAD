from src.cad_core.entity_model import entity_from_raw, LineEntity

def test_line_entity():
    e = entity_from_raw({'object_name':'AcDbLine','handle':'A','layer':'A-WALL','start':[0,0,0],'end':[1,0,0]})
    assert isinstance(e, LineEntity)
