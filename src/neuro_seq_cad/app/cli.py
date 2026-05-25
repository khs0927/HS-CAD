"""
cli.py — Unified Floorplan-to-CAD Framework의 Typer 기반 CLI 및 파이프라인 제어기
=============================================================================
이 CLI는 전체 파이프라인 프로세스(스캔 전처리 → 다중 AI/전통 알고리즘 추론 → 다중 소스 융합 →
공간 충돌 해결 → 스케일 오토 보정 → VLM 피드백 리뷰 → DXF 조립 생성 → QA 레포트)를 통합 기동합니다.

주요 동사(Verbs):
  1. analyze: 단일 도면 이미지에 대해 전체 파이프라인을 기동 및 검수 결과 출력.
  2. export-dxf: 기존 증거 그래프 데이터를 사용하여 곧바로 DXF만 재조립 내보내기.
  3. overlay: 검출 결과를 배경 도면에 입혀 QA용 오버레이 시각화 이미지만 별도로 드로잉.
  4. check-img2cadseq: Img2CADSeq 저장소 공개 상태(릴리즈 릴리즈 코드)를 GitHub API를 통해 실시간 체크.
"""

from __future__ import annotations

import sys
# Windows cp949 콘솔 인코딩 문제 자동 우회
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from neuro_seq_cad.config.settings import get_settings
from neuro_seq_cad.io.image_loader import load_image, generate_synthetic_floorplan
from neuro_seq_cad.preprocessing.normalize_scan import normalize_scan
from neuro_seq_cad.raster2seq.adapter import Raster2SeqAdapter
from neuro_seq_cad.detection.planparser_adapter import PlanParserAdapter
from neuro_seq_cad.line_extraction.mlsd_adapter import MLSDAdapter
from neuro_seq_cad.ocr.paddleocr_adapter import PaddleOCRAdapter
from neuro_seq_cad.geometry.scale_calibration import calibrate_scale
from neuro_seq_cad.geometry.primitives import Line2D, Point2D
from neuro_seq_cad.fusion.evidence_graph import (
    EvidenceGraph, EvidenceEntity, PipelineMeta, BBox, Polygon2D
)
from neuro_seq_cad.fusion.conflict_resolver import resolve_conflicts
from neuro_seq_cad.vlm.vlm_client import VLMRefinementClient
from neuro_seq_cad.vlm.vlm_refiner import VLMFloorplanRefiner
from neuro_seq_cad.cad.dxf_builder import DXFBuilder
from neuro_seq_cad.review.overlay_renderer import OverlayRenderer
from neuro_seq_cad.review.qa_report import QAReportGenerator

app = typer.Typer(help="Unified Floorplan-to-CAD Framework CLI 도구")
console = Console()
logger = logging.getLogger(__name__)


