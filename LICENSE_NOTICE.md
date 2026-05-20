# License Notice

This package contains two different categories of files.

1. Project source code
   - Python source code, tests, examples, and documentation under `zwcad-ai-modifier/` were generated for this automation framework.
   - You may apply your own project license to this code before publishing it.

2. XiCAD vendor files
   - Files under `vendor/xicad/` are third-party XiCAD files provided by the user for integration testing and packaging.
   - These files may have their own copyright, license, and redistribution restrictions.
   - Before publishing this repository publicly, verify whether `vendor/xicad/` can be redistributed.
   - A safer public GitHub structure is to exclude `vendor/xicad/` and let users configure their local XiCAD installation path.

Recommended public distribution model:

- Commit `zwcad-ai-modifier/` source code.
- Do not commit `vendor/xicad/` unless redistribution is clearly permitted.
- Keep `config/xicad_profile.yaml` and CLI options for local XiCAD path detection.
