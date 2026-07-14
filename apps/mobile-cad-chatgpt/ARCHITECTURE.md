# Architecture

HS-CAD Mobile is an **interactive-decoupled** ChatGPT App. The model chooses a
small set of architectural tools; a stateless Worker computes deterministic
drawing data; a touch-first widget owns interactive inspection and artifact
downloads.

```text
ChatGPT mobile / desktop host             Mobile browser / installed PWA
              |                                      |
              +--------- HTTPS Streamable MCP -------+
                                   |
                     Cloudflare Worker (/mcp)
                     fresh McpServer per request
                                   |
                strict BuildingSpec 1.0 validation
                                   |
                   deterministic CAD model
                   /             |          \
            7 drawing views   DXF R12    SVG renderers
                   \             |          /
                    concise summaries + widget artifacts
                                   |
               MCP Apps widget (ui://.../editor-v3.html)
```

## Runtime boundaries

`src/index.ts` is the Cloudflare entry point. It handles `/health`, bounds and
routes `/mcp`, and delegates every other path to Workers Assets. MCP uses
Streamable HTTP through Cloudflare Agents' stateless handler. A server instance
is never reused across requests and there is no legacy HTTP+SSE transport,
Durable Object, database, object store, queue, or user account.

`src/cad-model.ts` normalizes only documented defaults, validates semantic
relationships and references, and produces stable geometric entities. It does
not perform I/O or execute code. `src/dxf.ts` and `src/svg.ts` serialize those
entities into newly generated artifacts.

`src/app.tsx` is a React 19 mobile editor bundled by Vite into one MCP Apps HTML
resource. A small bridge module implements the standard MCP Apps JSON-RPC
messages. Supported `window.openai` APIs are additive host enhancements, never
the only path for receiving input or results.

## Tool contracts

| Tool | Visibility | Purpose | Widget |
| --- | --- | --- | --- |
| `open_mobile_cad` | model | Open the default touch editor | mounts v3 resource |
| `render_architectural_set` | model | Generate and display a supplied spec | mounts v3 resource |
| `generate_architectural_set` | app | Recalculate an edited widget spec | keeps mounted widget |
| `validate_architectural_set` | model/app | Validate geometry and derived metrics | no new widget |

All descriptions begin with a model-selection cue, all annotations declare the
operations read-only, non-destructive, closed-world, and idempotent, and all
inputs are strict Zod 4 objects. Output schemas describe only model-visible
`structuredContent`.

The result channels have deliberately different sizes:

- `content`: a short Korean user-facing outcome and warning count.
- `structuredContent`: project identity, metrics, validation summaries, view and
  layer lists, schedules, and artifact names/sizes.
- `_meta`: complete drawing data and full DXF/SVG strings for the widget only.

This prevents large CAD documents from consuming model context while leaving
downloads immediately available in the UI.

## BuildingSpec 1.0

Units are fixed to millimetres. The versioned contract covers project and scale
metadata; building, slab, foundation, ceiling, attic, eave, ridge, roof, and
finish parameters; a closed exterior polygon; stable wall IDs; rooms, grids,
and section cuts; wall-attached doors/windows/attic openings/vents; stairs and
attic access; and optional fixtures, furniture, cabinets, columns, and labels.

Limits on coordinates, text lengths, vertices, walls, openings, grids, and
symbols are applied before geometry generation. Explicit empty arrays remain
empty; defaults are supplied only for omitted fields. Unsupported versions and
orphan wall references are errors rather than silent guesses.

## Drawing and artifact model

The CAD engine emits one floor plan, four projected elevations, cross section
A-A, and longitudinal section B-B. Entity order and layer order are stable. The
same entity graph feeds both renderers, so schedules, metrics, SVG, and DXF refer
to the same normalized spec.

DXF targets ASCII R12 with primitive entities and millimetre unit convention.
SVG uses escaped text/attributes, bounded `viewBox` values, and sanitized layer
classes. The UI never interpolates user HTML; generated SVG is accepted only
from the trusted local serializer after spec validation.

## State and host integration

The authoritative draft lives in the widget. It can be imported/exported as
BuildingSpec JSON and synchronized with the host's widget state when supported.
The bridge receives tool input/result notifications, can call the app-visible
generation tool, updates model context with concise state, and sends a revision
request. Display mode and intrinsic height are requested only after feature
detection.

No project is stored server-side. Refreshing an ordinary PWA session resets to
the default unless the user imports a saved JSON file; a ChatGPT host may restore
its own widget state.

## Release and rollback coupling

The Worker tool schema, `_meta` artifact envelope, bridge, and v3 resource URI
form one release unit. Deploy them together and verify initialize, list,
resource read, all four tool calls, downloads, and mobile rendering. Roll back
the whole Worker deployment rather than mixing server and widget versions.
