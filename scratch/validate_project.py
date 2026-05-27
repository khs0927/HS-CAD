# -*- coding: utf-8 -*-
"""HS-CAD-clone 프로젝트 품질 및 테스트 검증 스크립트"""
import subprocess
import os
import sys

def run_cmd(args):
    try:
        res = subprocess.run(args, capture_output=True, text=True, shell=True, encoding='utf-8')
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return -1, "", str(e)

def validate():
    print("======================================================================")
    print("프로젝트 검증 시작: Pytest & Git Diff 스캔")
    print("======================================================================")
    
    # 1. Pytest 실행
    print("Pytest 테스트 실행 중...")
    py_code, py_out, py_err = run_cmd("pytest tests/ --tb=short")
    print(f"Pytest 완료 (Exit Code: {py_code})")
    
    # 2. Git Status & Diff
    print("Git Diff 수집 중...")
    status_code, status_out, _ = run_cmd("git status")
    diff_code, diff_out, _ = run_cmd("git diff")
    
    # 3. 마크다운 리포트 생성
    report_path = r"C:\Users\khs09\.gemini\antigravity\brain\7fda61dd-af82-4394-8768-b540e75cbb44\validation_results.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 프로젝트 품질 검증 리포트\n\n")
        f.write("> [!NOTE]\n")
        f.write("> 복제 프로세스 완료 및 프로젝트의 코드 변경 사항과 테스트 통과 여부에 대한 검증 결과입니다.\n\n")
        
        f.write("## 1. Pytest 테스트 검증 결과\n")
        if py_code == 0:
            f.write("### ✅ 모든 테스트 통과 (PASS)\n")
        else:
            f.write("### ❌ 일부 테스트 실패 (FAIL)\n")
        f.write("```text\n")
        # 출력 내용 요약
        lines = py_out.splitlines()
        summary_lines = [l for l in lines if "passed" in l or "failed" in l or "error" in l or "====" in l]
        f.write("\n".join(summary_lines[-10:]) if summary_lines else py_out[:1000])
        f.write("\n```\n\n")
        
        f.write("## 2. Git Status\n")
        f.write("```text\n")
        f.write(status_out)
        f.write("\n```\n\n")
        
        f.write("## 3. Git Diff (변경 내용)\n")
        if diff_out.strip():
            f.write("```diff\n")
            f.write(diff_out[:5000]) # 용량 제어
            if len(diff_out) > 5000:
                f.write("\n... [일부 생략됨] ...\n")
            f.write("\n```\n")
        else:
            f.write("*코드 변경 사항이 존재하지 않습니다 (Clean).* \n")
            
    print(f"[SUCCESS] 검증 보고서 작성 완료: {report_path}")

if __name__ == "__main__":
    validate()
