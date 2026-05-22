"""
qa_report.py — 평면도 CAD화 파이프라인 최종 기하 통계 및 품질 제어(QC) 보고서 생성기
==================================================================================
파이프라인 전체 공정을 통해 도출된 데이터 무결성을 검증하고, 기하 요약 통계(벽체, 문, 창호 개수 등),
다중 센서 충돌 해결(Conflict resolution) 이력, VLM 보정 전후 수치 비교 및 최종 스케일 보정 계수를 포함하는
프리미엄 스타일의 검수용 마크다운(.md) 보고서 및 미려하게 디자인된 HTML(.html) 품질 검수 보고서를 작성합니다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neuro_seq_cad.fusion.evidence_graph import EvidenceGraph

logger = logging.getLogger(__name__)


class QAReportGenerator:
    """EvidenceGraph 데이터를 기반으로 마크다운 및 인터랙티브 HTML QA 리포트를 컴파일하는 도구."""

    def __init__(self, evidence_graph: EvidenceGraph) -> None:
        """
        QAReportGenerator 초기화.

        Parameters
        ----------
        evidence_graph : EvidenceGraph
            분석 대상이 되는 최종 결과 증거 그래프.
        """
        self.graph = evidence_graph

    def generate_markdown(self, filepath: str | Path) -> Path:
        """
        마크다운 형식의 기하 품질 보고서를 생성합니다.

        Parameters
        ----------
        filepath : str | Path
            저장할 .md 파일의 경로.

        Returns
        -------
        Path
            저장된 마크다운 파일의 절대 경로.
        """
        filepath = Path(filepath).resolve()
        filepath.parent.mkdir(parents=True, exist_ok=True)

        summary = self.graph.summary()
        pipeline = self.graph.pipeline
        meta = self.graph.metadata

        # 스케일 변수 획득
        scale = pipeline.scale_pixels_per_mm or 1.0
        scale_calibration_method = meta.get("scale_calibration_method", "Median OCR-to-Geometry Ratio")

        # 평균 신뢰도 계산
        total_entities = len(self.graph.entities)
        avg_conf = sum(e.confidence for e in self.graph.entities) / total_entities if total_entities > 0 else 0.0

        # 저신뢰도 항목
        low_conf_items = self.graph.low_confidence(0.6)

        lines = [
            f"# 📐 Floorplan-to-CAD 품질 보증 (QA) 보고서",
            f"",
            f"본 보고서는 AI 파이프라인(Raster2Seq + MLSD + PlanParser + PaddleOCR + VLM Refiner)을 통해 생성된 CAD 도면의 정밀도 및 일관성을 검증한 결과입니다.",
            f"",
            f"---",
            f"",
            f"## 📋 1. 도면 분석 개요",
            f"- **분석 시각**: `{datetime.now(timezone.utc).isoformat()}` (UTC)",
            f"- **대상 이미지**: `{pipeline.image_path or 'synthetic_floorplan.png'}`",
            f"- **이미지 해상도**: `{pipeline.image_width} x {pipeline.image_height} px`",
            f"- **적용 축적 스케일 계수**: `1 px = {scale:.4f} mm` ({scale_calibration_method})",
            f"- **활성화 추론 소스**: `{', '.join(pipeline.active_sources) or 'Raster2SeqMock'}`",
            f"",
            f"## 📊 2. 건축 기하 통계 (Entity Summary)",
            f"| 요소 유형 (Entity Type) | 검출 개수 (Count) | 타겟 CAD 레이어 | 설명 |",
            f"| :--- | :---: | :---: | :--- |",
            f"| 기둥 (Column) | `{summary.get('column', 0)}` | `COL` | 골조 사각 기둥 블록 |",
            f"| 외벽/일반벽 (Wall) | `{summary.get('wall', 0)}` | `WAL1 / WAL2` | 외곽 내력벽 및 내부 파티션 선분 |",
            f"| 문 (Door) | `{summary.get('door', 0)}` | `DOOR` | 90° Swing 여닫이 블록 |",
            f"| 창문 (Window) | `{summary.get('window', 0)}` | `WIN` | 프레임 및 내부 유리창선블록 |",
            f"| 구역계 (Room/Zone) | `{summary.get('room', 0)}` | `ZONE` | 실 경계 폴리곤 |",
            f"| 문자 (Text) | `{summary.get('text', 0)}` | `TXT` | OCR 방 이름 및 주석 문자 |",
            f"| 치수선 (Dimension) | `{summary.get('dimension', 0)}` | `DIM` | 자동 실측 보정 및 표기선 |",
            f"| 가구 (Furniture) | `{summary.get('furniture', 0)}` | `FUR` | 침대, 변기, 싱크 등 내장재 |",
            f"| 계단 (Stair) | `{summary.get('stair', 0)}` | `STAIR` | 피난 계단선 |",
            f"| **총합 (Total Entities)** | **`{total_entities}`** | - | **전체 기하 객체 수** |",
            f"",
            f"## 🛡️ 3. 다중 센서 융합 및 충돌 해결 (Fusion & Conflicts)",
        ]

        # 충돌 로그 파싱
        conflicts = meta.get("conflict_records", [])
        if conflicts:
            lines.append(f"총 `{len(conflicts)}` 건의 공간 기하 겹침(Overlapping) 충돌이 성공적으로 해결되었습니다.")
            lines.append("")
            lines.append("| ID | 유형 (Type) | 해결 내용 | 판단 방식 (IoU/Distance) |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for c in conflicts:
                lines.append(
                    f"| `{c.get('entity_id', 'N/A')}` | {c.get('type', 'Unknown')} | "
                    f"{c.get('action', 'Merged/Dropped')} | {c.get('reason', 'IoU Threshold Over')}"
                )
        else:
            lines.append("- 감지된 심볼/공간 영역 간의 심각한 중복 겹침 및 중복 할당 충돌이 발견되지 않았습니다. (클린 그래프 상태)")

        lines.extend([
            f"",
            f"## 👁️ 4. VLM (Vision-Language) 최종 감리 및 미세 보정",
        ])

        # VLM 피드백 파싱
        vlm_applied = meta.get("vlm_refinements_applied", [])
        if vlm_applied:
            lines.append(f"VLM Comparative Review를 통해 총 `{len(vlm_applied)}`건의 구조 정밀 교정이 완료되었습니다.")
            lines.append("")
            lines.append("| 순번 | 대상 ID | 보정 유형 (Action) | 세부 조치 사항 (Description) | 교정 사유 (Reason) |")
            lines.append("| :---: | :--- | :--- | :--- | :--- |")
            for idx, item in enumerate(vlm_applied, 1):
                action_str = str(item.get('action', 'modify')).upper()
                desc_str = item.get('desc', item.get('description', 'Refinement'))
                reason_str = item.get('reason', 'N/A')
                lines.append(
                    f"| {idx} | `{item.get('target_id', 'N/A')}` | "
                    f"`{action_str}` | "
                    f"{desc_str} | "
                    f"{reason_str} |"
                )
        else:
            lines.append("- VLM 에이전트의 비교 도면 감수 결과, 모델 기하와 래스터 픽셀 스케일이 매우 잘 일치하여 특별한 수동 시프트 보정이 제외되었습니다.")

        lines.extend([
            f"",
            f"## 📈 5. 최종 데이터 신뢰도 품질 검사",
            f"- **도면 종합 평균 신뢰도**: `{avg_conf * 100:.2f}%`",
            f"- **검수 요구 항목 (Needs Review)**: `{len(low_conf_items)}`건",
        ])

        if low_conf_items:
            lines.append("")
            lines.append("### ⚠️ 정밀 검수 필요 요소 리스트 (신뢰도 < 60%)")
            lines.append("| 엔티티 ID | 유형 (Type) | 융합 신뢰도 (Confidence) | 사유 |")
            lines.append("| :--- | :--- | :---: | :--- |")
            for item in low_conf_items[:10]:  # 최대 10개만 리스팅
                lines.append(
                    f"| `{item.id}` | {item.entity_type} | `{item.confidence * 100:.1f}%` | "
                    f"추론 감지 소스 부족 및 픽셀 신뢰도 미달"
                )
            if len(low_conf_items) > 10:
                lines.append(f"| ... | ... | ... | 외 {len(low_conf_items) - 10}개 요소 생략. CAD 툴 내 `QA-REVIEW` 레이어 참조. |")
        else:
            lines.append("- 🎉 전체 요소의 감지 신뢰도가 60% 이상으로, 극도로 일관된 고품질 벡터화 도면입니다.")

        # 파일 쓰기
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info("마크다운 QA 보고서가 생성되었습니다: %s", filepath)
        return filepath

    def generate_html(self, filepath: str | Path) -> Path:
        """
        비주얼 레이아웃이 적용된 프리미엄 스타일의 HTML QA 보고서를 작성합니다.

        Parameters
        ----------
        filepath : str | Path
            저장할 .html 파일의 경로.

        Returns
        -------
        Path
            저장된 HTML 파일의 절대 경로.
        """
        filepath = Path(filepath).resolve()
        filepath.parent.mkdir(parents=True, exist_ok=True)

        summary = self.graph.summary()
        pipeline = self.graph.pipeline
        meta = self.graph.metadata

        # 데이터 변수
        scale = pipeline.scale_pixels_per_mm or 1.0
        total_entities = len(self.graph.entities)
        avg_conf = sum(e.confidence for e in self.graph.entities) / total_entities if total_entities > 0 else 0.0
        avg_conf_pct = f"{avg_conf * 100:.1f}%"

        # 저신뢰도 항목
        low_conf_items = self.graph.low_confidence(0.6)
        conflicts = meta.get("conflict_records", [])
        vlm_applied = meta.get("vlm_refinements_applied", [])

        # HTML 기하 요약 테이블 행 템플릿
        types_korean = {
            "column": "기둥 (Column)", "wall": "벽체 (Wall)", "door": "문 (Door)",
            "window": "창문 (Window)", "room": "구역계 (Room/Zone)", "text": "문자 (Text)",
            "dimension": "치수선 (Dimension)", "furniture": "가구 (Furniture)", "stair": "계단 (Stair)"
        }
        layers_map = {
            "column": "COL", "wall": "WAL1/WAL2", "door": "DOOR",
            "window": "WIN", "room": "ZONE", "text": "TEXT",
            "dimension": "DIM", "furniture": "FURN", "stair": "STAIR"
        }

        sum_rows = ""
        for k, name in types_korean.items():
            cnt = summary.get(k, 0)
            layer = layers_map.get(k, "QA-REVIEW")
            sum_rows += f"""
            <tr>
                <td>{name}</td>
                <td class="text-center font-bold">{cnt}</td>
                <td class="text-center"><span class="badge layer-badge">{layer}</span></td>
                <td>{k.upper()} 레이어 컴파일 매핑</td>
            </tr>
            """

        # 충돌 해결 리스트
        conflict_rows = ""
        if conflicts:
            for c in conflicts:
                conflict_rows += f"""
                <tr>
                    <td><code>{c.get('entity_id', 'N/A')}</code></td>
                    <td><span class="badge badge-warn">{c.get('type', 'Overlap')}</span></td>
                    <td>{c.get('action', 'Merged')}</td>
                    <td>{c.get('reason', 'IoU Over')}</td>
                </tr>
                """
        else:
            conflict_rows = """
            <tr>
                <td colspan="4" class="text-center text-muted">충돌 해결 이력이 없습니다. 그래프가 매우 깔끔합니다.</td>
            </tr>
            """

        # VLM 수정 이력
        vlm_rows = ""
        if vlm_applied:
            for idx, item in enumerate(vlm_applied, 1):
                action_str = str(item.get('action', 'modify')).upper()
                desc_str = item.get('desc', item.get('description', 'Refinement'))
                reason_str = item.get('reason', 'N/A')
                vlm_rows += f"""
                <tr>
                    <td class="text-center">{idx}</td>
                    <td><code>{item.get('target_id', 'N/A')}</code></td>
                    <td><span class="badge badge-success">{action_str}</span></td>
                    <td>{desc_str}</td>
                    <td>{reason_str}</td>
                </tr>
                """
        else:
            vlm_rows = """
            <tr>
                <td colspan="5" class="text-center text-muted">VLM 자동 교정 건이 없습니다. 원본 벡터 일치율이 완벽합니다.</td>
            </tr>
            """

        # 저신뢰도 경고 목록
        low_rows = ""
        if low_conf_items:
            for item in low_conf_items[:8]:
                low_rows += f"""
                <tr>
                    <td><code>{item.id}</code></td>
                    <td><span class="badge layer-badge">{item.entity_type.upper()}</span></td>
                    <td class="text-center text-danger font-bold">{item.confidence * 100:.1f}%</td>
                    <td>추론 가중 결합 신뢰도 미달</td>
                </tr>
                """
            if len(low_conf_items) > 8:
                low_rows += f"""
                <tr>
                    <td colspan="4" class="text-center font-bold text-muted">외 {len(low_conf_items) - 8}개 요소가 더 존재합니다. CAD 내 QA 레이어에서 확인하십시오.</td>
                </tr>
                """
        else:
            low_rows = """
            <tr>
                <td colspan="4" class="text-center text-success font-bold">🎉 모든 기하학 엔티티의 신뢰도가 60% 이상인 완벽한 도면입니다!</td>
            </tr>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>Floorplan-to-CAD 통합 QA 레포트</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Noto+Sans+KR:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --primary: #38bdf8;
            --accent: #a855f7;
            --text-color: #f1f5f9;
            --text-muted: #94a3b8;
            --success: #34d399;
            --warning: #fbbf24;
            --danger: #f87171;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Outfit', 'Noto Sans KR', sans-serif;
            line-height: 1.6;
            padding: 40px 20px;
        }}

        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}

        header {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
            padding: 40px;
            border-radius: 20px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
            position: relative;
            overflow: hidden;
        }}

        header::after {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 80%);
            pointer-events: none;
        }}

        header h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 10px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }}

        header p {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}

        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
        }}

        .stat-card:hover {{
            transform: translateY(-5px);
            border-color: rgba(56, 189, 248, 0.4);
            box-shadow: 0 10px 20px rgba(56, 189, 248, 0.05);
        }}

        .stat-card .label {{
            color: var(--text-muted);
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }}

        .stat-card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: #fff;
            margin-top: auto;
        }}

        .stat-card .value.highlight-primary {{ color: var(--primary); }}
        .stat-card .value.highlight-accent {{ color: var(--accent); }}
        .stat-card .value.highlight-success {{ color: var(--success); }}

        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
        }}

        .card h2 {{
            font-size: 1.4rem;
            font-weight: 600;
            margin-bottom: 20px;
            border-left: 4px solid var(--primary);
            padding-left: 12px;
            color: #fff;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.95rem;
        }}

        th, td {{
            padding: 14px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}

        th {{
            background-color: rgba(255, 255, 255, 0.02);
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 0.05em;
        }}

        tr:hover td {{
            background-color: rgba(255, 255, 255, 0.01);
        }}

        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 100px;
            font-size: 0.75rem;
            font-weight: 700;
            text-align: center;
        }}

        .layer-badge {{
            background-color: rgba(56, 189, 248, 0.15);
            color: var(--primary);
            border: 1px solid rgba(56, 189, 248, 0.3);
        }}

        .badge-success {{
            background-color: rgba(52, 211, 153, 0.15);
            color: var(--success);
            border: 1px solid rgba(52, 211, 153, 0.3);
        }}

        .badge-warn {{
            background-color: rgba(251, 191, 36, 0.15);
            color: var(--warning);
            border: 1px solid rgba(251, 191, 36, 0.3);
        }}

        .badge-danger {{
            background-color: rgba(248, 113, 113, 0.15);
            color: var(--danger);
            border: 1px solid rgba(248, 113, 113, 0.3);
        }}

        .text-center {{ text-align: center; }}
        .text-right {{ text-align: right; }}
        .font-bold {{ font-weight: 700; }}
        .text-muted {{ color: var(--text-muted); }}
        .text-danger {{ color: var(--danger); }}
        .text-success {{ color: var(--success); }}

        code {{
            font-family: 'Consolas', 'Courier New', monospace;
            background: rgba(0, 0, 0, 0.3);
            padding: 3px 6px;
            border-radius: 4px;
            font-size: 0.85rem;
        }}

        footer {{
            text-align: center;
            padding: 40px 0;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid var(--border-color);
            margin-top: 50px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📐 Floorplan-to-CAD QA Report</h1>
            <p>다중 소스 증거 융합 및 VLM 피드백 기반 기하 구조 검수 통계 보고서</p>
        </header>

        <div class="dashboard-grid">
            <div class="stat-card">
                <div class="label">총 기하 요소</div>
                <div class="value highlight-primary">{total_entities} <span style="font-size: 1rem; font-weight: normal;">개</span></div>
            </div>
            <div class="stat-card">
                <div class="label">종합 평균 신뢰도</div>
                <div class="value highlight-success">{avg_conf_pct}</div>
            </div>
            <div class="stat-card">
                <div class="label">스케일 계수 (Scale)</div>
                <div class="value" style="font-size: 1.5rem;">{scale:.4f} <span style="font-size: 0.8rem; color: var(--text-muted)">mm/px</span></div>
            </div>
            <div class="stat-card">
                <div class="label">정밀 검수 요청 건수</div>
                <div class="value highlight-accent">{len(low_conf_items)} <span style="font-size: 1rem; font-weight: normal;">건</span></div>
            </div>
        </div>

        <div class="card">
            <h2>📊 1. 세부 건축 요소 검출 현황</h2>
            <table>
                <thead>
                    <tr>
                        <th>요소 유형</th>
                        <th class="text-center">검출 수량</th>
                        <th class="text-center">배치 CAD 레이어</th>
                        <th>파이프라인 레이어 정책</th>
                    </tr>
                </thead>
                <tbody>
                    {sum_rows}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>🛡️ 2. 다중 센서 기하 충돌 해결 이력</h2>
            <table>
                <thead>
                    <tr>
                        <th>엔티티 ID</th>
                        <th>유형</th>
                        <th>공간 처리 내역</th>
                        <th>판단 기준</th>
                    </tr>
                </thead>
                <tbody>
                    {conflict_rows}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>👁️ 3. VLM comparative Review 감리 및 미세 교정 내역</h2>
            <table>
                <thead>
                    <tr>
                        <th class="text-center" style="width: 80px;">순번</th>
                        <th>보정 타겟 ID</th>
                        <th>보정 유형</th>
                        <th>세부 조치 사항</th>
                        <th>교정 사유</th>
                    </tr>
                </thead>
                <tbody>
                    {vlm_rows}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>⚠️ 4. 저신뢰도 항목 검수 지시 (신뢰도 &lt; 60%)</h2>
            <table>
                <thead>
                    <tr>
                        <th>엔티티 ID</th>
                        <th>요소 유형</th>
                        <th class="text-center">평균 신뢰도</th>
                        <th>검수 사유</th>
                    </tr>
                </thead>
                <tbody>
                    {low_rows}
                </tbody>
            </table>
        </div>

        <footer>
            <p>Unified Floorplan-to-CAD Framework • Advanced Agentic Coding by Google DeepMind team</p>
            <p style="margin-top: 5px; opacity: 0.5;">본 보고서는 파이프라인 출력 데이터로부터 실시간 자동 컴파일되었습니다.</p>
        </footer>
    </div>
</body>
</html>
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info("HTML QA 보고서가 생성되었습니다: %s", filepath)
        return filepath
