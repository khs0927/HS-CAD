# Mobile ChatGPT acceptance prompts

Select **Developer mode → HS-CAD** for the conversation before running these.
If another drawing or browsing tool is available, explicitly tell ChatGPT to use
only HS-CAD so tool selection is unambiguous.

## Open

```text
HS-CAD 앱의 open_mobile_cad 도구만 사용해서 모바일 편집기를 열어줘.
```

Expected: the v3 widget mounts, shows the Korean touch UI and seven view choices,
and has no validation error for the default BuildingSpec 1.0.

## Reference generation

```text
HS-CAD 앱으로 가로 12,000mm, 세로 11,300mm, 벽 두께 200mm,
천장 2,500mm, 처마 3,200mm, 용마루 5,000mm, 다락 바닥 2,600mm인
박공지붕 건물을 만들어줘. 평면도 1면, 입면도 4면, 횡단면 A-A와
종단면 B-B를 위젯에 표시해줘.
```

Expected: `render_architectural_set` runs, the view list is exactly seven, and
the metrics/schedules/warnings are concise in the tool transcript while DXF/SVG
downloads stay in the widget.

## Validation

```text
HS-CAD 앱의 validate_architectural_set으로 외곽선 폐합과 자기교차,
벽 ID/개구 참조, 높이 관계, 지붕 경사, 다락 유효폭, DXF/SVG 무결성을
검사하고 오류와 경고를 구분해줘.
```

Expected: a structured validity summary and derived metrics, with no full SVG or
DXF string in the visible conversation.

## Revision

```text
처마 높이를 3.4m로 변경하고 다른 치수는 유지한 채 다락 유효폭과
지붕 경사를 다시 계산해줘. 열린 HS-CAD 위젯도 갱신해줘.
```

Expected: only `eaveHeight` changes to 3400, the mounted widget receives the new
result, and updated metrics render without remounting a second editor.

## Deliberate invalid input

```text
용마루 높이를 3,000mm, 처마 높이를 3,400mm로 설정해서 생성해줘.
불가능하면 자동 보정하지 말고 정확한 필드 오류를 알려줘.
```

Expected: generation is rejected with a user-readable semantic error; no NaN,
Infinity, partial DXF, or silent height swap is produced.

## Download and touch checks

In embedded and full-screen modes, test 375 × 812, 390 × 844, 430 × 932, and a
tablet width. Pan and zoom a view, fit/reset it, hide a layer, download one SVG,
the combined SVG sheet, and DXF, export/copy JSON, then send the revision prompt
from the widget. Confirm visible loading/error feedback and no page-level
horizontal overflow.
