from __future__ import annotations

from typing import Any
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

class SpatialIndexService:
    """High-performance R-tree spatial indexing service utilizing Shapely's STRtree.
    
    Provides O(log N) geometric queries (intersection, containment, nearest neighbors)
    to eliminate expensive O(N^2) loops in CAD processing pipelines.
    """
    
    def __init__(self, geometries: list[BaseGeometry]):
        self.geometries = [g for g in geometries if g is not None and not g.is_empty]
        # Initialize Shapely's STRtree
        self.tree = STRtree(self.geometries) if self.geometries else None
        
    def query_intersects(self, geom: BaseGeometry) -> list[BaseGeometry]:
        """Query all indexed geometries that intersect with the input geometry."""
        if not self.tree or geom is None or geom.is_empty:
            return []
        
        indices = self.tree.query(geom, predicate="intersects")
        return [self.geometries[idx] for idx in indices]
    
    def query_nearest(self, geom: BaseGeometry) -> BaseGeometry | None:
        """Find the single nearest indexed geometry to the input geometry."""
        if not self.tree or geom is None or geom.is_empty:
            return None
            
        idx = self.tree.nearest(geom)
        if idx is not None:
            try:
                # If it's a sequence/array, extract the first index
                if hasattr(idx, '__len__') and not isinstance(idx, (str, bytes)):
                    if len(idx) > 0:
                        return self.geometries[int(idx[0])]
                    return None
                # Directly convert scalar (numpy.int64 or python int)
                return self.geometries[int(idx)]
            except Exception:
                pass
        return None
