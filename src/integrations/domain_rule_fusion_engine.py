# -*- coding: utf-8 -*-
"""
Domain Rule Fusion Engine (Full Command Registry Version)

이 모듈은 XiCAD, ArchiOffice, HS-Steel 세 가지 도메인 룰 엔진에서 추출한
방대한 지식 베이스를 하나의 유기적인 컨텍스트로 통합(Fusion)합니다.

중요:
이 엔진은 AI 에이전트나 사용자가 단축키(Alias)에 의존하여 발생하는 충돌을 원천 차단하기 위해,
세 프로그램의 모든 기능을 "풀 명령어(Full Command)" 형태로 수집하여 레지스트리를 구축합니다.
AI는 반드시 이 풀 명령어를 사용해야 모든 기능을 충돌 없이 제어할 수 있습니다.
"""

from typing import Dict, Any, List
from pathlib import Path

from src.integrations.xicad_rule_engine import XiCADRuleEngine
from src.integrations.archioffice_rule_engine import ArchiOfficeRuleEngine
from src.integrations.hssteel_rule_engine import HSSteelRuleEngine

class DomainRuleFusionEngine:
    def __init__(self):
        self.xicad = XiCADRuleEngine("C:\\xicad")
        self.archioffice = ArchiOfficeRuleEngine("C:\\Program Files\\ArchiOfficeZW2024")
        self.hssteel = HSSteelRuleEngine("C:\\cad\\HSSTEEL")
        
        self.is_loaded = False
        
        # 통합 데이터셋: 단축키가 아닌 원본 커맨드를 키로 가짐
        self.full_commands: Dict[str, Dict[str, str]] = {} # command -> { "source": source, "description": desc }
        
        self.unified_blocks: Dict[str, str] = {} # block_name -> source
        self.block_conflicts: Dict[str, List[str]] = {} # block_name -> [sources]

    def load_all(self):
        print("Loading all three domain rule engines...")
        self.xicad.load_all_rules()
        self.archioffice.load_all_rules()
        self.hssteel.load_all()
        
        self._build_full_command_registry()
        self._analyze_block_conflicts()
        
        self.is_loaded = True

    def _build_full_command_registry(self):
        """단축키가 아닌 풀 명령어(Full Command) 전체 풀셋을 구축합니다."""
        # 1. XiCAD 풀 명령어
        for k, v in self.xicad.shortkeys.items():
            cmd = v.get("lisp_function", "").upper().strip()
            desc = v.get("description", "XiCAD Function")
            if cmd and cmd != "UNKNOWN":
                if not cmd.startswith("C:"):
                    cmd = f"C:{cmd}"
                self.full_commands[cmd] = {"source": "XiCAD", "description": desc}
                
        # 2. ArchiOffice 풀 명령어
        for k, v in self.archioffice.xpress_aliases.items():
            cmd = v.upper().strip()
            if cmd:
                if not cmd.startswith("C:"):
                    cmd = f"C:{cmd}"
                self.full_commands[cmd] = {"source": "ArchiOffice", "description": "XPress Tool"}
                
        for k, v in self.archioffice.onekeys.items():
            cmd = v.get("command", "").upper().strip()
            desc = v.get("description", "ArchiOffice Lisp")
            if cmd:
                if not cmd.startswith("C:"):
                    cmd = f"C:{cmd}"
                self.full_commands[cmd] = {"source": "ArchiOffice", "description": desc}
                
        # 3. HS-Steel 풀 명령어
        for k, v in self.hssteel.aliases.items():
            cmd = v.upper().strip()
            if cmd:
                if not cmd.startswith("C:"):
                    cmd = f"C:{cmd}"
                self.full_commands[cmd] = {"source": "HS-Steel", "description": "HS-Steel Macro"}

    def _analyze_block_conflicts(self):
        """라이브러리 블록 이름의 충돌을 분석합니다."""
        temp_blocks: Dict[str, List[str]] = {}
        
        # 1. XiCAD
        if "catalog_detail" in self.xicad.block_catalog:
            for cat, files in self.xicad.block_catalog["catalog_detail"].items():
                for f in files:
                    bname = f.lower().replace(".dwg", "")
                    temp_blocks.setdefault(bname, []).append("XiCAD")
                    
        # 2. ArchiOffice
        if "catalog_detail" in self.archioffice.block_catalog:
            for cat, files in self.archioffice.block_catalog["catalog_detail"].items():
                for f in files:
                    bname = f.lower().replace(".dwg", "")
                    temp_blocks.setdefault(bname, []).append("ArchiOffice")
                    
        # 3. HS-Steel
        for b in self.hssteel.blocks:
            bname = b.lower().replace(".dwg", "")
            temp_blocks.setdefault(bname, []).append("HS-Steel")
            
        for bname, sources in temp_blocks.items():
            sources = list(set(sources))
            if len(sources) > 1:
                self.block_conflicts[bname] = sources
            self.unified_blocks[bname] = sources[0]

    def generate_fused_ai_prompt(self, context_domain: str = "architecture") -> str:
        """AI 에이전트가 풀 명령어(Full Command) 기반으로 유기적 제어를 하도록 돕는 프롬프트를 생성합니다."""
        if not self.is_loaded:
            self.load_all()
            
        lines = [
            f"### [FUSED DOMAIN CONSTRAINTS - Context: {context_domain.upper()}]",
            "이 도면 환경은 XiCAD, ArchiOffice, HS-Steel 시스템이 융합된 복합 환경입니다.",
            "**CRITICAL RULE**: 당신은 작업을 진행할 때 단축키(Alias)를 절대 사용하지 마십시오. 단축키는 사용자별로 다르고 충돌할 수 있습니다.",
            "반드시 아래의 **풀 명령어(Full Command)**를 호출하여 각 프로그램이 가진 모든 유기적 기능 풀셋을 안전하게 다루십시오.",
            ""
        ]
        
        # 1. 풀 명령어 통합 결과 요약
        lines.append("#### 1. 도메인별 풀 명령어(Full Command) 카탈로그")
        lines.append(f"- 총 {len(self.full_commands)}개의 고유 풀 명령어가 융합되었습니다.")
        
        # 대표적인 풀 명령어 몇 개 보여주기 (각 소스별)
        lines.append("- 주요 샘플(소스별 3개씩 발췌):")
        counts = {"XiCAD": 0, "ArchiOffice": 0, "HS-Steel": 0}
        for cmd, info in self.full_commands.items():
            src = info["source"]
            if counts.get(src, 3) < 3:
                lines.append(f"  * `{cmd}` : {info['description']} (Source: {src})")
                counts[src] += 1
                
        # 2. 다이얼로그(DCL) 융합
        total_dcl = len(getattr(self.xicad, 'dialog_parameters', {})) + len(getattr(self.archioffice, 'dialog_parameters', {})) + len(getattr(self.hssteel, 'dialog_parameters', {}))
        lines.append("")
        lines.append("#### 2. 통합 다이얼로그(DCL) UI 제약 조건")
        lines.append(f"- 총 3개 시스템에서 {total_dcl}개의 대화상자 파라미터가 백그라운드에 등록되었습니다.")
        lines.append("- AI가 특정 명령어(예: 'A_ELEVTR' 또는 'DIM_EDIT')를 실행하기 전, 해당 다이얼로그의 파라미터(toggle, edit_box 등)를 채워서 API를 호출해야 합니다.")
        
        # 3. 블록 충돌 방지 가이드
        lines.append("")
        lines.append("#### 3. 통합 블록 카탈로그 가이드")
        lines.append(f"- 통합된 라이브러리 블록 종류: {len(self.unified_blocks)}개")
        if self.block_conflicts:
            lines.append(f"- 블록 이름 중복 발생 수: {len(self.block_conflicts)}개")
            lines.append("- (블록 삽입 시 경로(Path)를 절대 경로로 명시하거나 도메인 접두사를 사용하여 충돌을 방지하십시오.)")
            
        lines.append("")
        lines.append("---")
        lines.append("이 정보는 AI 에이전트가 각 툴의 유기적 시너지를 높이고 충돌 없이 ZWCAD/AutoCAD를 제어하기 위한 기반 지식입니다.")
        
        return "\n".join(lines)

if __name__ == "__main__":
    fusion = DomainRuleFusionEngine()
    fusion.load_all()
    
    print("\n[Fusion Engine Report]")
    print(f"- Total Full Commands Extracted : {len(fusion.full_commands)}")
    print(f"- Total Blocks Analyzed         : {len(fusion.unified_blocks)}")
    print(f"- Block Conflicts Detected      : {len(fusion.block_conflicts)}")

    print("\n=== FUSED AI PROMPT (Full Command Approach) ===")
    print(fusion.generate_fused_ai_prompt("architecture"))
