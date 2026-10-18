"""Arknights JP Translator — official application entry point.

Run: python main.py
"""
from __future__ import annotations
import sys


def main():
    if '--ocr-worker' in sys.argv:
        from arknights_translator.auto_detection_worker import main as worker_main
        return worker_main()
    if '--rogue-worker' in sys.argv:
        from arknights_translator.rogue_ocr_worker import main as worker_main
        return worker_main()

    # Import final layer once; it installs the shutdown-safe Controller.
    from arknights_translator.app_layers import shutdown
    return shutdown.previous.p233.old.p231.base.main()


if __name__ == '__main__':
    raise SystemExit(main())
