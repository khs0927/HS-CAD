# Detail Drafting Standards

These rules capture the detail-drawing corrections validated in ZWCAD.

## Dimensions

- Generated dimensions must use real dimension entities.
- Do not set `TextOverride` for generated dimensions.
- Dimension text must come from the measured geometry, so a 230 mm span displays as 230, not an invented 200 label.
- Use the shared dimension style resolver and the project default dimension scale.

## Leaders

- Generated leaders must use QLEADER-style CAD leader entities.
- Do not draw loose lines as fake leaders.
- Use an L route: target point, vertical leg, then a horizontal landing next to the text.
- The final segment must be horizontal so the leader visually connects to the label.

## Insulation Batting

- Treat insulation as an area with length and thickness.
- The batting pattern belongs on the insulation thickness centerline.
- Pattern amplitude must be derived from the insulation thickness and kept inside the area.
- Avoid raw `BATTING` linetype when the pattern must fit the exact insulation thickness.
- Generate pattern geometry instead of guessing linetype scale.

## Annotation Placement

- Narrow parts such as 100T insulation and 100T wall should not receive direct labels when the label box cannot fit.
- Move those labels to leader annotations.
- Run annotation collision checks before saving generated drawings.
