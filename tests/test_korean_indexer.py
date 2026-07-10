# -*- coding: utf-8 -*-
from __future__ import annotations

from src.semantics.korean_indexer import disassemble_choseung, KoreanMaterialIndexer

def test_disassemble_choseung():
    # Test choseung extraction from Korean Syllables
    assert disassemble_choseung("그라스울") == "ㄱㄹㅅㅇ"
    assert disassemble_choseung("그라스울 판넬") == "ㄱㄹㅅㅇ ㅍㄴ"
    assert disassemble_choseung("T125 EPS 패널") == "T125 EPS ㅍㄴ"
    assert disassemble_choseung("H형강") == "Hㅎㄱ"
    assert disassemble_choseung("123") == "123"


def test_material_indexer_choseung_search(tmp_path):
    # Setup temporary materials file
    temp_file = tmp_path / "test_materials.txt"
    temp_file.write_text(
        "Layer: TXT | Text: THK125 EPS(불연) 1000판넬\n"
        "Layer: TXT | Text: T100 그라스울 패널\n"
        "Layer: TXT | Text: T125 그라스울 판넬\n"
        "Layer: TXT | Text: THK300 철근콘크리트옹벽\n"
        "Layer: TXT | Text: H-400X200X8X13 형강 기둥\n",
        encoding="utf-8"
    )

    indexer = KoreanMaterialIndexer(temp_file)
    
    # 1. Verify parsing and cleaning
    assert len(indexer.materials) == 5
    assert "T100 그라스울 패널" in indexer.materials
    assert "THK300 철근콘크리트옹벽" in indexer.materials

    # 2. Test Choseung (Initial Consonants Only) Search
    # "ㄱㄹㅅㅇ" (그라스울) should match T100 and T125 glasswool
    results = indexer.search("ㄱㄹㅅㅇ")
    assert len(results) == 2
    assert "T100 그라스울 패널" in results
    assert "T125 그라스울 판넬" in results

    # "ㅍㄴ" (패널/판넬) should match EPS, T100, T125
    results_panel = indexer.search("ㅍㄴ")
    assert len(results_panel) == 3
    assert "THK125 EPS(불연) 1000판넬" in results_panel

    # 3. Test Substring Search
    results_sub = indexer.search("그라스울")
    assert len(results_sub) == 2

    results_conc = indexer.search("콘크리트")
    assert len(results_conc) == 1
    assert "THK300 철근콘크리트옹벽" in results_conc

    # 4. Empty search returns all
    assert len(indexer.search("")) == 5
