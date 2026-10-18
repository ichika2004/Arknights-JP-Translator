"""Build Windows one-folder release and include OCR models next to the EXE.

Usage:
    python build_exe.py
    python build_exe.py --models-dir C:\\path\\to\\models

Expected release layout:
    dist/Arknights-JP-Translator/Arknights-JP-Translator.exe
    dist/Arknights-JP-Translator/models/PP-OCRv6_medium_det/
    dist/Arknights-JP-Translator/models/PP-OCRv6_medium_rec/
"""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import os
import shutil
import subprocess
import sys
from pathlib import Path

MODELS = ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec")
PROJECT_ROOT = Path(__file__).resolve().parent
RELEASE_NAME = "Arknights-JP-Translator"


def candidate_roots(explicit: Path | None):
    """Search user-supplied model root first, then standard PaddleX locations."""
    home = Path.home()
    roots = [
        explicit,
        PROJECT_ROOT / "models",
        PROJECT_ROOT / "model",
        home / ".paddlex" / "official_models",
        home / ".paddlex" / "models",
        home / ".paddleocr" / "models",
    ]
    for env_name in ("PADDLEX_HOME", "PADDLEOCR_HOME"):
        env_value = os.getenv(env_name)
        if env_value:
            value = Path(env_value).expanduser()
            roots += [value, value / "official_models", value / "models"]
    seen = set()
    for root in roots:
        if root is None:
            continue
        root = root.expanduser().resolve()
        if root not in seen:
            seen.add(root)
            yield root


def locate_models(explicit: Path | None):
    located = {}
    search_paths = list(candidate_roots(explicit))
    for name in MODELS:
        for root in search_paths:
            directory = root if root.name == name else root / name
            if directory.is_dir() and any(directory.iterdir()):
                located[name] = directory
                break
    missing = [name for name in MODELS if name not in located]
    if missing:
        searched = "\n  ".join(str(root) for root in search_paths)
        raise SystemExit(
            "找不到以下 OCR 模型，已停止建置，避免產生無法使用的 Release：\n"
            + "\n".join(f"- {name}" for name in missing)
            + f"\n查找位置：\n  {searched}\n"
            + "請先在開發環境成功執行一次 OCR，或使用：\n"
            + 'python build_exe.py --models-dir "C:\\模型上層資料夾"'
        )
    return located


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", type=Path, help="包含兩個 PP-OCRv6_* 模型資料夾的路徑")
    args = parser.parse_args()

    # Fail before the expensive build if model files are unavailable.
    models = locate_models(args.models_dir)
    for name, path in models.items():
        print(f"[Model] {name}: {path}", flush=True)

    import paddlex
    installed = {d.metadata["Name"].lower() for d in metadata.distributions() if d.metadata["Name"]}
    required = {name.lower() for name in paddlex.utils.deps.BASE_DEP_SPECS}
    deps = sorted(installed & required)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--console",
        "--name", RELEASE_NAME,
        "--runtime-hook", "rthook_dll.py",
        "--add-data", f"data/generated{os.pathsep}data/generated",
        "--add-data", f"assets{os.pathsep}assets",
        "--collect-all", "paddle",
        "--collect-all", "paddleocr",
        "--collect-all", "paddlex",
        "--collect-submodules", "arknights_translator",
    ]
    for dep in deps:
        command.extend(["--copy-metadata", dep])
    command.append("main.py")
    print("Copying metadata for:", ", ".join(deps), flush=True)
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)

    destination_root = PROJECT_ROOT / "dist" / RELEASE_NAME / "models"
    destination_root.mkdir(parents=True, exist_ok=True)
    for name, source in models.items():
        destination = destination_root / name
        if source != destination:
            shutil.copytree(source, destination, dirs_exist_ok=True)
        if not destination.is_dir() or not any(destination.iterdir()):
            raise RuntimeError(f"模型複製失敗：{name} -> {destination}")
        print(f"[OK] {name} -> {destination}", flush=True)

    exe = PROJECT_ROOT / "dist" / RELEASE_NAME / (RELEASE_NAME + ".exe")
    if not exe.is_file():
        raise RuntimeError(f"找不到 EXE：{exe}")
    print(f"\n完成：{exe.parent}\n請將整個 {RELEASE_NAME} 資料夾壓縮成 ZIP 發布。", flush=True)


if __name__ == "__main__":
    main()
