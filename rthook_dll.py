
import os
import sys
from pathlib import Path

_DLL_HANDLES = []

if sys.platform == "win32" and getattr(sys, "frozen", False):
    root = Path(sys._MEIPASS)

    folders = [
        root,
        root / "paddle" / "libs",
        root / "paddle" / "base",
    ]

    for folder in folders:
        if folder.is_dir():
            handle = os.add_dll_directory(str(folder))
            _DLL_HANDLES.append(handle)

            os.environ["PATH"] = (
                str(folder)
                + os.pathsep
                + os.environ.get("PATH", "")
            )
