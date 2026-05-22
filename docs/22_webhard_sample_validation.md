# 22. Webhard Sample Validation Workflow

This guide is for the local Google Drive synchronized folder:

```powershell
Z:\내 드라이브\#웹하드
```

Google Drive contains several folders named `#웹하드`, and the local Windows path is the safest source for ZWCAD COM access because DWG scanning needs local files and a Windows ZWCAD environment.

## First safe sample pass

Start with a small sample. Do not run the full workspace first.

```powershell
python -m src.main corpus-run prepare --root "Z:\내 드라이브\#웹하드" --workspace "outputs/webhard_corpus_sample" --sample 20
python -m src.main corpus-run fileize --workspace "outputs/webhard_corpus_sample" --limit 20
python -m src.main corpus-run validate --workspace "outputs/webhard_corpus_sample"
python -m src.main corpus-run index --workspace "outputs/webhard_corpus_sample"
python -m src.main corpus-run learn --workspace "outputs/webhard_corpus_sample"
python -m src.main corpus-run quality --workspace "outputs/webhard_corpus_sample"
python -m src.main corpus-run report --workspace "outputs/webhard_corpus_sample"
```

## Review outputs

Check these files first:

```text
outputs/webhard_corpus_sample/run_manifest.json
outputs/webhard_corpus_sample/fileized/json/*.json
outputs/webhard_corpus_sample/failures/*.json
outputs/webhard_corpus_sample/cad_knowledge.sqlite
outputs/webhard_corpus_sample/learning_summary.json
outputs/webhard_corpus_sample/quality_audit.json
outputs/webhard_corpus_sample/QUALITY_AUDIT.md
outputs/webhard_corpus_sample/FINAL_REPORT.md
```

## Query examples

```powershell
python -m src.main corpus-run query "T100" --workspace "outputs/webhard_corpus_sample"
python -m src.main corpus-run evidence "그라스울" --workspace "outputs/webhard_corpus_sample"
python -m src.main corpus-run evidence "H-BEAM" --workspace "outputs/webhard_corpus_sample"
```

## When sample is stable

Increase gradually:

```powershell
python -m src.main corpus-run prepare --root "Z:\내 드라이브\#웹하드" --workspace "outputs/webhard_corpus_100" --sample 100
python -m src.main corpus-run fileize --workspace "outputs/webhard_corpus_100" --limit 100
python -m src.main corpus-run validate --workspace "outputs/webhard_corpus_100"
python -m src.main corpus-run index --workspace "outputs/webhard_corpus_100"
python -m src.main corpus-run learn --workspace "outputs/webhard_corpus_100"
python -m src.main corpus-run quality --workspace "outputs/webhard_corpus_100"
python -m src.main corpus-run report --workspace "outputs/webhard_corpus_100"
```

## Safety notes

- This workflow does not mutate drawings.
- DWG fileization opens local DWG files through ZWCAD COM and scans ModelSpace.
- If ZWCAD is not installed or COM is not available, DWG records become `unavailable` instead of crashing the whole run.
- PDF and image files can still be processed without ZWCAD.
- Always inspect `QUALITY_AUDIT.md` before increasing the sample size.
