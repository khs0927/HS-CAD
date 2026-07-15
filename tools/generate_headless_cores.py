import os
import json
from pathlib import Path

# Paths
CONTRACTS_DIR = Path("C:/CODE/HS-CAD/hs-cad/outputs/xicad_contracts_all")
OUTPUT_CORE_DIR = Path("C:/CODE/HS-CAD/hs-cad-v0.3.0/src/headless_core")

def generate_headless_core_code(alias: str, function_name: str, args_spec: list[str]) -> str:
    """
    Generates structured Python code for a headless core command implementation.
    """
    code_lines = [
        f'# Headless Core implementation for XiCAD command: {alias} ({function_name})',
        'import array',
        'from typing import List, Tuple, Any',
        'from pydantic import BaseModel, Field',
        '',
        f'class {alias}Input(BaseModel):',
    ]
    
    # Write dynamic input schema based on template args
    if not args_spec:
        # Fallback fields based on alias
        if alias == "MTB":
            code_lines.extend([
                '    p1: Tuple[float, float] = Field(..., description="P1 coordinate tuple (X, Y)")',
                '    width: float = Field(default=1000.0, description="Toilet booth width")',
                '    height: float = Field(default=1200.0, description="Toilet booth height")',
            ])
        elif alias == "Q1":
            code_lines.extend([
                '    p1: Tuple[float, float] = Field(..., description="Insertion point tuple (X, Y)")',
                '    block_name: str = Field(default="Standard_Block", description="Name of the block to insert")',
            ])
        else:
            code_lines.append('    pass')
    else:
        for arg in args_spec:
            clean_arg = arg.strip("{}")
            if clean_arg.lower() in ("thickness", "width", "height"):
                code_lines.append(f'    {clean_arg}: float = Field(default=200.0, description="{clean_arg.capitalize()} dimension")')
            elif clean_arg.lower() in ("p1", "p2", "p3", "p4", "point", "insert_point"):
                code_lines.append(f'    {clean_arg}: Tuple[float, float] = Field(..., description="{clean_arg.capitalize()} coordinate tuple (X, Y)")')
            else:
                code_lines.append(f'    {clean_arg}: str = Field(..., description="Argument {clean_arg}")')
            
    code_lines.extend([
        '',
        f'def execute_{alias.lower()}(adapter: Any, input_data: {alias}Input) -> List[str]:',
        '    """',
        f'    Executes {alias} command in headless mode using CAD COM API.',
        '    """',
        '    doc = adapter.get_active_document()',
        '    ms = doc.ModelSpace',
        '    created_handles = []',
        ''
    ])
    
    # Specific implementation logic templates for WAL, MTB, Q1
    if alias == "WAL":
        code_lines.extend([
            '    # 4 Corner Points to construct the wall',
            '    pts = [input_data.p1, input_data.p2, input_data.p3, input_data.p4]',
            '    flat_2d = []',
            '    for p in pts:',
            '        flat_2d.extend([p[0], p[1]])',
            '    ',
            '    # Create double array for Lightweight Polyline',
            '    double_array = array.array("d", flat_2d)',
            '    pline = ms.AddLightWeightPolyline(double_array)',
            '    pline.Closed = True',
            '    created_handles.append(pline.Handle)',
            '    ',
            '    # Create interior wall outline via offset',
            '    try:',
            '        offset_pline = pline.Offset(-input_data.thickness)',
            '        if offset_pline:',
            '            for item in offset_pline:',
            '                created_handles.append(item.Handle)',
            '    except Exception:',
            '        try:',
            '            offset_pline = pline.Offset(input_data.thickness)',
            '            if offset_pline:',
            '                for item in offset_pline:',
            '                    created_handles.append(item.Handle)',
            '        except Exception:',
            '            pass',
        ])
    elif alias == "MTB":
        code_lines.extend([
            '    # Toilet Booth Cubicle Drawing',
            '    # Draws a standard rectangular cubicle at p1 with thickness/width dimensions',
            '    p1 = input_data.p1',
            '    width = getattr(input_data, "width", 1000.0)',
            '    height = getattr(input_data, "height", 1200.0)',
            '    ',
            '    # Construct 4 corner points',
            '    pts = [',
            '        (p1[0], p1[1]),',
            '        (p1[0] + width, p1[1]),',
            '        (p1[0] + width, p1[1] + height),',
            '        (p1[0], p1[1] + height)',
            '    ]',
            '    flat_2d = []',
            '    for p in pts:',
            '        flat_2d.extend([p[0], p[1]])',
            '        ',
            '    double_array = array.array("d", flat_2d)',
            '    pline = ms.AddLightWeightPolyline(double_array)',
            '    pline.Closed = True',
            '    created_handles.append(pline.Handle)',
        ])
    elif alias == "Q1":
        code_lines.extend([
            '    # Block Insertion',
            '    # Inserts block at p1 coordinate',
            '    p1 = input_data.p1',
            '    block_name = getattr(input_data, "block_name", "Standard_Block")',
            '    ',
            '    import win32com.client',
            '    # Add standard Block if it does not exist',
            '    try:',
            '        block = doc.Blocks.Add(array.array("d", [0.0, 0.0, 0.0]), block_name)',
            '        # Add a simple circle indicator inside block',
            '        block.AddCircle(array.array("d", [0.0, 0.0, 0.0]), 100.0)',
            '    except Exception:',
            '        pass',
            '        ',
            '    # Insert Block reference',
            '    try:',
            '        ins_pt = array.array("d", [p1[0], p1[1], 0.0])',
            '        ref = ms.InsertBlock(ins_pt, block_name, 1.0, 1.0, 1.0, 0.0)',
            '        created_handles.append(ref.Handle)',
            '    except Exception:',
            '        pass',
        ])
    else:
        # Default placeholder core
        code_lines.extend([
            '    # General drawing block placeholder',
            '    print(f"[INFO] General command execution for {alias}")',
        ])
        
    code_lines.extend([
        '',
        '    return created_handles',
    ])
    
    return "\n".join(code_lines) + "\n"

def run_generation(target_aliases: list[str]):
    OUTPUT_CORE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create __init__.py if not exists
    init_file = OUTPUT_CORE_DIR / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# Headless Core module init\n", encoding="utf-8")
        
    for alias in target_aliases:
        contract_file = CONTRACTS_DIR / f"{alias}.json"
        
        # Fallback to defaults if contract file does not exist
        if contract_file.exists():
            with open(contract_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            arg_templates = data.get("argument_templates", [])
            function_name = data.get("function", f"xi{alias}")
        else:
            if alias == "WAL":
                arg_templates = ["{thickness}", "{p1}", "{p2}", "{p3}", "{p4}", "C"]
                function_name = "xiDrawWall"
            elif alias == "MTB":
                arg_templates = ["{p1}", "{width}", "{height}"]
                function_name = "xiMakeToiletBooth"
            elif alias == "Q1":
                arg_templates = ["{p1}", "{block_name}"]
                function_name = "xiBlockLibrary"
            else:
                arg_templates = []
                function_name = f"xi{alias}"
                
        # Parse arguments
        args_spec = [arg for arg in arg_templates if arg.startswith("{") and arg.endswith("}")]
        
        # Generate code
        code = generate_headless_core_code(alias, function_name, args_spec)
        out_path = OUTPUT_CORE_DIR / f"{alias.lower()}_core.py"
        out_path.write_text(code, encoding="utf-8")
        print(f"[SUCCESS] Headless Core generated for {alias} at {out_path}")

if __name__ == "__main__":
    run_generation(["WAL", "MTB", "Q1"])
