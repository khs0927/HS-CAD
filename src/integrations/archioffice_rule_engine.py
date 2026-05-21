# -*- coding: utf-8 -*-
"""
ArchiOffice Knowledge Extraction & Rule Parser Framework

이 프레임워크는 C:\\Program Files\\ArchiOfficeZW2024 디렉토리 내의 핵심 실무 자산
(InerCAD/onekey.lsp, InerCAD/ShapeSteel.txt, XPress/XPRESS.PGP, InerCAD/ROOMNAME.TXT)을
정밀 파싱하고 데이터화하여, AI 모델이 아키오피스 표준에 맞추어 건축 도면을 설계할 수 있도록
독자적인 규칙 가이드를 제공합니다.

기존 XiCAD 룰셋과 데이터 충돌이 없도록 완전히 격리된 네임스페이스로 작동합니다.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

class ArchiOfficeRuleEngine:
    def __init__(self, ao_root: str = "C:\\Program Files\\ArchiOfficeZW2024"):
        self.ao_root = Path(ao_root)
        self.inercad_path = self.ao_root / "InerCAD"
        self.xpress_path = self.ao_root / "XPress"
        
        # 파싱된 결과를 저장할 멤버 변수
        self.onekeys: Dict[str, Any] = {}
        self.steel_specs: Dict[str, Any] = {}
        self.xpress_aliases: Dict[str, str] = {}
        self.standard_rooms: List[str] = []
        
        # 엔진 상태
        self.is_loaded = False

    def load_all_rules(self) -> bool:
        """
        아키오피스의 모든 룰셋 자원을 로드 및 파싱합니다.
        """
        if not self.ao_root.exists():
            return False

        self.onekeys = self.parse_onekey_lisp()
        self.steel_specs = self.parse_shape_steel()
        self.xpress_aliases = self.parse_xpress_pgp()
        self.standard_rooms = self.parse_room_names()
        
        self.is_loaded = True
        return True

    def _read_file_safe(self, file_path: Path) -> Optional[List[str]]:
        """한글이 들어간 아키오피스 설정 파일을 다양한 인코딩으로 안전하게 로드합니다."""
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

    def parse_onekey_lisp(self) -> Dict[str, Any]:
        """onekey.lsp를 파싱하여 아키오피스 고유의 1키(One-Key) 단축키 매핑 테이블을 추출합니다."""
        file_path = self.inercad_path / "onekey.lsp"
        content = self._read_file_safe(file_path)
        if not content:
            return {}

        onekeys = {}
        for line in content:
            line_str = line.strip()
            if not line_str:
                continue
            
            # 주석 라인 중 단축키 설명 파싱 (예: ";;;  C:PM     Position Mark")
            if line_str.startswith(";;;") and "C:" in line_str:
                parts = line_str.replace(";;;", "").strip().split("C:", 1)
                if len(parts) > 1:
                    tokens = parts[1].split(None, 1)
                    if len(tokens) >= 2:
                        alias = tokens[0].strip().upper()
                        desc = tokens[1].strip()
                        onekeys[alias] = {
                            "command": f"C:{alias}",
                            "description": desc,
                            "type": "OneKey Shortcut"
                        }
            # LISP 함수 정의 파싱 (예: "(defun C:T_KC ()")
            elif line_str.startswith("(defun C:"):
                # 함수 이름 추출
                func_part = line_str.split("C:")[1].split()[0].split("(")[0].strip()
                if func_part:
                    func_name = func_part.upper()
                    onekeys[func_name] = {
                        "command": f"C:{func_name}",
                        "description": "ArchiOffice LISP Function",
                        "type": "LISP Command"
                    }
                    
        return onekeys

    def parse_shape_steel(self) -> Dict[str, Any]:
        """ShapeSteel.txt를 해독하여 아키오피스가 사용하는 표준 철골/형강 치수를 추출합니다."""
        file_path = self.inercad_path / "ShapeSteel.txt"
        content = self._read_file_safe(file_path)
        if not content:
            return {}

        specs = {}
        current_category = None
        
        for line in content:
            line_str = line.strip()
            if not line_str:
                continue
                
            # 카테고리 헤더 감지 (예: *경량 H형강, *일반구조용 각형강관 등)
            if line_str.startswith("*"):
                current_category = line_str.replace("*", "").strip()
                specs[current_category] = []
            elif current_category:
                # 탭 또는 공백으로 분리된 치수 파싱
                parts = [p.strip() for p in line_str.split()]
                try:
                    if len(parts) >= 4:
                        if "H형강" in current_category or "H" in current_category:
                            # H: 높이, 폭, 웹두께, 플랜지두께
                            specs[current_category].append({
                                "name": f"H-{parts[0]}x{parts[1]}x{parts[2]}x{parts[3]}",
                                "height": float(parts[0]),
                                "width": float(parts[1]),
                                "web_thickness": float(parts[2]),
                                "flange_thickness": float(parts[3])
                            })
                        elif "각" in current_category or "PIPE" in current_category:
                            # 각관: 가로, 세로, 두께
                            specs[current_category].append({
                                "name": f"□-{parts[0]}x{parts[1]}x{parts[2]}",
                                "width": float(parts[0]),
                                "height": float(parts[1]),
                                "thickness": float(parts[2])
                            })
                except ValueError:
                    continue
                    
        return specs

    def parse_xpress_pgp(self) -> Dict[str, str]:
        """XPRESS.PGP 단축키 별칭 테이블을 파싱하여 XPress Tools 단축 정보를 구조화합니다."""
        file_path = self.xpress_path / "XPRESS.PGP"
        content = self._read_file_safe(file_path)
        if not content:
            return {}

        aliases = {}
        for line in content:
            line_str = line.strip()
            if not line_str or line_str.startswith(";"):
                continue
                
            # 'XEL,        *XELEV' 또는 'XBM,        *XBEAM' 형식 파싱
            if "," in line_str and "*" in line_str:
                parts = line_str.split(",")
                alias = parts[0].strip().upper()
                cmd_part = parts[1].strip()
                if cmd_part.startswith("*"):
                    cmd = cmd_part.replace("*", "").strip().upper()
                    aliases[alias] = cmd
        return aliases

    def parse_room_names(self) -> List[str]:
        """ROOMNAME.TXT 파일을 파싱하여 실무 표준 실명 목록을 수집합니다."""
        file_path = self.inercad_path / "ROOMNAME.TXT"
        if not file_path.exists():
            file_path = self.xpress_path / "ROOMNAME.TXT"
            
        content = self._read_file_safe(file_path)
        if not content:
            return []

        rooms = []
        for line in content:
            line_str = line.strip()
            if line_str and not line_str.startswith(";"):
                # 인코딩 깨진 빈 글자 등 예방 조치
                cleaned = line_str.replace(" ", "")
                if cleaned:
                    rooms.append(line_str)
        return rooms

    def generate_ao_drafting_prompt(self) -> str:
        """파싱된 아키오피스 도면 제약 조건을 AI 전용 마크다운 가이드 프롬프트로 작성합니다."""
        if not self.is_loaded:
            self.load_all_rules()

        lines = [
            "### [SYSTEM DRAFTING CONSTRAINTS - ArchiOffice KNOWLEDGE BASE]",
            "AI가 ArchiOffice(아키오피스/InerCAD) 도면 템플릿 환경을 다루거나 해당 요소들을 생성/검증할 때 아래의 표준 제약과 명칭을 독립적으로 준수하십시오. (기존 XiCAD 표준과 엄격히 격리)",
            ""
        ]

        # 1. 1키 및 LISP 단축키
        lines.append("#### 1. ArchiOffice 전용 단축키 및 LISP 기능 매핑 (ArchiOffice Shortkeys)")
        if self.onekeys:
            lines.append("- **주요 원키(One-Key) 작도 단축키**:")
            # 상위 15개 샘플 출력
            keys = sorted(self.onekeys.keys())
            count = 0
            for k in keys:
                item = self.onekeys[k]
                if item["type"] == "OneKey Shortcut" and count < 15:
                    lines.append(f"  * {k:<6} -> {item['command']:<10} | {item['description']}")
                    count += 1
        else:
            lines.append("- (단축키 정보 없음)")

        lines.append("")

        # 2. XPress 도구 단축키
        lines.append("#### 2. XPress Tools 캐드 명령어 별칭 (XPress Command Aliases)")
        if self.xpress_aliases:
            lines.append("- **XPress 도구 핵심 명령어 단축키 (상위 15개)**:")
            xkeys = sorted(self.xpress_aliases.keys())
            for xk in xkeys[:15]:
                lines.append(f"  * {xk:<8} -> {self.xpress_aliases[xk]}")
        else:
            lines.append("- (XPress 별칭 정보 없음)")

        lines.append("")

        # 3. 형강 부재 규격
        lines.append("#### 3. ArchiOffice 표준 구조 강재 치수 규격 (Standard Steel Specs)")
        if self.steel_specs:
            for cat, items in self.steel_specs.items():
                lines.append(f"- **{cat} 규격 (상위 5개)**:")
                for item in items[:5]:
                    lines.append(f"  * {item['name']}")
        else:
            lines.append("- (구조재 규격 정보 없음)")

        lines.append("")

        # 4. 실명 가이드
        lines.append("#### 4. 도면 작도용 실무 표준 실명 가이드 (Standard Room Labels)")
        if self.standard_rooms:
            lines.append(f"- **실무용 표준 공간 명칭**: {', '.join(self.standard_rooms)}")
        else:
            lines.append("- (실명 정보 없음)")

        return "\n".join(lines)

    def export_rules_to_json(self, out_path: str) -> None:
        """파싱된 아키오피스 룰 지식을 JSON 파일로 내보내기합니다."""
        out_dir = Path(out_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        
        data = {
            "onekey_shortcuts": self.onekeys,
            "steel_specs": self.steel_specs,
            "xpress_aliases": self.xpress_aliases,
            "standard_rooms": self.standard_rooms
        }
        
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    engine = ArchiOfficeRuleEngine()
    if engine.load_all_rules():
        print("ArchiOffice Rule Engine successfully initialized!")
        print(f"- OneKey Mappings: {len(engine.onekeys)} items")
        print(f"- Steel Specs    : {len(engine.steel_specs)} categories")
        print(f"- XPress Aliases : {len(engine.xpress_aliases)} items")
        print(f"- Standard Rooms : {len(engine.standard_rooms)} labels")
    else:
        print("Failed to initialize ArchiOffice Rule Engine.")
