from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from src.semantic_index.service import SemanticIndexService


class SemanticIndexApp:
    def __init__(self, root: tk.Tk, db_path: str | Path):
        self.root = root
        self.root.title('HS-CAD Semantic Index')
        self.root.geometry('980x620')
        self.db_var = tk.StringVar(value=str(db_path))
        self.records_var = tk.StringVar()
        self.query_var = tk.StringVar()
        self.status_var = tk.StringVar(value='Ready')
        self._build_ui()
        self.refresh_status()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text='HS-CAD 로컬 유사도 검색', font=('Segoe UI', 18, 'bold')).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 16))

        self._path_row(frame, 1, '인덱스 DB', self.db_var, self._choose_db, '파일 선택')
        self._path_row(frame, 2, '파일화 JSON 폴더', self.records_var, self._choose_records, '폴더 선택')
        self._path_row(frame, 3, '검색 기준 JSON', self.query_var, self._choose_query, '파일 선택')

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=4, sticky='w', pady=12)
        ttk.Button(button_frame, text='인덱스 만들기', command=self.build_index).pack(side='left', padx=(0, 8))
        ttk.Button(button_frame, text='유사 도면 검색', command=self.search).pack(side='left', padx=(0, 8))
        ttk.Button(button_frame, text='상태 새로고침', command=self.refresh_status).pack(side='left')

        columns = ('rank', 'score', 'drawing', 'entities', 'feature')
        self.results = ttk.Treeview(frame, columns=columns, show='headings', height=20)
        headings = {'rank': '순위', 'score': '유사도', 'drawing': '도면', 'entities': '객체 수', 'feature': '특징 버전'}
        widths = {'rank': 60, 'score': 100, 'drawing': 520, 'entities': 100, 'feature': 120}
        for key in columns:
            self.results.heading(key, text=headings[key])
            self.results.column(key, width=widths[key], anchor='w')
        self.results.grid(row=5, column=0, columnspan=4, sticky='nsew', pady=(8, 8))

        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.results.yview)
        scrollbar.grid(row=5, column=4, sticky='ns')
        self.results.configure(yscrollcommand=scrollbar.set)

        ttk.Label(frame, textvariable=self.status_var).grid(row=6, column=0, columnspan=4, sticky='w')
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(5, weight=1)

    def _path_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar, command, button_text: str) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, columnspan=2, sticky='ew', pady=4)
        ttk.Button(parent, text=button_text, command=command).grid(row=row, column=3, sticky='e', padx=(8, 0), pady=4)

    def _choose_db(self) -> None:
        selected = filedialog.asksaveasfilename(defaultextension='.sqlite3', filetypes=[('SQLite', '*.sqlite3'), ('All files', '*.*')])
        if selected:
            self.db_var.set(selected)
            self.refresh_status()

    def _choose_records(self) -> None:
        selected = filedialog.askdirectory()
        if selected:
            self.records_var.set(selected)

    def _choose_query(self) -> None:
        selected = filedialog.askopenfilename(filetypes=[('JSON', '*.json'), ('All files', '*.*')])
        if selected:
            self.query_var.set(selected)

    def _service(self) -> SemanticIndexService:
        return SemanticIndexService(self.db_var.get())

    def build_index(self) -> None:
        try:
            result = self._service().build_from_json_dir(self.records_var.get())
        except Exception as exc:
            messagebox.showerror('인덱스 오류', str(exc))
            return
        self.status_var.set(json.dumps(result, ensure_ascii=False))
        messagebox.showinfo('완료', f"{result['indexed']}개 도면을 인덱싱했습니다.")

    def search(self) -> None:
        try:
            hits = self._service().search_record(self.query_var.get(), limit=20)
        except Exception as exc:
            messagebox.showerror('검색 오류', str(exc))
            return
        for item in self.results.get_children():
            self.results.delete(item)
        for index, hit in enumerate(hits, start=1):
            self.results.insert('', 'end', values=(index, f'{hit.score:.4f}', hit.relative_path, hit.metadata.get('entity_count', ''), hit.feature_version))
        self.status_var.set(f'{len(hits)}개 유사 도면을 찾았습니다. 문자는 검색 점수에 사용되지 않았습니다.')

    def refresh_status(self) -> None:
        try:
            status = self._service().inspect()
            self.status_var.set(f"DB: {status['sqlite_path']} | 도면: {status['drawing_count']} | 모드: {status['mode']}")
        except Exception as exc:
            self.status_var.set(str(exc))


def run_app(db_path: str | Path = 'outputs/semantic_index/semantic.sqlite3') -> None:
    root = tk.Tk()
    SemanticIndexApp(root, db_path)
    root.mainloop()


if __name__ == '__main__':
    run_app()
