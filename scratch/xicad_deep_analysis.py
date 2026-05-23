# -*- coding: utf-8 -*-
import os
import json
from pathlib import Path
from collections import defaultdict

class XiCADDeepAnalyzer:
    def __init__(self, root_path="C:/xicad"):
        self.root = Path(root_path)
        self.stats = defaultdict(int)
        self.knowledge_dump = {
            "auto_leaders": [],
            "layer_settings": [],
            "common_texts": [],
            "text_boxes": [],
            "calculators": [],
            "ini_configs": {},
            "xml_configs": [],
            "slb_libraries": [],
            "lisp_files": [],
        }

    def _read_safe(self, path: Path):
        for enc in ["cp949", "utf-8", "euc-kr", "latin1"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    return f.read()
            except:
                pass
        return ""

    def analyze_xilib_texts(self):
        xilib = self.root / "xiLib"
        if not xilib.exists():
            return

        # 1. AutoLeader
        f_al = xilib / "xiAutoLeader.txt"
        if f_al.exists():
            lines = self._read_safe(f_al).splitlines()
            self.knowledge_dump["auto_leaders"] = [l.strip() for l in lines if l.strip()]

        # 2. CommonText
        f_ct = xilib / "xiCommonText.txt"
        if f_ct.exists():
            lines = self._read_safe(f_ct).splitlines()
            self.knowledge_dump["common_texts"] = [l.strip() for l in lines if l.strip()]

        # 3. TextBox
        f_tb = xilib / "xiTextBox.txt"
        if f_tb.exists():
            lines = self._read_safe(f_tb).splitlines()
            self.knowledge_dump["text_boxes"] = [l.strip() for l in lines if l.strip()]
            
        # 4. Layer Settings (.lay)
        for f in xilib.glob("*.lay"):
            content = self._read_safe(f)
            self.knowledge_dump["layer_settings"].append({
                "file": f.name,
                "content": content[:500] # preview
            })

    def analyze_root_configs(self):
        # INI files
        for f in self.root.glob("*.ini"):
            content = self._read_safe(f)
            self.knowledge_dump["ini_configs"][f.name] = content

        # XML files
        for f in self.root.glob("*.xml"):
            self.knowledge_dump["xml_configs"].append(f.name)

    def analyze_slb_libraries(self):
        # Find all .slb (Slide Library)
        for f in self.root.rglob("*.slb"):
            self.knowledge_dump["slb_libraries"].append({
                "name": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "path": str(f.relative_to(self.root))
            })

    def analyze_lisp_scripts(self):
        lisp_dir = self.root / "Lisp"
        if not lisp_dir.exists():
            return
            
        for f in lisp_dir.rglob("*"):
            if f.is_file():
                self.stats[f.suffix.lower()] += 1
                if f.suffix.lower() == ".lsp":
                    self.knowledge_dump["lisp_files"].append(f.name)

    def run(self):
        print(f"Starting deep analysis of {self.root}...")
        
        for root, dirs, files in os.walk(self.root):
            for f in files:
                self.stats["total_files"] += 1
                self.stats[f"ext_{Path(f).suffix.lower()}"] += 1
                
        self.analyze_xilib_texts()
        self.analyze_root_configs()
        self.analyze_slb_libraries()
        self.analyze_lisp_scripts()
        
        print("Analysis complete.")

    def export(self, out_json="outputs/xicad_deep_analysis_dump.json"):
        os.makedirs(os.path.dirname(out_json), exist_ok=True)
        out_data = {
            "statistics": self.stats,
            "knowledge": self.knowledge_dump
        }
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(out_data, f, ensure_ascii=False, indent=2)
        print(f"Dumped to {out_json}")

if __name__ == "__main__":
    analyzer = XiCADDeepAnalyzer()
    analyzer.run()
    analyzer.export()
