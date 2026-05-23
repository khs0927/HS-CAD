from __future__ import annotations

import os
import time
from pathlib import Path

import typer

from src.app.cli import app
from src.app.logger import console, info, success, warn, error
from src.corpus_run.pipeline_runner import CorpusPipelineRunner
from src.corpus_run.result_summarizer import CorpusRunResultSummarizer
from src.corpus_run.manifest import read_manifest

@app.command('hscad-continuous-indexer')
def hscad_continuous_indexer(
    drive: str = typer.Option('Z:/', '--drive'),
    workspace: Path = typer.Option(Path('outputs/webhard_all'), '--workspace'),
    batch_size: int = typer.Option(100, '--batch-size'),
    sleep_interval: int = typer.Option(1, '--sleep-interval'),
    retry_interval: int = typer.Option(5, '--retry-interval'),
):
    """
    Autonomous background indexer that scans the entire drive and iteratively 
    processes chunks, populating the SQLite knowledge base endlessly until complete.
    """
    root = Path(drive) / '내 드라이브' / '#웹하드'
    if not root.exists():
        console.print({'error': f'Webhard root not found: {root}'})
        raise typer.Exit(code=2)
        
    os.environ["ODA_FILE_CONVERTER"] = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
    
    info("=== HS-CAD Autonomous Corpus Indexer Initializing ===")
    info(f"Workspace: {workspace}")
    info(f"Webhard Root: {root}")
    
    runner = CorpusPipelineRunner(workspace)
    manifest_path = workspace / "run_manifest.json"
    
    if not manifest_path.exists():
        info("No manifest found. Scanning entire webhard folder to build a comprehensive manifest...")
        start_time = time.time()
        prepared = runner.prepare(root, sample=0)
        duration = time.time() - start_time
        success(f"Manifest created successfully in {duration:.2f} seconds!")
        info(f"Total files identified: {prepared['file_count']}")
    else:
        info(f"Existing manifest found at: {manifest_path}")

    entries = read_manifest(manifest_path)
    total_files = len(entries)
    info(f"Total manifest entries to process: {total_files}")

    chunk_idx = 0
    while True:
        try:
            json_dir = workspace / "fileized" / "json"
            failures_dir = workspace / "failures"
            
            ok_count = len(list(json_dir.glob("*.json"))) if json_dir.exists() else 0
            fail_count = len(list(failures_dir.glob("*.json"))) if failures_dir.exists() else 0
            processed_count = ok_count + fail_count
            
            progress_pct = (processed_count / total_files * 100) if total_files > 0 else 100
            
            info(f"\n--- [Chunk #{chunk_idx}] Status: {processed_count}/{total_files} processed ({progress_pct:.2f}%) ---")
            
            if processed_count >= total_files:
                success("🎉 [SUCCESS] All files in the manifest have been processed successfully!")
                break
                
            info(f"Processing next batch of {batch_size} files...")
            batch_result = runner.fileize(limit=batch_size, offset=0, skip_existing=True)
            
            info("Indexing records into SQLite database...")
            runner.index()
            
            info("Running block model learning...")
            runner.learn()
            
            info("Generating report and summaries...")
            runner.report()
            summarizer = CorpusRunResultSummarizer(workspace)
            summarizer.write_json()
            summarizer.write_markdown()
            
            success(f"Batch completed: processed {batch_result['processed']} entries in this slice.")
            
            chunk_idx += 1
            time.sleep(sleep_interval)
            
        except KeyboardInterrupt:
            warn("\n[INFO] Autonomous Indexer paused by user.")
            break
        except Exception as e:
            error(f"\n⚠️ [ERROR] Exception encountered during execution: {e}")
            info(f"Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)

    success("\n=== HS-CAD Autonomous Corpus Indexer Finished ===")
