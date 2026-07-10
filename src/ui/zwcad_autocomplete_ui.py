# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import re
from pathlib import Path
import traceback

# Resolve and append project root directory for robust standalone module execution
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtCore import Qt, QPoint  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QListWidget, QPushButton, QLabel, QMessageBox, QMenu
)

# Core imports
from src.semantics.korean_indexer import KoreanMaterialIndexer  # noqa: E402
from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter  # noqa: E402


def find_drawing_file_by_name(filename: str, search_roots: list[str | Path] = ["C:\\CODE\\CAD\\HS-CAD", "G:\\내 드라이브"]) -> Path | None:
    """Recursively search for a drawing file by name under multiple roots (local & Google Drive)."""
    # 1. Strip full path prefixes if passed (only keep filename)
    filename = Path(filename).name
    
    for r in search_roots:
        root = Path(r)
        if not root.exists():
            continue
        try:
            # Recursive search for exact or similar drawing name
            for path in root.rglob(filename):
                if path.exists() and path.is_file():
                    return path
        except Exception:
            pass
    return None


class ZWCADAutocompletePanel(QMainWindow):
    """ZWCAD Smart Korean Material Autocomplete Overlay Panel with Cross-Reference Drawing Viewer."""
    
    def __init__(self, materials_file: str | Path):
        super().__init__()
        self.materials_file = Path(materials_file)
        self.indexer = KoreanMaterialIndexer(self.materials_file)
        self.zwcad_adapter = ZWCADCOMAdapter()
        self.is_connected = False
        
        self.init_ui()
        self.connect_to_zwcad()
        self.update_list()

    def init_ui(self) -> None:
        self.setWindowTitle("HS-CAD 지능형 지시선 한글 자동완성")
        self.resize(550, 680)
        self.setWindowFlags(Qt.WindowStaysOnTopHint) # Keep on top for CAD overlay work

        # Main Widget and Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Connection Status Label
        self.status_label = QLabel("ZWCAD 연결 상태 확인 중...")
        self.status_label.setStyleSheet("font-weight: bold; color: gray; margin-bottom: 5px;")
        main_layout.addWidget(self.status_label)

        # Search Bar Layout
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("검색할 지시선 입력 (예: 그라스울, ㄱㄹㅅㅇ, EPS)...")
        self.search_input.textChanged.connect(self.update_list)
        search_layout.addWidget(self.search_input)
        
        # Clear button
        clear_btn = QPushButton("초기화")
        clear_btn.clicked.connect(lambda: self.search_input.clear())
        search_layout.addWidget(clear_btn)
        main_layout.addLayout(search_layout)

        # Autocomplete Suggestions List
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("font-size: 13px; padding: 5px;")
        
        # Double Click -> Insert to CAD
        self.list_widget.itemDoubleClicked.connect(self.insert_selected_to_cad)
        
        # Enable Custom Context Menu for Right-Click Cross Referencing
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_context_menu)
        
        main_layout.addWidget(self.list_widget)

        # Guidance Label
        guide_lbl = QLabel("💡 팁: 리스트를 [더블클릭]하면 캐드에 삽입하며, [우클릭]하면 출처 도면을 열 수 있습니다.")
        guide_lbl.setStyleSheet("color: #0d47a1; font-size: 11px; font-weight: bold; margin-bottom: 5px;")
        main_layout.addWidget(guide_lbl)

        # Control Buttons Layout
        btn_layout = QHBoxLayout()
        
        # Insert MTEXT button
        insert_btn = QPushButton("📍 캐드에 지시선(텍스트) 삽입")
        insert_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b78e4;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1e5bb8;
            }
        """)
        insert_btn.clicked.connect(self.insert_selected_to_cad)
        btn_layout.addWidget(insert_btn)
        
        # Refresh connection button
        refresh_conn_btn = QPushButton("캐드 연결")
        refresh_conn_btn.clicked.connect(self.connect_to_zwcad)
        btn_layout.addWidget(refresh_conn_btn)
        
        main_layout.addLayout(btn_layout)

        # Statistics summary
        self.summary_label = QLabel(f"스캔된 지시선 사전 수: {len(self.indexer.materials)}개")
        self.summary_label.setStyleSheet("color: #666; font-size: 11px; margin-top: 5px;")
        main_layout.addWidget(self.summary_label)

    def connect_to_zwcad(self) -> None:
        """Attempt to bind to the active ZWCAD instance via COM Adapter."""
        try:
            self.zwcad_adapter.connect()
            connected = self.zwcad_adapter.app is not None
            if connected:
                self.is_connected = True
                self.status_label.setText("🟢 ZWCAD가 정상적으로 연결되어 연동 중입니다.")
                self.status_label.setStyleSheet("font-weight: bold; color: #2e7d32; margin-bottom: 5px;")
            else:
                self.is_connected = False
                self.status_label.setText("🔴 ZWCAD 실행 상태가 감지되지 않았습니다. (연결 대기 중)")
                self.status_label.setStyleSheet("font-weight: bold; color: #c62828; margin-bottom: 5px;")
        except Exception:
            self.is_connected = False
            self.status_label.setText("🔴 ZWCAD 연결 실패 (ZWCAD 활성 여부를 확인하세요)")
            self.status_label.setStyleSheet("font-weight: bold; color: #c62828; margin-bottom: 5px;")

    def update_list(self) -> None:
        """Trigger search using the Korean choseung/substring indexer and refresh UI list."""
        query = self.search_input.text()
        matches = self.indexer.search(query)
        
        self.list_widget.clear()
        self.list_widget.addItems(matches)
        
        if query:
            self.summary_label.setText(f"검색 결과: {len(matches)}개 / 전체 사전: {len(self.indexer.materials)}개")
        else:
            self.summary_label.setText(f"스캔된 지시선 사전 수: {len(self.indexer.materials)}개")

    def show_context_menu(self, position: QPoint) -> None:
        """Display Right-Click context menu listing source drawings for cross-referencing."""
        item = self.list_widget.itemAt(position)
        if not item:
            return
            
        note_text = item.text()
        sources = self.indexer.get_sources(note_text)
        
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { font-size: 12px; }")
        
        title_action = menu.addAction(f"지시선 출처 분석: '{note_text[:20]}...'")
        title_action.setEnabled(False)
        menu.addSeparator()

        # Add each drawing/source filename as a clickable action
        for src in sources:
            is_dwg_dxf = src.lower().endswith(('.dxf', '.dwg'))
            
            # Map old Z:\ drive letters to G:\ dynamically in the UI display
            corrected_src = re.sub(r"^[Zz]:\\", r"G:\\", src)
            corrected_src = re.sub(r"^[Zz]:/", r"G:/", corrected_src)
            
            icon_prefix = "📐 [도면 열기] " if is_dwg_dxf else "📄 [텍스트 출처] "
            action = menu.addAction(f"{icon_prefix}{corrected_src}")
            # Bind the click action dynamically
            action.triggered.connect(lambda checked=False, s=corrected_src: self.handle_source_click(s))

        menu.exec(self.list_widget.mapToGlobal(position))

    def handle_source_click(self, source_path_str: str) -> None:
        """Dynamically locate and open the source drawing in ZWCAD, or display information."""
        is_dwg_dxf = source_path_str.lower().endswith(('.dxf', '.dwg'))
        
        if not is_dwg_dxf:
            QMessageBox.information(
                self, 
                "출처 파일 안내", 
                f"이 지시선은 다음 텍스트 데이터 로그에서 수집되었습니다:\n\n{source_path_str}"
            )
            return

        # Double check Z: to G: conversion in case it was missed
        source_path_str = re.sub(r"^[Zz]:\\", r"G:\\", source_path_str)
        source_path_str = re.sub(r"^[Zz]:/", r"G:/", source_path_str)

        # Check if ZWCAD is connected
        self.connect_to_zwcad()
        if not self.is_connected or not self.zwcad_adapter.app:
            QMessageBox.warning(
                self, 
                "캐드 미연결", 
                f"ZWCAD가 실행되고 있지 않습니다.\n이 지시선이 포함된 도면은 다음과 같습니다:\n\n👉 {source_path_str}"
            )
            return

        try:
            original_path = Path(source_path_str)
            resolved_path: Path | None = None
            
            # 1. Try opening the direct path first
            if original_path.exists() and original_path.is_file():
                resolved_path = original_path
            else:
                # 2. Search for the file name dynamically under local project & Google Drive (G:)
                filename = original_path.name
                self.status_label.setText(f"🔎 파일 '{filename}'을 구글 드라이브 및 로컬 드라이브에서 실시간 탐색 중...")
                self.status_label.setStyleSheet("font-weight: bold; color: #f57c00; margin-bottom: 5px;")
                QApplication.processEvents()
                
                resolved_path = find_drawing_file_by_name(filename)
            
            if not resolved_path or not resolved_path.exists():
                self.status_label.setText("🟢 ZWCAD가 정상적으로 연결되어 연동 중입니다.")
                self.status_label.setStyleSheet("font-weight: bold; color: #2e7d32; margin-bottom: 5px;")
                QMessageBox.critical(
                    self, 
                    "도면 열기 실패", 
                    f"컴퓨터 내에서 혹은 구글 드라이브(G:)에서 도면 '{Path(source_path_str).name}'을 찾을 수 없습니다.\n파일이 다른 이름으로 변경되었거나 마운트 상태를 확인해 주세요."
                )
                return

            # 3. Tell ZWCAD to open the drawing via COM interface
            filename_only = resolved_path.name
            self.status_label.setText(f"📂 ZWCAD에서 '{filename_only}' 도면 여는 중...")
            self.status_label.setStyleSheet("font-weight: bold; color: #2b78e4; margin-bottom: 5px;")
            QApplication.processEvents()
            
            doc_path_str = str(resolved_path.resolve())
            self.zwcad_adapter.app.Documents.Open(doc_path_str)
            
            self.status_label.setText(f"🟢 도면 '{filename_only}' 열기 성공!")
            self.status_label.setStyleSheet("font-weight: bold; color: #2e7d32; margin-bottom: 5px;")
            
        except Exception as e:
            traceback.print_exc()
            self.status_label.setText("🟢 ZWCAD가 정상적으로 연결되어 연동 중입니다.")
            self.status_label.setStyleSheet("font-weight: bold; color: #2e7d32; margin-bottom: 5px;")
            QMessageBox.critical(
                self, 
                "도면 열기 오류", 
                f"ZWCAD로 도면을 여는 과정에서 오류가 발생했습니다.\n도면: {source_path_str}\n에러: {e}"
            )

    def insert_selected_to_cad(self) -> None:
        """Insert the selected material text directly into the active ZWCAD drawing at clicked coordinates."""
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "경고", "삽입할 지시선을 리스트에서 먼저 선택해 주세요.")
            return

        text_to_insert = selected_items[0].text()
        
        self.connect_to_zwcad()
        if not self.is_connected or not self.zwcad_adapter.app:
            QMessageBox.critical(
                self, 
                "캐드 연결 실패", 
                "ZWCAD가 연결되어 있지 않습니다.\nZWCAD를 먼저 실행한 뒤 '캐드 연결'을 시도하세요."
            )
            return

        try:
            self.status_label.setText("⚡ 캐드 화면 상에 지시선을 삽입할 위치를 직접 마우스 클릭해 주세요...")
            self.status_label.setStyleSheet("font-weight: bold; color: #f57c00; margin-bottom: 5px;")
            QApplication.processEvents()

            doc = self.zwcad_adapter.app.ActiveDocument
            utility = doc.Utility
            
            try:
                point = utility.GetPoint(Prompt="\n지시선 텍스트 삽입 좌표를 마우스로 클릭하세요: ")
            except Exception:
                self.status_label.setText("🟢 ZWCAD가 정상적으로 연결되어 연동 중입니다.")
                self.status_label.setStyleSheet("font-weight: bold; color: #2e7d32; margin-bottom: 5px;")
                return
            
            model_space = doc.ModelSpace
            text_height = doc.GetVariable("TEXTSIZE") or 3.0
            
            mtext_obj = model_space.AddMText(point, 0.0, text_to_insert)
            mtext_obj.Height = text_height
            
            try:
                doc.Layers.Add("HS-CAD-ADD-NOTE")
            except Exception:
                pass
            mtext_obj.Layer = "HS-CAD-ADD-NOTE"
                
            doc.Regen(1)
            
            self.status_label.setText(f" 성공: 캐드에 '{text_to_insert}'을 삽입했습니다.")
            self.status_label.setStyleSheet("font-weight: bold; color: #2e7d32; margin-bottom: 5px;")
            
        except Exception as e:
            traceback.print_exc()
            self.status_label.setText("🟢 ZWCAD가 정상적으로 연결되어 연동 중입니다.")
            self.status_label.setStyleSheet("font-weight: bold; color: #2e7d32; margin-bottom: 5px;")
            QMessageBox.critical(
                self, 
                "작도 실패", 
                f"ZWCAD로 객체를 전송하는 과정에서 오류가 발생했습니다.\n에러 내용: {e}"
            )


def main():
    materials_path = Path("oriental_materials_utf8.txt")
    if not materials_path.exists():
        materials_path = Path("oriental_materials.txt")

    app = QApplication(sys.argv)
    panel = ZWCADAutocompletePanel(materials_path)
    panel.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
