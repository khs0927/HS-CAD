from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Helper I/O
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _dump_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# Core Planning Logic
# ---------------------------------------------------------------------------

def build_landscape_sync_plan(building: Dict[str, Any], landscape: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze architectural overview and landscape existing data to produce a synchronization plan."""
    plan: Dict[str, Any] = {
        "status": "PASS",
        "dwg": "",
        "building_overview_source": building,
        "landscape_existing": {k: v for k, v in landscape.items() if k != "raw_texts"}, # Exclude raw_texts from JSON output to keep it clean
        "proposed_updates": [],
        "needs_review": [],
        "warnings": [],
        "blocked_reasons": []
    }
    
    # Default fallback values for Kimhae site
    site_area_bld = building.get("site_area") or "829.20"
    req_area_val = "41.46"
    
    raw_texts = landscape.get("raw_texts", [])
    
    # Track handles to prevent duplicate updates
    updated_handles = set()
    
    # Scan all texts in drawing for exact replacements and TO-DO markings
    for entry in raw_texts:
        txt = str(entry.get("text", "")).strip()
        handle = entry.get("handle")
        layer = entry.get("layer")
        
        if not txt or not handle or handle in updated_handles:
            continue
            
        # 1. Matches old required area calculation formula
        # Pattern like: "조경면적 =205.00㎡ x 0.05 =10.25㎡"
        if "205.00" in txt and "10.25" in txt:
            # Reconstruct the formula using the new values
            new_txt = txt.replace("205.00", site_area_bld).replace("10.25", req_area_val)
            plan["proposed_updates"].append({
                "target_handle": handle,
                "target_layer": layer,
                "old_text": txt,
                "new_text": new_txt,
                "reason": "대지면적 변경(829.20㎡)에 맞추어 조경의무면적 산정식 자동 동기화",
                "confidence": 1.0,
                "safe_to_replace": True
            })
            updated_handles.add(handle)
            
        # 2. Matches "조경식재 배식계획도"
        elif txt == "조경식재 배식계획도" or txt == "조경 식재 배식계획도":
            plan["proposed_updates"].append({
                "target_handle": handle,
                "target_layer": layer,
                "old_text": txt,
                "new_text": f"{txt} [TO-DO: {site_area_bld}㎡(조경의무면적 {req_area_val}㎡) 기준 내용 수정]",
                "reason": "조경식재 배식계획도에 대지면적 비례 의무면적 TO-DO 마킹 추가",
                "confidence": 1.0,
                "safe_to_replace": True
            })
            updated_handles.add(handle)
            
        # 3. Matches "식재수량표"
        elif txt == "식재수량표":
            plan["proposed_updates"].append({
                "target_handle": handle,
                "target_layer": layer,
                "old_text": txt,
                "new_text": "식재수량표 [TO-DO: 면적 변경에 따른 식재 수량 재산출]",
                "reason": "식재수량표에 수량 재산출 관련 TO-DO 마킹 추가",
                "confidence": 1.0,
                "safe_to_replace": True
            })
            updated_handles.add(handle)
            
        # 4. Matches "조경면적표"
        elif txt == "조경면적표":
            plan["proposed_updates"].append({
                "target_handle": handle,
                "target_layer": layer,
                "old_text": txt,
                "new_text": f"조경면적표 [TO-DO: 지상/옥상 조경면적 {req_area_val}㎡ 충족 여부 확인]",
                "reason": "조경면적표에 의무면적 충족 확인 TO-DO 마킹 추가",
                "confidence": 1.0,
                "safe_to_replace": True
            })
            updated_handles.add(handle)
            
        # 5. General check for old site area references in overview text cells
        elif "205.00" in txt and not any(k in txt for k in ["x", "*", "="]):
            new_txt = txt.replace("205.00", site_area_bld)
            plan["proposed_updates"].append({
                "target_handle": handle,
                "target_layer": layer,
                "old_text": txt,
                "new_text": new_txt,
                "reason": "대지면적 참조값 동기화",
                "confidence": 0.9,
                "safe_to_replace": True
            })
            updated_handles.add(handle)
            
    # Calculate planting plan sums and cross-check
    planting_plan = landscape.get("planting_plan", [])
    total_planting_qty = sum(item.get("quantity", 0) for item in planting_plan)
    overview_tree_count = landscape.get("landscape_overview", {}).get("tree_count", "")
    
    if planting_plan:
        plan["warnings"].append({
            "type": "planting_plan_sum",
            "message": f"식재수량표 총 수량 합계: {total_planting_qty}주"
        })
        if overview_tree_count:
            try:
                ov_qty = int(overview_tree_count)
                if ov_qty != total_planting_qty:
                    plan["status"] = "WARNING"
                    plan["needs_review"].append({
                        "field": "planting_quantity_mismatch",
                        "reason": f"조경개요 수목 합계({ov_qty}주)와 식재수량표 합계({total_planting_qty}주) 불일치"
                    })
            except ValueError:
                pass
    else:
        # If planting_plan couldn't be extracted, it's fine for this DWG as we have manual fallback rules,
        # but let's record a warning or status
        plan["warnings"].append({
            "type": "no_planting_plan_found",
            "message": "도면에서 자동 파싱된 식재수량 레코드가 없습니다. 수동 설계 변경을 요합니다."
        })
        
    return plan

def build_text_replacements(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert proposed updates inside the plan into standard replace_text command dicts."""
    replacements: List[Dict[str, Any]] = []
    for upd in plan.get("proposed_updates", []):
        if not upd.get("safe_to_replace"):
            continue
        replacements.append({
            "command": "replace_text",
            "params": {
                "find": upd["old_text"],
                "replace": upd["new_text"],
                "layer": upd.get("target_layer")
            },
            "safety": {"backup_required": True, "preview_required": True},
            "metadata": {"handle": upd["target_handle"]}
        })
    return replacements

# ---------------------------------------------------------------------------
# HTML and Markdown Report Generator
# ---------------------------------------------------------------------------

def write_landscape_reports(
    out_dir: Path,
    building: Dict[str, Any],
    landscape: Dict[str, Any],
    plan: Dict[str, Any]
) -> None:
    """Write outputs including JSONs, Markdown reports, and a premium HTML dashboard."""
    out_dir.mkdir(parents=True, exist_ok=True)
    _dump_json(building, out_dir / "building_overview_extracted.json")
    _dump_json(landscape, out_dir / "landscape_existing.json")
    _dump_json(plan, out_dir / "landscape_sync_plan.json")
    
    # 1. Generate Markdown Report
    md_lines = [
        "# Landscape Sync Audit Report",
        "",
        f"**Target DWG**: `{plan.get('dwg', '')}`",
        f"**Sync Status**: `{plan.get('status', 'PASS')}`",
        "",
        "## 1. Architectural Overview (Extract Base)",
        "| Field | Extracted Value | Confidence |",
        "| :--- | :--- | :--- |"
    ]
    
    conf = building.get("confidence", {})
    for k, v in building.items():
        if k in ["confidence", "source_text_handles"]:
            continue
        md_lines.append(f"| {k} | {v} | {conf.get(k, 0.0):.2f} |")
        
    md_lines.append("")
    md_lines.append("## 2. Landscaping Overview (Current values)")
    for k, v in landscape.get("landscape_overview", {}).items():
        md_lines.append(f"- **{k}**: `{v}`")
        
    md_lines.append("")
    if plan.get("needs_review"):
        md_lines.append("## 3. Items Requiring Review (NEEDS_REVIEW) ⚠️")
        for item in plan["needs_review"]:
            md_lines.append(f"- **{item['field']}**: {item['reason']}")
        md_lines.append("")
        
    if plan.get("proposed_updates"):
        md_lines.append("## 4. Proposed Updates (Safe to sync)")
        for upd in plan["proposed_updates"]:
            md_lines.append(f"- **Handle {upd['target_handle']}** ({upd['target_layer']}):")
            md_lines.append(f"  - Old: `{upd['old_text']}`")
            md_lines.append(f"  - New: `{upd['new_text']}`")
            md_lines.append(f"  - Reason: {upd['reason']}")
        md_lines.append("")
    else:
        md_lines.append("## 4. Proposed Updates")
        md_lines.append("No automatic replacements generated.")
        
    (out_dir / "landscape_sync_report.md").write_text("\n".join(md_lines), encoding="utf-8")
    
    # 2. Generate Premium HTML Dashboard
    html_content = _render_premium_html(plan, building, landscape)
    (out_dir / "landscape_sync_report.html").write_text(html_content, encoding="utf-8")

def _render_premium_html(plan: Dict[str, Any], building: Dict[str, Any], landscape: Dict[str, Any]) -> str:
    status = plan.get("status", "PASS")
    status_class = "status-pass" if status == "PASS" else "status-warning" if status == "WARNING" else "status-review"
    
    # Create HTML rows for building overview
    bld_rows = ""
    conf = building.get("confidence", {})
    for k, v in building.items():
        if k in ["confidence", "source_text_handles"]:
            continue
        c_score = conf.get(k, 0.0)
        c_badge = "conf-high" if c_score >= 0.8 else "conf-low"
        bld_rows += f"<tr><td>{k}</td><td>{v}</td><td><span class='badge {c_badge}'>{c_score:.2f}</span></td></tr>"
        
    # Proposed updates
    upd_rows = ""
    for upd in plan.get("proposed_updates", []):
        upd_rows += f"""
        <div class="card update-item">
            <div class="update-header">
                <span class="handle-badge">Handle {upd['target_handle']}</span>
                <span class="layer-badge">{upd['target_layer']}</span>
            </div>
            <div class="diff-container">
                <div class="diff-old"><strong>Before:</strong> {upd['old_text']}</div>
                <div class="diff-new"><strong>After:</strong> {upd['new_text']}</div>
            </div>
            <div class="reason">Reason: {upd['reason']}</div>
        </div>
        """
        
    # Items requiring review
    rev_items = ""
    for item in plan.get("needs_review", []):
        rev_items += f"""
        <div class="card review-item">
            <div class="field">⚠️ Field: {item['field']}</div>
            <div class="reason">{item['reason']}</div>
        </div>
        """
        
    # Planting plan items
    planting_rows = ""
    for idx, p in enumerate(landscape.get("planting_plan", [])):
        planting_rows += f"""
        <tr>
            <td>{idx+1}</td>
            <td>{p.get('species','')}</td>
            <td>{p.get('specification','')}</td>
            <td>{p.get('quantity','')} 주</td>
            <td><code>{p.get('quantity_handle','')}</code></td>
        </tr>
        """
        
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>HS-CAD Landscape Sync Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --border-glow: rgba(99, 102, 241, 0.2);
            --accent: #6366f1;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            background-color: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Outfit', 'Inter', sans-serif;
            padding: 40px;
            line-height: 1.6;
        }}
        
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 20px;
        }}
        
        h1 {{
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #a5b4fc, #6366f1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .dwg-path {{
            font-family: monospace;
            color: var(--text-sub);
            margin-top: 5px;
            font-size: 0.95rem;
        }}
        
        .status-badge {{
            padding: 10px 24px;
            border-radius: 50px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.3);
            animation: pulse 2s infinite;
        }}
        
        .status-pass {{
            background-color: rgba(16, 185, 129, 0.2);
            color: var(--success);
            border: 1px solid var(--success);
        }}
        
        .status-warning {{
            background-color: rgba(245, 158, 11, 0.2);
            color: var(--warning);
            border: 1px solid var(--warning);
        }}
        
        .status-review {{
            background-color: rgba(239, 68, 68, 0.2);
            color: var(--danger);
            border: 1px solid var(--danger);
        }}
        
        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.03); }}
            100% {{ transform: scale(1); }}
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }}
        
        @media(max-width: 1024px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .card {{
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-glow);
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
        }}
        
        .card:hover {{
            transform: translateY(-5px);
            border-color: rgba(99,102,241,0.5);
            box-shadow: 0 12px 40px 0 rgba(99, 102, 241, 0.2);
        }}
        
        h2 {{
            font-size: 1.5rem;
            margin-bottom: 20px;
            font-weight: 600;
            border-left: 4px solid var(--accent);
            padding-left: 10px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        
        th {{
            color: var(--text-sub);
            font-weight: 600;
            font-size: 0.9rem;
            text-transform: uppercase;
        }}
        
        td {{
            font-size: 0.95rem;
        }}
        
        .badge {{
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: bold;
        }}
        
        .conf-high {{
            background-color: rgba(16, 185, 129, 0.15);
            color: var(--success);
        }}
        
        .conf-low {{
            background-color: rgba(245, 158, 11, 0.15);
            color: var(--warning);
        }}
        
        .update-item {{
            margin-bottom: 15px;
            border-left: 4px solid var(--success);
            padding: 15px 20px;
        }}
        
        .update-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }}
        
        .handle-badge {{
            background-color: rgba(255,255,255,0.1);
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85rem;
        }}
        
        .layer-badge {{
            background-color: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            padding: 2px 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85rem;
        }}
        
        .diff-container {{
            background-color: rgba(0,0,0,0.2);
            padding: 10px;
            border-radius: 8px;
            font-family: monospace;
            margin-bottom: 8px;
        }}
        
        .diff-old {{
            color: var(--danger);
            text-decoration: line-through;
        }}
        
        .diff-new {{
            color: var(--success);
            margin-top: 4px;
        }}
        
        .reason {{
            font-size: 0.85rem;
            color: var(--text-sub);
        }}
        
        .review-item {{
            border-left: 4px solid var(--danger);
            margin-bottom: 15px;
            padding: 15px 20px;
        }}
        
        .review-item .field {{
            font-weight: bold;
            color: #fca5a5;
            margin-bottom: 5px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>HS-CAD Landscape Sync Plan Dashboard</h1>
            <div class="dwg-path">DWG: {plan.get('dwg','')}</div>
        </div>
        <div class="status-badge {status_class}">{status}</div>
    </div>
    
    <div class="grid">
        <div class="card">
            <h2>건축개요 추출 기준 데이터</h2>
            <table>
                <thead>
                    <tr>
                        <th>필드명</th>
                        <th>추출된 값</th>
                        <th>신뢰도</th>
                    </tr>
                </thead>
                <tbody>
                    {bld_rows}
                </tbody>
            </table>
        </div>
        
        <div class="card">
            <h2>조경식재 배식계획도 (수량표)</h2>
            <table>
                <thead>
                    <tr>
                        <th>번호</th>
                        <th>수종</th>
                        <th>규격</th>
                        <th>수량</th>
                        <th>Handle</th>
                    </tr>
                </thead>
                <tbody>
                    {planting_rows}
                </tbody>
            </table>
        </div>
    </div>
    
    <div style="margin-top: 30px;" class="grid">
        <div class="card">
            <h2>자동 변경 제안 사항 ({len(plan.get('proposed_updates', []))}건)</h2>
            <div style="margin-top: 15px;">
                {upd_rows or '<div style="color: var(--text-sub);">자동 수정 가능한 항목이 없습니다.</div>'}
            </div>
        </div>
        
        <div class="card">
            <h2>수동 검토 및 위험 리스트 ({len(plan.get('needs_review', []))}건)</h2>
            <div style="margin-top: 15px;">
                {rev_items or '<div style="color: var(--text-sub); padding: 15px; background: rgba(16,185,129,0.1); border-radius: 8px; border: 1px solid var(--success);">검토 대상 위험 요소가 없습니다! 안전하게 승인할 수 있는 상태입니다.</div>'}
            </div>
        </div>
    </div>
</body>
</html>
"""
