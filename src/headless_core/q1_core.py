# Headless Core implementation for XiCAD command: Q1 (xiQ1)
from typing import Any

import pythoncom
import win32com.client
from pydantic import BaseModel, Field


class Q1Input(BaseModel):
    p1: tuple[float, float] = Field(..., description="Insertion point tuple (X, Y)")
    block_name: str = Field(default="Standard_Block", description="Name of the block to insert")


def _point3d(x: float, y: float):
    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        [float(x), float(y), 0.0],
    )


def execute_q1(adapter: Any, input_data: Q1Input) -> list[str]:
    """
    Executes Q1 command in headless mode using CAD COM API.
    """
    doc = adapter.get_active_document()
    ms = doc.ModelSpace
    created_handles = []

    # Block Insertion
    # Inserts block at p1 coordinate
    p1 = input_data.p1
    block_name = getattr(input_data, "block_name", "Standard_Block")
    
    origin = _point3d(0.0, 0.0)

    # Add the test block definition only when it does not already exist.
    try:
        doc.Blocks.Item(block_name)
    except Exception:
        block = doc.Blocks.Add(origin, block_name)
        block.AddCircle(origin, 100.0)
        
    # Insert Block reference
    ins_pt = _point3d(p1[0], p1[1])
    ref = ms.InsertBlock(ins_pt, block_name, 1.0, 1.0, 1.0, 0.0)
    created_handles.append(ref.Handle)

    return created_handles
