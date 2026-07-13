# Architecture

```text
ChatGPT mobile client / mobile browser
        |
        | MCP over HTTPS
        v
Cloudflare Worker: /mcp
        |
        +-- open_mobile_cad
        +-- generate_architectural_set
        +-- validate_architectural_set
        |
        v
Deterministic TypeScript CAD model
        |
        +-- SVG drawing views
        +-- ASCII DXF R12 exporter
        +-- validation report
```

The worker does not execute arbitrary code, mutate an existing DWG, or require a local CAD installation. Input is validated structured data, and output is generated from deterministic geometry functions.
