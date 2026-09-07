import os
import sys

from app import config, gui

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        lines = [
            "selftest-ok",
            f"frozen={bool(getattr(sys, 'frozen', False))}",
            f"frpc={os.path.exists(config.FRPC_EXE)}",
            f"frpc_path={config.FRPC_EXE}",
            f"data_dir={config.DATA_DIR}",
        ]
        out = config.DATA_DIR / "selftest.txt"
        out.write_text("\n".join(lines), encoding="utf-8")
        sys.exit(0)
    gui.main()