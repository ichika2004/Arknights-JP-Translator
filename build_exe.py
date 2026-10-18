
import importlib.metadata as metadata
import subprocess
import sys

import paddlex

installed = {
    dist.metadata["Name"].lower()
    for dist in metadata.distributions()
    if dist.metadata["Name"]
}

required = {
    name.lower()
    for name in paddlex.utils.deps.BASE_DEP_SPECS
}

deps = sorted(installed & required)

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onedir",
    "--console",
    "--name", "Arknights-JP-Translator",
    "--runtime-hook", "rthook_dll.py",
    "--add-data", "data/generated;data/generated",
    "--add-data", "assets;assets",
    "--collect-all", "paddle",
    "--collect-all", "paddleocr",
    "--collect-all", "paddlex",
    "--collect-submodules", "arknights_translator",
]

for dep in deps:
    cmd.extend(["--copy-metadata", dep])

cmd.append("main.py")

print("Copying metadata for:", ", ".join(deps), flush=True)

subprocess.run(cmd, check=True)