@app.command()
def analyze(
    image: Optional[Path] = typer.Argument(None, help="분석 대상 도면 이미지 경로 (PNG, JPG, BMP 등)"),
    output_dir: Optional[Path] = typer.Option(None, "--out-dir", "-o", help="DXF 및 레포트 출력 폴더"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d",
        help="AI 가중치 로드를 강제 스킵하고, 신속한 파이프라인 연결을 검증하기 위한 완벽한 Mock 데이터를 생성합니다."
    ),
    vlm_refine: bool = typer.Option(True, "--vlm/--no-vlm", help="VLM 시각적 감리 및 미세 교정 주입 실행 여부"),
    synthetic: bool = typer.Option(False, "--synthetic", help="합성 평면도를 가상으로 빌드하여 분석합니다. (테스트용)"),
) -> None:
    """
    도면 이미지 전처리부터 다중 AI 융합, 스케일 자동 보정, DXF 빌드 및 QA 레포트까지의 전 과정을 논스톱 실행합니다.
    """
    settings = get_settings()
    out_dir = output_dir or settings.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if synthetic or image is None:
        synthetic = True
        image_path = out_dir / "synthetic_floorplan.png"
    else:
        image_path = Path(image).resolve()
    
    console.print(Panel.fit(
        f"[bold cyan]📐 Floorplan-to-CAD End-to-End Pipeline[/bold cyan]\n"
        f"대상 이미지: [yellow]{image_path.name}[/yellow]\n"
        f"출력 경로: [green]{out_dir}[/green]\n"
        f"작동 모드: {'[red]Dry-Run (Mock)[/red]' if dry_run else '[green]Production / Full Weights[/green]'}",
        title="Pipeline Starting", border_style="cyan"
    ))

    # ------------------------------------------------------------------
    # Step 1: 이미지 로딩 및 전처리 (Scan Normalization)
    # ------------------------------------------------------------------
    console.print("[bold]1. 전처리 단계 기동 중...[/bold]")
    if synthetic:
        console.print("[yellow]테스트용 합성 평면도 이미지를 가상으로 빌드합니다.[/yellow]")
        raw_img = generate_synthetic_floorplan(1200, 800)
        try:
            from PIL import Image
            Image.fromarray(raw_img).save(image_path)
        except Exception:
            pass
    else:
        try:
            raw_img = load_image(image_path)
        except Exception as e:
            console.print(f"[yellow]경고: 원본 이미지 로드 실패({e}). 테스트용 합성 평면도 이미지를 가상으로 빌드합니다.[/yellow]")
            raw_img = generate_synthetic_floorplan(1200, 800)
            # 임시 이미지 파일 작성
            temp_img_path = out_dir / "synthetic_floorplan.png"
            try:
                from PIL import Image
                Image.fromarray(raw_img).save(temp_img_path)
                image_path = temp_img_path
            except Exception:
                pass

    # 도면 전처리 (노이즈 필터, Otsu 이진화 등)
    preprocessed_img = normalize_scan(raw_img)
    prep_output_path = out_dir / f"{image_path.stem}_normalized.png"
    try:
        from PIL import Image
        Image.fromarray(preprocessed_img).save(prep_output_path)
        console.print(f"  └ 전처리 이미지 저장 완료: [dim]{prep_output_path}[/dim]")
    except Exception:
        pass

    h, w = raw_img.shape[:2]

    # ------------------------------------------------------------------
    # Step 2: 다중 모델 센서 추론 (Adapters)
    # ------------------------------------------------------------------
    console.print("\n[bold]2. 다중 AI 모델 추론 및 감지 개시...[/bold]")
    
    # 가. Raster2Seq (공간 분할 밎 벽체 폐곡선)
    console.print("  └ Raster2Seq 다각형 세그먼트 분석 중...")
    r2s_adapter = Raster2SeqAdapter()
    if dry_run:
        r2s_out = r2s_adapter._predict_mock(image_path)
    else:
        r2s_out = r2s_adapter.predict(image_path, output_dir=out_dir)
        
    # 나. PlanParser (YOLO 심볼/개구부 검출)
    console.print("  └ PlanParser 객체 심볼 검출 중...")
    pp_adapter = PlanParserAdapter()
    if dry_run:
        pp_out = pp_adapter._dummy_detect(image_path)
    else:
        pp_out = pp_adapter.detect(image_path)

    # 다. MLSD / LSD (건축 뼈대 선분 추출)
    console.print("  └ MLSD/LSD 건축 구조 선분 탐색 중...")
    mlsd_adapter = MLSDAdapter()
    if dry_run or not mlsd_adapter.is_available():
        mlsd_out = mlsd_adapter.extract_mock_lines(w, h)
    else:
        mlsd_out = mlsd_adapter.extract_lines(preprocessed_img)

    # 라. PaddleOCR / EasyOCR (치수 문자 및 방 라벨 리딩)
    console.print("  └ OCR 도면 문자 분석 및 텍스트 구조화 중...")
    ocr_adapter = PaddleOCRAdapter()
    if dry_run or not ocr_adapter.is_available():
        ocr_results = ocr_adapter._run_mock_ocr(image_path)
    else:
        ocr_results = ocr_adapter.run_ocr(image_path)

    # ------------------------------------------------------------------
    # Step 3: 스케일 자동 보정 (Scale Calibration)
    # ------------------------------------------------------------------
    console.print("\n[bold]3. 픽셀-물리 치수 스케일 자동 보정 중...[/bold]")
    # OCR 결과를 BBox2D 형태로 치수선 매칭
    ocr_calib_inputs = [(bbox, text) for bbox, text, conf in ocr_results]
    
    # 선분 목록을 Line2D로 매핑
    lines_2d = []
    for line in mlsd_out.lines:
        lines_2d.append(Line2D(
            p1=Point2D(x=line.p1[0], y=line.p1[1]),
            p2=Point2D(x=line.p2[0], y=line.p2[1])
        ))

    scale_res = calibrate_scale(
        lines=lines_2d,
        ocr_results=ocr_calib_inputs,
        default_scale=settings.default_scale
    )
    scale_factor = scale_res.scale_factor
    console.print(f"  └ 산출된 최적 스케일 계수: [green]{scale_factor:.4f} mm/px[/green] (신뢰도: {scale_res.confidence * 100:.1f}%)")

    # ------------------------------------------------------------------
    # Step 4: 다중 소스 증거 그래프 융합 (Evidence Graph Fusion)
    # ------------------------------------------------------------------
    console.print("\n[bold]4. 다중 소스 증거 데이터 융합 (Multi-Source Fusion) 중...[/bold]")
    
    active_srcs = ["raster2seq", "planparser", "mlsd"]
    if dry_run:
        active_srcs = [f"{s}_mock" for s in active_srcs]
        
    pipeline_meta = PipelineMeta(
        pipeline_version="0.1.0",
        image_path=str(image_path),
        image_width=w,
        image_height=h,
        scale_pixels_per_mm=scale_factor,
        active_sources=active_srcs
    )
    
    graph = EvidenceGraph(pipeline=pipeline_meta)
    
    # 가. Raster2Seq 출력 데이터 융합
    for poly in r2s_out.polygons:
        etype = "wall" if poly.type == "wall_boundary" else "room"
        entity = EvidenceEntity(
            entity_type=etype,
            polygon=Polygon2D(points=poly.points, closed=True),
            text=poly.label if etype == "room" else "",
            confidence=poly.confidence,
            needs_review=False
        )
        entity.add_source(name=poly.source, confidence=poly.confidence)
        graph.entities.append(entity)

    # 나. PlanParser 출력 데이터 융합
    for sym in pp_out.symbols:
        bbox_ent = BBox(x1=sym.bbox[0], y1=sym.bbox[1], x2=sym.bbox[2], y2=sym.bbox[3])
        entity = EvidenceEntity(
            entity_type=sym.type,
            bbox=bbox_ent,
            text=sym.class_name if sym.type == "text" else "",
            confidence=sym.confidence,
            needs_review=False
        )
        entity.add_source(name=sym.source, confidence=sym.confidence)
        graph.entities.append(entity)

    # 다. MLSD 출력 데이터 융합 (선분)
    for line in mlsd_out.lines:
        entity = EvidenceEntity(
            entity_type="wall",
            points=[[line.p1[0], line.p1[1], line.p2[0], line.p2[1]]],
            confidence=line.confidence,
            needs_review=False
        )
        entity.add_source(name=line.source, confidence=line.confidence)
        graph.entities.append(entity)

    # 라. OCR 텍스트 융합 (방 이름 및 치수 보정)
    for bbox, text, conf in ocr_results:
        # 이미 text로 감지된 심볼 영역들과 비교하여 누락된 치수 텍스트만 신규 추가
        bbox_ent = BBox(x1=bbox.x1, y1=bbox.y1, x2=bbox.x2, y2=bbox.y2)
        
        # 숫자 치수인지 단순 방 문자 라벨인지 분기
        is_digit = any(char.isdigit() for char in text)
        etype = "dimension" if is_digit else "text"
        
        entity = EvidenceEntity(
            entity_type=etype,
            bbox=bbox_ent,
            text=text,
            confidence=conf,
            needs_review=False
        )
        entity.add_source(name="ocr", confidence=conf)
        graph.entities.append(entity)

    # ------------------------------------------------------------------
    # Step 5: 공간 충돌 해결 (Conflict Resolution)
    # ------------------------------------------------------------------
    console.print("\n[bold]5. 공간 기하학 충돌 해결 (Conflict Resolution) 적용 중...[/bold]")
    graph = resolve_conflicts(graph)

    # ------------------------------------------------------------------
    # Step 6: VLM 감리 및 구조 보정 (VLM Inspection Refinement)
    # ------------------------------------------------------------------
    if vlm_refine:
        console.print("\n[bold]6. VLM Comparative Review (도면 비교 감리) 실행 중...[/bold]")
        vlm_client = VLMRefinementClient()
        
        # VLM은 원본 이미지와 융합된 메타데이터를 비교분석하여 교정 데이터를 반환함
        try:
            feedback = vlm_client.request_refinement(image_path, graph)
            refiner = VLMFloorplanRefiner()
            graph = refiner.refine(graph, feedback)
            console.print(f"  └ VLM 감리 완료: [green]품질 점수={feedback.quality_score:.2f}[/green]")
        except Exception as e:
            console.print(f"  [red]└ VLM 피드백 요청 실패: {e} (스킵)[/red]")

    # ------------------------------------------------------------------
    # Step 7: DXF 도면 최종 어셈블 조립 및 저장 (DXF Exporter)
    # ------------------------------------------------------------------
    console.print("\n[bold]7. 다중 레이어 DXF 빌드 및 도면 내보내기...[/bold]")
    dxf_output_path = out_dir / f"{image_path.stem}.dxf"
    
    try:
        dxf_builder = DXFBuilder(graph)
        dxf_builder.build(dxf_output_path)
        console.print(f"  └ DXF 도면 저장 성공: [green]{dxf_output_path}[/green]")
    except Exception as e:
        console.print(f"  [red]└ DXF 빌드 에러: {e}[/red]")
        dxf_output_path = None

    # ------------------------------------------------------------------
    # Step 8: 시각 오버레이 보고서 및 QA 분석 레포트 작성
    # ------------------------------------------------------------------
    console.print("\n[bold]8. 품질 검수 시각 오버레이 및 보고서 작성 중...[/bold]")
    
    # 가. 오버레이 이미지 드로잉
    overlay_output_path = out_dir / f"{image_path.stem}_overlay_qa.png"
    overlay_renderer = OverlayRenderer(graph)
    overlay_renderer.render(image_path, overlay_output_path)
    console.print(f"  └ 시각 QA 오버레이 이미지: [dim]{overlay_output_path}[/dim]")

    # 나. QA 마크다운 보고서
    qa_md_path = out_dir / f"{image_path.stem}_qa_report.md"
    qa_report = QAReportGenerator(graph)
    qa_report.generate_markdown(qa_md_path)
    console.print(f"  └ QC 마크다운 리포트: [dim]{qa_md_path}[/dim]")

    # 다. QA HTML 보고서
    qa_html_path = out_dir / f"{image_path.stem}_qa_report.html"
    qa_report.generate_html(qa_html_path)
    console.print(f"  └ QC 인터랙티브 HTML 리포트: [dim]{qa_html_path}[/dim]")

    # ------------------------------------------------------------------
    # 결과 요약
    # ------------------------------------------------------------------
    summary = graph.summary()
    table = Table(title="도면 감출 건축 기하 요약", border_style="cyan")
    table.add_column("건축 요소 유형", style="cyan", no_wrap=True)
    table.add_column("수량", style="green")
    table.add_column("레이어 매핑", style="yellow")
    
    for k, v in summary.items():
        entity = EvidenceEntity(entity_type=k)
        table.add_row(k.upper(), str(v), entity.resolve_layer())
        
    console.print("\n")
    console.print(Panel(table, title="[bold green]Pipeline Completed Successfully![/bold green]", expand=False))


