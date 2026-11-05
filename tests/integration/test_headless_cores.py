import time

from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter
from src.headless_core.mtb_core import MTBInput, execute_mtb
from src.headless_core.q1_core import Q1Input, execute_q1
from src.headless_core.wal_core import WALInput, execute_wal


def test_headless_wal_and_undo():
    """
    Test headless WAL core drawing and undo validation in ZWCAD 2026.
    """
    adapter = ZWCADCOMAdapter(visible=True, version="2026", start_if_needed=True)
    adapter.connect()
    
    # 1. Create a fresh document
    doc = adapter.app.Documents.Add()
    time.sleep(3)
    
    try:
        # Before state
        before_objects = adapter.scan_modelspace()
        before_handles = {obj['handle'] for obj in before_objects if obj.get('handle')}
        
        # 2. Run WAL Core
        wal_data = WALInput(
            thickness=200.0,
            p1=(0.0, 0.0),
            p2=(5000.0, 0.0),
            p3=(5000.0, 3000.0),
            p4=(0.0, 3000.0)
        )
        
        print("[INFO] Executing headless WAL...")
        created_handles = execute_wal(adapter, wal_data)
        assert len(created_handles) > 0, "WAL core should return created entity handles"
        
        # After state
        after_objects = adapter.scan_modelspace()
        after_handles = {obj['handle'] for obj in after_objects if obj.get('handle')}
        
        # Ensure new handles are registered in drawing
        for h in created_handles:
            assert h in after_handles, f"Created entity handle {h} should exist in active drawing"
            
        print(f"[SUCCESS] WAL drew {len(created_handles)} entities successfully.")
        
        # 3. Perform Undo & Validate Rollback
        print("[INFO] Performing Undo...")
        doc.SendCommand("_UNDO\n1\n")
        time.sleep(2)
        
        undo_objects = adapter.scan_modelspace()
        undo_handles = {obj['handle'] for obj in undo_objects if obj.get('handle')}
        
        # Rollback validation
        assert undo_handles == before_handles, "Drawing state must return to pre-execution state after Undo"
        print("[SUCCESS] Rollback validation passed. All created entities removed successfully.")
        
    finally:
        # Close without saving
        adapter.close()

def test_headless_mtb_and_undo():
    """
    Test headless MTB core drawing and undo validation in ZWCAD 2026.
    """
    adapter = ZWCADCOMAdapter(visible=True, version="2026", start_if_needed=True)
    adapter.connect()
    doc = adapter.app.Documents.Add()
    time.sleep(3)
    
    try:
        before_objects = adapter.scan_modelspace()
        before_handles = {obj['handle'] for obj in before_objects if obj.get('handle')}
        
        mtb_data = MTBInput(
            p1=(1000.0, 1000.0),
            width=1200.0,
            height=1500.0
        )
        
        print("[INFO] Executing headless MTB...")
        created_handles = execute_mtb(adapter, mtb_data)
        assert len(created_handles) > 0
        
        after_objects = adapter.scan_modelspace()
        after_handles = {obj['handle'] for obj in after_objects if obj.get('handle')}
        
        for h in created_handles:
            assert h in after_handles
            
        doc.SendCommand("_UNDO\n1\n")
        time.sleep(2)
        
        undo_objects = adapter.scan_modelspace()
        undo_handles = {obj['handle'] for obj in undo_objects if obj.get('handle')}
        assert undo_handles == before_handles
        print("[SUCCESS] MTB core test and rollback passed.")
        
    finally:
        adapter.close()


def test_headless_q1_and_undo():
    """Test headless Q1 block insertion and rollback in ZWCAD 2026."""
    adapter = ZWCADCOMAdapter(visible=True, version="2026", start_if_needed=True)
    adapter.connect()
    doc = adapter.app.Documents.Add()
    time.sleep(3)

    try:
        before_objects = adapter.scan_modelspace()
        before_handles = {obj["handle"] for obj in before_objects if obj.get("handle")}

        q1_data = Q1Input(p1=(2500.0, 2500.0), block_name="HSCAD_Q1_HEADLESS_TEST")

        print("[INFO] Executing headless Q1...")
        created_handles = execute_q1(adapter, q1_data)
        assert len(created_handles) == 1, "Q1 core should return the inserted block handle"

        after_objects = adapter.scan_modelspace()
        after_handles = {obj["handle"] for obj in after_objects if obj.get("handle")}
        assert created_handles[0] in after_handles

        doc.SendCommand("_UNDO\n1\n")
        time.sleep(2)

        undo_objects = adapter.scan_modelspace()
        undo_handles = {obj["handle"] for obj in undo_objects if obj.get("handle")}
        assert undo_handles == before_handles
        print("[SUCCESS] Q1 core test and rollback passed.")

    finally:
        adapter.close()
