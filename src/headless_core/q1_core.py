# Headless Core implementation for XiCAD command: Q1 (xiQ1)
import array
from typing import List, Tuple, Any
from pydantic import BaseModel, Field

class Q1Input(BaseModel):
    p1: Tuple[float, float] = Field(..., description="Insertion point tuple (X, Y)")
    block_name: str = Field(default="Standard_Block", description="Name of the block to insert")

def execute_q1(adapter: Any, input_data: Q1Input) -> List[str]:
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
    
    import win32com.client
    # Add standard Block if it does not exist
    try:
        block = doc.Blocks.Add(array.array("d", [0.0, 0.0, 0.0]), block_name)
        # Add a simple circle indicator inside block
        block.AddCircle(array.array("d", [0.0, 0.0, 0.0]), 100.0)
    except Exception:
        pass
        
    # Insert Block reference
    try:
        ins_pt = array.array("d", [p1[0], p1[1], 0.0])
        ref = ms.InsertBlock(ins_pt, block_name, 1.0, 1.0, 1.0, 0.0)
        created_handles.append(ref.Handle)
    except Exception:
        pass

    return created_handles