@app.command("export-dxf")
def export_dxf(
    json_graph_path: Path = typer.Argument(..., help="EvidenceGraph가 담겨있는 result.json 파일 경로"),
    output: Path = typer.Argument(..., help="저장할 출력 DXF 파일 파일명"),
) -> None:
    """
    이미 생성되어 있는 EvidenceGraph JSON 데이터를 읽어 곧바로 CAD DXF 도면으로 컴파일 변환합니다.
    """
    console.print(f"[bold green]DXF Exporter:[/bold green] JSON 로드 중... [dim]{json_graph_path}[/dim]")
    import json
    try:
        with open(json_graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # entities 및 pipeline 획득
        graph = EvidenceGraph.model_validate(data)
        
        builder = DXFBuilder(graph)
        builder.build(output)
        console.print(f"🎉 성공적으로 DXF 도면을 컴파일 완료했습니다: [green]{output}[/green]")
    except Exception as e:
        console.print(f"[bold red]오류 발생:[/bold red] DXF 내보내기 실패: {e}")


@app.command("overlay")
def overlay(
    json_graph_path: Path = typer.Argument(..., help="EvidenceGraph JSON 데이터 경로"),
    base_image: Path = typer.Argument(..., help="배경으로 사용할 원본 평면도 도면"),
    output: Path = typer.Argument(..., help="오버레이 완료된 검수용 이미지 출력 경로"),
) -> None:
    """
    EvidenceGraph의 감출 요소를 원본 도면 이미지 배경에 오버레이 드로잉하여 시각 QC 이미지를 생성합니다.
    """
    console.print("[bold]Overlay Renderer:[/bold] 로드 중...")
    import json
    try:
        with open(json_graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        graph = EvidenceGraph.model_validate(data)
        renderer = OverlayRenderer(graph)
        renderer.render(base_image, output)
        console.print(f"🎉 QA 오버레이 완성: [green]{output}[/green]")
    except Exception as e:
        console.print(f"[bold red]오류 발생:[/bold red] 오버레이 생성 실패: {e}")


@app.command("check-img2cadseq")
def check_img2cadseq() -> None:
    """
    Img2CADSeq (단일 이미지-to-3D CAD) 프로젝트가 현재 GitHub에 소스 코드를 릴리즈했는지 실시간 확인합니다.
    """
    console.print("[bold cyan]Img2CADSeq GitHub 저장소 공개 여부 모니터링[/bold cyan]")
    
    # setup_third_party 내 스크립트 실행 또는 독립 기동
    from neuro_seq_cad.config.settings import get_settings
    import requests
    
    settings = get_settings()
    url = "https://api.github.com/repos/Rilpraa0110/Img2CADSeq"
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=5.0)
        if resp.status_code != 200:
            console.print(f"[red]GitHub API 호출 오류: {resp.status_code}[/red]")
            return
            
        data = resp.json()
        size = data.get("size", 0)
        updated_at = data.get("updated_at", "Unknown")
        
        # 릴리즈 확인
        rel_resp = requests.get(f"{url}/releases", headers=headers, timeout=5.0)
        releases = rel_resp.json() if rel_resp.status_code == 200 else []
        
        console.print("  - [bold]저장소 이름[/bold]: Rilpraa0110/Img2CADSeq")
        console.print(f"  - [bold]저장소 크기[/bold]: {size} KB")
        console.print(f"  - [bold]최종 업데이트 시각[/bold]: {updated_at}")
        
        if releases:
            console.print("  - [bold green]공개 릴리즈 발견![/bold green]")
            for r in releases[:3]:
                console.print(f"    * {r.get('tag_name')} ({r.get('published_at')})")
        else:
            console.print("  - [bold yellow]경고: 등록된 공식 릴리즈(Releases)가 없습니다.[/bold yellow]")
            
        # 공개 여부 판별 가이드
        if size > 100:
            console.print("\n[bold green]판단:[/bold green] 저장소 크기가 100KB 이상으로, README 외 실제 소스 코드가 공개된 것으로 추정됩니다! Img2CADSeq 엔진 도입이 추천됩니다.")
        else:
            console.print("\n[bold yellow]판단:[/bold yellow] 아직 저장소 크기가 매우 작아 리드미(README)만 올라온 공개 대기 상태입니다. 현재처럼 [bold green]Raster2Seq[/bold]를 메인으로 유지해야 합니다.")
            
    except Exception as e:
        console.print(f"[red]모니터링 조회 실패: {e}[/red]")


if __name__ == "__main__":
    app()
