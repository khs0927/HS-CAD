from src.cad_core.entity_model import entity_from_raw, LineEntity, BlockEntity

def test_line_entity():
    e = entity_from_raw({'object_name':'AcDbLine','handle':'A','layer':'A-WALL','start':[0,0,0],'end':[1,0,0]})
    assert isinstance(e, LineEntity)

def test_block_entity_with_effective_name():
    e = entity_from_raw({
        'object_name': 'AcDbBlockReference',
        'handle': 'B',
        'layer': 'A-COLUMN',
        'Name': '*U123',
        'EffectiveName': 'C600',
        'InsertionPoint': [100.0, 200.0, 0.0],
        'Rotation': 0.5,
        'XScaleFactor': 1.0,
        'YScaleFactor': 1.0,
        'ZScaleFactor': 1.0
    })
    assert isinstance(e, BlockEntity)
    assert e.name == '*U123'
    assert e.effective_name == 'C600'
    assert e.insert == [100.0, 200.0, 0.0]
    assert e.rotation == 0.5

