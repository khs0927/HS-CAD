# -*- coding: utf-8 -*-
import sys
import json
import sqlite3
from pathlib import Path

# Windows COM 라이브러리 임포트
try:
    import win32com.client
    import pythoncom
    COM_AVAILABLE = True
except ImportError:
    COM_AVAILABLE = False

DB_PATH = Path(r"C:\cad\HS-CAD-clone\outputs\webhard_all\cad_knowledge.sqlite")

def get_active_drawing_info():
    """ZWCAD COM 연동을 통해 현재 활성화된 도면 정보를 수집합니다."""
    if not COM_AVAILABLE:
        return {"status": "error", "message": "pywin32 library is not installed."}
    
    pythoncom.CoInitialize()
    try:
        zwcad = win32com.client.Dispatch("ZWCAD.Application")
        doc = zwcad.ActiveDocument
        ms = doc.ModelSpace
        
        # 간단한 오브젝트 카운팅
        counts = {}
        limit = min(500, ms.Count) # 속도 보호를 위한 최대 스캔 제한
        for i in range(limit):
            try:
                obj = ms.Item(i)
                name = obj.ObjectName
                counts[name] = counts.get(name, 0) + 1
            except Exception:
                continue
                
        return {
            "status": "success",
            "active_document": doc.Name,
            "path": doc.Path,
            "total_objects_in_modelspace": ms.Count,
            "scanned_samples": counts,
            "limited_scan": ms.Count > 500
        }
    except Exception as e:
        return {"status": "error", "message": f"Could not connect to active ZWCAD application. Error: {str(e)}"}
    finally:
        pythoncom.CoUninitialize()

def get_project_db_stats():
    """HS-CAD SQLite DB에 쿼리하여 현재 인덱싱된 도면 통계를 가져옵니다."""
    if not DB_PATH.exists():
        return {
            "status": "error", 
            "message": f"Database file not found at {DB_PATH}. Please run the indexing CLI first."
        }
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 테이블 존재 여부 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        stats = {"tables": tables}
        
        if "files" in tables:
            cursor.execute("SELECT COUNT(*) FROM files")
            stats["total_files"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT status, COUNT(*) FROM files GROUP BY status")
            stats["status_counts"] = dict(cursor.fetchall())
            
        if "layers" in tables:
            cursor.execute("SELECT COUNT(DISTINCT name) FROM layers")
            stats["unique_layers"] = cursor.fetchone()[0]
            
        if "dimensions" in tables:
            cursor.execute("SELECT COUNT(*) FROM dimensions")
            stats["total_dimensions"] = cursor.fetchone()[0]
            
        conn.close()
        return {"status": "success", "db_path": str(DB_PATH), "stats": stats}
    except Exception as e:
        return {"status": "error", "message": f"Failed to query local database. Error: {str(e)}"}

def main():
    # 표준 입력을 통한 JSON-RPC 기반 MCP Protocol 처리
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
                
            request = json.loads(line)
            
            # JSON-RPC 핸들러
            if "method" in request:
                method = request["method"]
                req_id = request.get("id")
                
                # MCP 프로토콜 핸들러
                if method == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {
                                "tools": {}
                            },
                            "serverInfo": {
                                "name": "hscad-zwcad-bridge",
                                "version": "1.0.0"
                            }
                        }
                    }
                elif method == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "tools": [
                                {
                                    "name": "get_active_drawing_info",
                                    "description": "ZWCAD COM 연동을 통해 현재 활성화된 도면 정보 및 객체 분포를 실시간으로 스캔합니다.",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {}
                                    }
                                },
                                {
                                    "name": "get_project_db_stats",
                                    "description": "HS-CAD SQLite 로컬 데이터베이스의 인덱싱 상태 및 데이터 통계를 조회합니다.",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {}
                                    }
                                }
                            ]
                        }
                    }
                elif method == "tools/call":
                    params = request.get("params", {})
                    tool_name = params.get("name")
                    
                    if tool_name == "get_active_drawing_info":
                        result_data = get_active_drawing_info()
                    elif tool_name == "get_project_db_stats":
                        result_data = get_project_db_stats()
                    else:
                        result_data = {"status": "error", "message": f"Unknown tool: {tool_name}"}
                        
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result_data, ensure_ascii=False, indent=2)
                                }
                            ]
                        }
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    }
                    
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
                
        except Exception as e:
            # 에러 발생 시 로그를 남김 (stderr)
            sys.stderr.write(f"Error in MCP Loop: {str(e)}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
