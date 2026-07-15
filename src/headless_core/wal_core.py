# Headless Core implementation for XiCAD command: WAL (xiWAL)
import array
from typing import List, Tuple, Any
from pydantic import BaseModel, Field

class WALInput(BaseModel):
    thickness: float = Field(default=200.0, description="Thickness dimension")
    p1: Tuple[float, float] = Field(..., description="P1 coordinate tuple (X, Y)")
    p2: Tuple[float, float] = Field(..., description="P2 coordinate tuple (X, Y)")
    p3: Tuple[float, float] = Field(..., description="P3 coordinate tuple (X, Y)")
    p4: Tuple[float, float] = Field(..., description="P4 coordinate tuple (X, Y)")

def execute_wal(adapter: Any, input_data: WALInput) -> List[str]:
    """
    Executes WAL command in headless mode using CAD COM API.
    """
    doc = adapter.get_active_document()
    ms = doc.ModelSpace
    created_handles = []

    # 4 Corner Points to construct the wall
    pts = [input_data.p1, input_data.p2, input_data.p3, input_data.p4]
    flat_2d = []
    for p in pts:
        flat_2d.extend([p[0], p[1]])
    
    # Create double array for Lightweight Polyline
    double_array = array.array("d", flat_2d)
    pline = ms.AddLightWeightPolyline(double_array)
    pline.Closed = True
    created_handles.append(pline.Handle)
    
    # Create interior wall outline via offset
    try:
        offset_pline = pline.Offset(-input_data.thickness)
        if offset_pline:
            for item in offset_pline:
                created_handles.append(item.Handle)
    except Exception:
        try:
            offset_pline = pline.Offset(input_data.thickness)
            if offset_pline:
                for item in offset_pline:
                    created_handles.append(item.Handle)
        except Exception:
            pass

    return created_handles
