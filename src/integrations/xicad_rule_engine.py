# -*- coding: utf-8 -*-
"""
XiCAD Knowledge Extraction & Rule Parser Framework (v2)

이 프레임워크는 C:\\xicad 디렉토리 내의 다양한 설정 및 자산 파일들
(xiDrawWall.txt, xiBlkLayerSet.txt, xiConfig.cfg, xiShortkey.key, zwcad.pgp, xiBE_*.dat, Lib/*.dwg)을
고속 파싱하고 정밀 분석하여, AI 모델이 도면을 설계할 때 사용할 수 있는 
강력한 제도 규칙 사전(Drafting Rule Dictionary) 및 명령어 매핑 데이터베이스를 제공합니다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

class XiCADRuleEngine:
    def __init__(self, xicad_root: str = "C:\\xicad"):
        self.xicad_root = Path(xicad_root)
        self.xilib_path = self.xicad_root / "xiLib"
        self.lisp_path = self.xicad_root / "Lisp"
        self.lib_path = self.xicad_root / "Lib"
        self.zwcad_path = self.xicad_root / "_ZWCad"
        
        # 파싱된 결과를 저장할 멤버 변수
        self.wall_styles: Dict[str, Any] = {}
        self.block_layer_rules: Dict[str, Any] = {}
        self.configs: Dict[str, Any] = {}
        self.shortkeys: Dict[str, Any] = {}
        self.pgp_aliases: Dict[str, Any] = {}
        self.structural_steel_specs: Dict[str, Any] = {}
        self.block_catalog: Dict[str, Any] = {}
        
        # 엔진 상태
        self.is_loaded = False

    def load_all_rules(self) -> bool:
        """
        XiCAD의 모든 다차원 룰셋 자원을 로드 및 파싱합니다.
        """
        if not self.xicad_root.exists():
            return False

        self.wall_styles = self.parse_wall_styles()
        self.block_layer_rules = self.parse_block_rules()
        self.configs = self.parse_config_variables()
        self.shortkeys = self.parse_shortkeys()
        self.pgp_aliases = self.parse_pgp_aliases()
        self.structural_steel_specs = self.parse_dat_files()
        self.block_catalog = self.parse_block_catalog()
        
        self.is_loaded = True
        return True

    def _read_file_safe(self, file_path: Path) -> Optional[List[str]]:
        """한글 및 특수기호가 포함된 설정 파일을 안전하게 디코딩하여 라인 단위로 읽어옵니다."""
        if not file_path.exists():
            return None
        encodings = ["cp949", "utf-8", "euc-kr", "latin1"]
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    return f.readlines()
            except Exception:
                continue
        return None

    def parse_wall_styles(self) -> Dict[str, Any]:
        """xiDrawWall.txt 파일을 파싱하여, 각 벽체 다중선 그룹의 오프셋 구조를 분석합니다."""
        file_path = self.xilib_path / "xiDrawWall.txt"
        content = self._read_file_safe(file_path)
        if not content:
            return {}

        styles = {}
        current_group = None
        current_lines = []

        for line in content:
            line_str = line.strip()
            if not line_str:
                continue

            # 그룹 구분선 감지 (예: *****Group01: 외단열벽+석)
            if line_str.startswith("*****"):
                if current_group:
                    styles[current_group] = self._structure_wall_lines(current_lines)
                
                parts = line_str.split(":", 1)
                group_name = parts[0].replace("*****", "").strip()
                desc = parts[1].strip() if len(parts) > 1 else ""
                current_group = f"{group_name} ({desc})" if desc else group_name
                current_lines = []
            else:
                if current_group:
                    # '280;S;6;Continuous' 구조 파싱 [오프셋;레이어명;색상번호;선종류]
                    parts = line_str.split(";")
                    if len(parts) >= 2:
                        try:
                            offset = float(parts[0])
                            layer = parts[1].strip()
                            color = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 7
                            linetype = parts[3].strip() if len(parts) > 3 else "Continuous"
                            current_lines.append({
                                "offset": offset,
                                "layer": layer,
                                "color": color,
                                "linetype": linetype
                            })
                        except ValueError:
                            continue

        # 마지막 그룹 추가
        if current_group and current_lines:
            styles[current_group] = self._structure_wall_lines(current_lines)

        return styles

    def _structure_wall_lines(self, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        """벽체 라인들의 상세 기하 구조(총 벽 두께, 내부 단열재/마감재 유무 등)를 역추적합니다."""
        if not lines:
            return {"lines": []}
            
        offsets = [l["offset"] for l in lines]
        max_offset = max(offsets)
        min_offset = min(offsets)
        total_thickness = max_offset - min_offset
        
        # 중심 구조선 레이어(일반적으로 'C' 또는 색상 2번)의 두께 추출
        core_lines = [l for l in lines if l["layer"] in ["C", "COL", "0"] or l["color"] == 2]
        core_thickness = 0.0
        if len(core_lines) >= 2:
            core_offsets = [l["offset"] for l in core_lines]
            core_thickness = max(core_offsets) - min(core_offsets)

        return {
            "total_thickness": total_thickness,
            "core_structure_thickness": core_thickness if core_thickness > 0 else total_thickness,
            "boundary": {"outer_limit": max_offset, "inner_limit": min_offset},
            "lines": lines
        }

    def parse_block_rules(self) -> Dict[str, Any]:
        """xiBlkLayerSet.txt 파일을 파싱하여 객체 타입별 기본 레이어, 선종류, 색상 매핑을 분석합니다."""
        file_path = self.xilib_path / "xiBlkLayerSet.txt"
        content = self._read_file_safe(file_path)
        if not content:
            return {}

        rules = {}
        for line in content:
            line_str = line.strip()
            if not line_str or line_str.startswith(";") or line_str.startswith("분류"):
                continue

            # 'symbol-furniture   ;FURN           ;HIDDEN       ;9      ;가구..' 형태 파싱
            parts = [p.strip() for p in line_str.split(";")]
            if len(parts) >= 4:
                category = parts[0]
                layer = parts[1]
                linetype = parts[2]
                color_code = parts[3]
                desc = parts[4] if len(parts) > 4 else ""
                
                rules[category] = {
                    "layer": layer,
                    "linetype": linetype,
                    "color": int(color_code) if color_code.isdigit() else 7,
                    "description": desc
                }
        return rules

    def parse_config_variables(self) -> Dict[str, Any]:
        """xiConfig.cfg 파일을 해석하여 XiCAD 명령어별 디폴트 기하 구조 및 표현 속성을 파싱합니다."""
        file_path = self.xilib_path / "xiConfig.cfg"
        content = self._read_file_safe(file_path)
        if not content:
            return {}

        configs = {}
        current_key = None
        for line in content:
            line_str = line.strip()
            if not line_str:
                continue

            # '/xiDoor1' 같은 헤더 감지
            if line_str.startswith("/"):
                current_key = line_str.replace("/", "")
            elif current_key:
                # '0|CmdFirst_rdo|0|Middle_rdo|1800|900...' 같은 직렬화 데이터 파싱
                raw_values = line_str.split("|")
                configs[current_key] = self._decode_config_values(current_key, raw_values)
                current_key = None
                
        return configs

    def _decode_config_values(self, key: str, values: List[str]) -> Dict[str, Any]:
        """각 명령어별 직렬화된 파라미터 리스트를 이해하기 쉬운 의미론적 딕셔너리로 해독합니다."""
        decoded = {"raw_list": values}
        
        # 1. 외여닫이문 (xiDoor1) 해독
        if key == "xiDoor1" and len(values) >= 15:
            try:
                decoded.update({
                    "default_width": float(values[5]) if values[5].replace(".", "", 1).isdigit() else 900.0,
                    "frame_thickness": float(values[6]) if values[6].replace(".", "", 1).isdigit() else 50.0,
                    "wall_alignment": values[7],
                    "opening_angle": float(values[12]) if values[12].replace(".", "", 1).isdigit() else 90.0,
                    "door_type": values[14],
                })
            except Exception:
                pass
                
        # 2. 양여닫이/슬라이딩문 (xiDoor3) 해독
        elif key == "xiDoor3" and len(values) >= 25:
            try:
                decoded.update({
                    "default_width": float(values[4]) if values[4].replace(".", "", 1).isdigit() else 1500.0,
                    "frame_thickness": float(values[8]) if values[8].replace(".", "", 1).isdigit() else 50.0,
                    "wall_depth_type": values[6],
                    "opening_angle": float(values[21]) if values[21].replace(".", "", 1).isdigit() else 90.0,
                    "door_style": values[26]
                })
            except Exception:
                pass

        # 3. 단열재 그리기 (xiInsul) 해독
        elif key == "xiInsul" and len(values) >= 4:
            try:
                decoded.update({
                    "default_thickness": float(values[1]) if values[1].replace(".", "", 1).isdigit() else 100.0,
                    "pattern_code": values[2],
                    "color_index": int(values[3]) if values[3].isdigit() else 251,
                })
            except Exception:
                pass

        # 4. 계단 그리기 (xiSTP) 해독
        elif key == "xiSTP" and len(values) >= 21:
            try:
                decoded.update({
                    "step_height_target": float(values[11]) if values[11].replace(".", "", 1).isdigit() else 150.0,
                    "tread_depth": float(values[12]) if values[12].replace(".", "", 1).isdigit() else 280.0,
                    "stair_width": float(values[13]) if values[13].replace(".", "", 1).isdigit() else 1200.0,
                    "riser_count": int(values[15]) if values[15].isdigit() else 18,
                    "stair_layer": values[16],
                    "handrail_layer": values[18]
                })
            except Exception:
                pass
                
        # 5. 보 그리기 (xiBeam) 해독
        elif key == "xiBeam" and len(values) >= 3:
            try:
                decoded.update({
                    "beam_type": values[1],
                    "color_index": int(values[2]) if values[2].isdigit() else 7
                })
            except Exception:
                pass

        return decoded

    def parse_shortkeys(self) -> Dict[str, Dict[str, str]]:
        """xiShortkey.key 단축키 파일을 파싱하여 명령어 단축키 정보를 추출합니다."""
        file_path = self.xilib_path / "xiShortkey.key"
        if not file_path.exists():
            file_path = self.lisp_path / "xiShortkey_origin.key"
            
        content = self._read_file_safe(file_path)
        if not content:
            return {}

        shortkeys = {}
        current_section = "Common"
        
        for line in content:
            line_str = line.strip()
            if not line_str:
                continue
            
            # 섹션 변경 감지 (예: *SecDraw, *SecComm)
            if line_str.startswith("*"):
                current_section = line_str.replace("*Sec", "").strip()
                continue
                
            # 'CT        ;xiCopyconTents           ;내용 복사(문자,블럭,두께,색)' 형식 파싱
            parts = [p.strip() for p in line_str.split(";")]
            if len(parts) >= 2:
                alias = parts[0].split()[0] if parts[0].split() else parts[0]
                lisp_func = parts[1]
                description = parts[2] if len(parts) > 2 else ""
                
                shortkeys[alias] = {
                    "lisp_function": lisp_func,
                    "section": current_section,
                    "description": description
                }
        return shortkeys

    def parse_pgp_aliases(self) -> Dict[str, str]:
        """zwcad.pgp 단축키 별칭 테이블을 파싱합니다."""
        file_path = self.zwcad_path / "zwcad.pgp"
        content = self._read_file_safe(file_path)
        if not content:
            return {}

        aliases = {}
        for line in content:
            line_str = line.strip()
            if not line_str or line_str.startswith(";"):
                continue
            
            # 'A,          *ARC' 또는 '3P,         *3DPOLY' 형식 파싱
            if "," in line_str and "*" in line_str:
                parts = line_str.split(",")
                alias = parts[0].strip().upper()
                cmd_part = parts[1].strip()
                if cmd_part.startswith("*"):
                    cmd = cmd_part.replace("*", "").strip().upper()
                    aliases[alias] = cmd
        return aliases

    def parse_dat_files(self) -> Dict[str, Any]:
        """H형강, 각관, 앵글 등의 구조 부재 치수 규격표를 해독합니다."""
        dat_files = {
            "h_beam": "xiBE_hbe.dat",
            "square_pipe": "xiBE_sqp.dat",
            "angle": "xiBE_ang.dat",
            "c_beam": "xiBE_cbe.dat",
            "channel": "xiBE_cch.dat",
            "circular_pipe": "xiBE_cip.dat"
        }
        
        specs = {}
        for key, filename in dat_files.items():
            file_path = self.lisp_path / filename
            content = self._read_file_safe(file_path)
            if not content:
                continue
                
            specs[key] = self._decode_steel_spec(key, content)
            
        return specs

    def _decode_steel_spec(self, steel_type: str, lines: List[str]) -> List[Dict[str, Any]]:
        """각 강재 데이터 파일의 치수 규격 테이블을 의미론적으로 파싱합니다."""
        items = []
        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("-") or "Angle" in line_str or "H-Beam" in line_str:
                continue
            
            parts = [p.strip() for p in line_str.split(";")]
            
            try:
                # 1. H형강 (높이;폭;웹두께;플랜지두께;R값)
                if steel_type == "h_beam" and len(parts) >= 5:
                    items.append({
                        "name": f"H-{parts[0]}x{parts[1]}x{parts[2]}x{parts[3]}",
                        "height": float(parts[0]),
                        "width": float(parts[1]),
                        "web_thickness": float(parts[2]),
                        "flange_thickness": float(parts[3]),
                        "radius": float(parts[4])
                    })
                # 2. 각관 (가로;세로;두께;R값)
                elif steel_type == "square_pipe" and len(parts) >= 4:
                    items.append({
                        "name": f"□-{parts[0]}x{parts[1]}x{parts[2]}",
                        "width": float(parts[0]),
                        "height": float(parts[1]),
                        "thickness": float(parts[2]),
                        "radius": float(parts[3])
                    })
                # 3. 앵글 (가로;세로;두께1;두께2;R값1;R값2)
                elif steel_type == "angle" and len(parts) >= 4:
                    items.append({
                        "name": f"L-{parts[0]}x{parts[1]}x{parts[2]}",
                        "width": float(parts[0]),
                        "height": float(parts[1]),
                        "thickness1": float(parts[2]),
                        "thickness2": float(parts[3]) if len(parts) > 3 and parts[3].replace(".","",1).isdigit() else float(parts[2])
                    })
            except ValueError:
                continue
        return items

    def parse_block_catalog(self) -> Dict[str, Any]:
        """Lib 폴더 내 1,450여개 실무 건축 블록 DWG들을 분류하고 카탈로그화합니다."""
        if not self.lib_path.exists():
            return {}

        catalog: Dict[str, List[str]] = {}
        total_blocks = 0
        
        for entry in self.lib_path.iterdir():
            if entry.is_file() and entry.suffix.lower() == ".dwg":
                total_blocks += 1
                name = entry.stem.upper()
                
                # 접두사를 기반으로 지능적 카테고리화
                if name.startswith("1P-") or name.startswith("2P-"):
                    # 평면도 블록 (e.g. 1P-BA101.dwg -> Plan_Bathroom)
                    sub = name.split("-")[1][:2] if "-" in name else "OTHER"
                    cat = f"Plan_{sub}"
                elif name.startswith("1E-") or name.startswith("2E-"):
                    # 입면도 블록 (e.g. 2E-Dr101.dwg -> Elevation_Door)
                    sub = name.split("-")[1][:2] if "-" in name else "OTHER"
                    cat = f"Elev_{sub}"
                elif name.startswith("2S-"):
                    cat = "Section"
                elif name.startswith("CAR"):
                    cat = "Vehicle"
                elif name.startswith("CHAIR") or name.startswith("SOFA") or name.startswith("BED") or name.startswith("TABLE") or name.startswith("CONF"):
                    cat = "Furniture"
                elif name.startswith("CTR") or name.startswith("CTRE"):
                    cat = "Landscape"
                elif name.startswith("ELEV") or name.startswith("LIFT"):
                    cat = "Elevator"
                elif name.startswith("XI"):
                    cat = "XiCAD_Custom"
                elif "PARK" in name:
                    cat = "Parking"
                elif any(x in name for x in ["TOILET", "BATH", "SINK", "LAUN", "FECES"]):
                    cat = "Sanitary"
                else:
                    cat = "Other"
                    
                if cat not in catalog:
                    catalog[cat] = []
                catalog[cat].append(entry.name)

        return {
            "total_blocks": total_blocks,
            "categories": {cat: len(files) for cat, files in catalog.items()},
            "catalog_detail": catalog
        }

    def generate_ai_drafting_prompt(self) -> str:
        """파싱된 모든 제도 규칙 및 치수 지식을 AI 학습용 마크다운 가이드로 빌드합니다."""
        if not self.is_loaded:
            self.load_all_rules()
            
        lines = [
            "### [SYSTEM DRAFTING CONSTRAINTS & XiCAD KNOWLEDGE BASE]",
            "AI가 CAD 도면을 설계, 분석 또는 수정하거나 도면 요소를 생성할 때 아래의 실무 표준과 치수 사양을 절대적인 제약조건으로 준수하십시오.",
            ""
        ]
        
        # 1. 벽체 작도 레이아웃 가이드
        lines.append("#### 1. 벽체 상세 작도 표준 (Wall Multi-line Specifications)")
        if self.wall_styles:
            for name, data in self.wall_styles.items():
                if "total_thickness" in data:
                    lines.append(f"- **{name}** (총 두께: {data['total_thickness']}mm | 구조체: {data['core_structure_thickness']}mm):")
                else:
                    lines.append(f"- **{name}** (지정된 라인 없음):")
                for l in data.get("lines", []):
                    lines.append(f"  * Offset: {l['offset']:+6.1f}mm | Layer: {l['layer']:<10} | Color: {l['color']:<2} | Linetype: {l['linetype']}")
        else:
            lines.append("- (벽체 규칙 정보 없음)")
            
        lines.append("")
        
        # 2. 블록 레이어 결합 표준
        lines.append("#### 2. 카테고리별 표준 도면층 매핑 (Block & Symbol Layer Mapping)")
        if self.block_layer_rules:
            for cat, rule in self.block_layer_rules.items():
                lines.append(f"- **{cat:<18}** -> Layer: {rule['layer']:<12} | Color: {rule['color']:<2} | Linetype: {rule['linetype']:<10} ({rule['description']})")
        else:
            lines.append("- (도면층 매핑 정보 없음)")
            
        lines.append("")
        
        # 3. 형강 부재 규격표 요약
        lines.append("#### 3. 실무 규격 강재 치수 표준 (Standard Structural Steel Specs)")
        if self.structural_steel_specs:
            for key, spec_list in self.structural_steel_specs.items():
                lines.append(f"- **{key.upper()} 표준 규격 (상위 5개)**:")
                for spec in spec_list[:5]:
                    lines.append(f"  * {spec['name']}")
        else:
            lines.append("- (구조재 규격 정보 없음)")
            
        lines.append("")
        
        # 4. 실무 단축키 및 명령어 연동 정보
        lines.append("#### 4. 주요 LISP 명령어 및 기능 숏컷 매핑 (LISP Cmd & Shortcut Mapping)")
        if self.shortkeys:
            draw_keys = [k for k, v in self.shortkeys.items() if v["section"] == "Draw"]
            lines.append("- **주요 작도(Draw) 단축키**:")
            for k in draw_keys[:10]:
                item = self.shortkeys[k]
                lines.append(f"  * {k:<6} -> {item['lisp_function']:<15} | {item['description']}")
        else:
            lines.append("- (LISP 단축키 매핑 정보 없음)")
            
        lines.append("")
        
        # 5. 블록 카탈로그 통계 요약
        if self.block_catalog:
            lines.append("#### 5. 실무 라이브러리 블록 구성 정보 (DWG Block Library Catalog)")
            lines.append(f"- 총 라이브러리 블록 수: {self.block_catalog.get('total_blocks')}개")
            for cat, count in self.block_catalog.get("categories", {}).items():
                lines.append(f"  * {cat:<18} : {count}개 블록 보유")

        return "\n".join(lines)

    def export_rules_to_json(self, out_path: str) -> None:
        """파싱된 모든 고차원 룰셋 지식 데이터를 JSON 형식으로 영구 내보내기합니다."""
        out_dir = Path(out_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        
        data = {
            "wall_styles": self.wall_styles,
            "block_layer_rules": self.block_layer_rules,
            "config_variables": self.configs,
            "shortkeys": self.shortkeys,
            "pgp_aliases": self.pgp_aliases,
            "structural_steel_specs": self.structural_steel_specs,
            "block_catalog": {
                "total_blocks": self.block_catalog.get("total_blocks", 0),
                "categories": self.block_catalog.get("categories", {}),
                "catalog_detail": self.block_catalog.get("catalog_detail", {})
            }
        }
        
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # 자가 진단 실행
    engine = XiCADRuleEngine("C:\\xicad")
    if engine.load_all_rules():
        print("XiCAD Multi-dimensional Rule Engine initialized successfully!")
        print(f"- Wall styles      : {len(engine.wall_styles)} groups")
        print(f"- Block rules      : {len(engine.block_layer_rules)} categories")
        print(f"- Shortkeys        : {len(engine.shortkeys)} aliases")
        print(f"- PGP Aliases      : {len(engine.pgp_aliases)} mappings")
        print(f"- Steel Specs      : {len(engine.structural_steel_specs)} types")
        print(f"- DWG Library      : {engine.block_catalog.get('total_blocks')} blocks")
        
        # 프롬프트 출력 확인
        print("\n=== GENERATED AI PROMPT PREVIEW ===")
        print("\n".join(engine.generate_ai_drafting_prompt().split("\n")[:30]))
    else:
        print("Failed to initialize Rule Engine.")
