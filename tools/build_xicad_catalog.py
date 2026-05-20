from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.integrations.xicad_command_catalog import parse_xicad_shortkey, command_table_rows, filter_architecture_commands
from src.integrations.xicad_paths import detect_xicad_profile
from src.integrations.xicad_manifest import write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description='Build XiCAD command catalog and path manifest.')
    parser.add_argument('--xicad-root', required=True, help='XiCAD root directory')
    parser.add_argument('--out-dir', default='generated/xicad', help='Output directory')
    parser.add_argument('--hashes', action='store_true', help='Include SHA-256 for every XiCAD file')
    args = parser.parse_args()

    root = Path(args.xicad_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    profile = detect_xicad_profile(root)
    (out_dir / 'xicad_path_profile.json').write_text(
        json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8'
    )

    if profile.shortkey_file:
        commands = parse_xicad_shortkey(profile.shortkey_file)
        (out_dir / 'xicad_commands_all.json').write_text(
            json.dumps(command_table_rows(commands), ensure_ascii=False, indent=2), encoding='utf-8'
        )
        arch = filter_architecture_commands(commands)
        (out_dir / 'xicad_commands_architecture.json').write_text(
            json.dumps(command_table_rows(arch), ensure_ascii=False, indent=2), encoding='utf-8'
        )

    write_manifest(root, out_dir / 'xicad_file_manifest.json', include_hashes=args.hashes)
    print(f'XiCAD catalog generated: {out_dir}')


if __name__ == '__main__':
    main()
