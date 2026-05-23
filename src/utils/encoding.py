from __future__ import annotations

import os
import sys


def ensure_utf8_stdio() -> None:
    """Best-effort UTF-8 console setup for Windows Korean paths/logs.

    PowerShell/cmd sessions may run with cp949 or another legacy code page.
    Reconfiguring Python stdio keeps Rich output and captured logs from failing
    when Korean project paths or prompts are printed.
    """
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    for stream_name in ('stdout', 'stderr'):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, 'reconfigure', None)
        if callable(reconfigure):
            try:
                reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
