NATURAL_LANGUAGE_TO_JSON_PROMPT = """
사용자 CAD 수정 요청을 아래 허용 명령 JSON 중 하나로만 변환하라.
허용 명령: move_layer, move_object_by_handle, replace_text, replace_block, create_boundary, create_grid, place_columns, scan_all.
Python 코드는 절대 출력하지 말라.
"""
