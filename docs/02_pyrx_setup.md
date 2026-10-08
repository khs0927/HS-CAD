# PyRx Setup

Install cad-pyrx/PyRx only after confirming compatible ZWCAD ZRX version.

## Adapter readiness reporting

`PyRxAdapter.connect()` only imports the dependency; it does not verify a CAD
host or implement native operations. The side-effect-free `health()` and
`capabilities()` reports therefore keep native read/write readiness and execution
permission false, even after a successful import. `close()` clears local dependency
state and does not close a CAD document. These reports are not workstation evidence.
