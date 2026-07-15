# Headless Core implementation for XiCAD command: MTB (xiMTB)
import array
from typing import List, Tuple, Any
from pydantic import BaseModel, Field

class MTBInput(BaseModel):
    p1: Tuple[float, float] = Field(..., description="P1 coordinate tuple (X, Y)")
    width: float = Field(default=1000.0, description="Toilet booth width")
    height: float = Field(default=1200.0, description="Toilet booth height")

def execute_mtb(adapter: Any, input_data: MTBInput) -> List[str]:
    """
    Executes MTB command in headless mode using CAD COM API.
    """
    doc = adapter.get_active_document()
    ms = doc.ModelSpace
    created_handles = []

    # Toilet Booth Cubicle Drawing
    # Draws a standard rectangular cubicle at p1 with thickness/width dimensions
    p1 = input_data.p1
    width = getattr(input_data, "width", 1000.0)
    height = getattr(input_data, "height", 1200.0)
    
    # Construct 4 corner points
    pts = [
        (p1[0], p1[1]),
        (p1[0] + width, p1[1]),
        (p1[0] + width, p1[1] + height),
        (p1[0], p1[1] + height)
    ]
    flat_2d = []
    for p in pts:
        flat_2d.extend([p[0], p[1]])
        
    double_array = array.array("d", flat_2d)
    pline = ms.AddLightWeightPolyline(double_array)
    pline.Closed = True
    created_handles.append(pline.Handle)

    return created_handles
