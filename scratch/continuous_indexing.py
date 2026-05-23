import os
import sys
import time
import json
from pathlib import Path

# Force ODA File Converter environment variable within Python
os.environ["ODA_FILE_CONVERTER"] = r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.corpus_run.pipeline_runner import CorpusPipelineRunner
from src.corpus_run.result_summarizer import CorpusRunResultSummarizer
from src.corpus_run.manifest import read_manifest

workspace = project_root / "outputs" / "webhard_all"
root_path = Path("Z:/내 드라이브/#웹하드")

print(f"=== HS-CAD Autonomous Corpus Indexer Initializing ===")
print(f"Workspace: {workspace}")
print(f"Webhard Root: {root_path}")
print(f"ODA File Converter: {os.environ['ODA_FILE_CONVERTER']}")

# Create pipeline runner
runner = CorpusPipelineRunner(workspace)

# 1. Prepare Workspace if not already prepared
manifest_path = workspace / "run_manifest.json"
if not manifest_path.exists():
    print("No manifest found. Scanning entire Z: webhard folder to build a comprehensive manifest...")
    start_time = time.time()
    prepared = runner.prepare(root_path, sample=0)
    duration = time.time() - start_time
    print(f"Manifest created successfully in {duration:.2f} seconds!")
    print(f"Total files identified: {prepared['file_count']}")
else:
    print(f"Existing manifest found at: {manifest_path}")

# Load entries
entries = read_manifest(manifest_path)
total_files = len(entries)
print(f"Total manifest entries to process: {total_files}")

# 2. Main Loop
batch_size = 100
chunk_idx = 0

while True:
    try:
        # Find already processed JSON records to calculate true progress
        json_dir = workspace / "fileized" / "json"
        failures_dir = workspace / "failures"
        
        ok_count = len(list(json_dir.glob("*.json"))) if json_dir.exists() else 0
        fail_count = len(list(failures_dir.glob("*.json"))) if failures_dir.exists() else 0
        processed_count = ok_count + fail_count
        
        progress_pct = (processed_count / total_files) * 100
        
        print(f"\n--- [Chunk #{chunk_idx}] Status: {processed_count}/{total_files} processed ({progress_pct:.2f}%) ---")
        
        if processed_count >= total_files:
            print("🎉 [SUCCESS] All files in the manifest have been processed successfully!")
            break
            
        # Run one batch of fileize
        print(f"Processing next batch of {batch_size} files...")
        batch_result = runner.fileize(limit=batch_size, offset=0, skip_existing=True)
        
        # Incremental indexing and learning
        print("Indexing records into SQLite database...")
        indexed = runner.index()
        
        print("Running block model learning...")
        runner.learn()
        
        print("Generating report and summaries...")
        runner.report()
        summarizer = CorpusRunResultSummarizer(workspace)
        summarizer.write_json()
        summarizer.write_markdown()
        
        print(f"Batch completed: processed {batch_result['processed']} entries in this slice.")
        
        chunk_idx += 1
        time.sleep(1)  # Brief pause between chunks for safety
        
    except KeyboardInterrupt:
        print("\n[INFO] Autonomous Indexer paused by user.")
        break
    except Exception as e:
        print(f"\n⚠️ [ERROR] Exception encountered during execution: {e}")
        print("Retrying in 5 seconds...")
        time.sleep(5)

print("\n=== HS-CAD Autonomous Corpus Indexer Finished ===")
