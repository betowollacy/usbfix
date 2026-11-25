import os
import sys

from app import config
from app.gui import main as run_gui


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        # Confirma que o bundle CA do certifi foi incluído no executável.
        from app.ssl_context import create_ssl_context

        ssl_context = create_ssl_context()
        if ssl_context.cert_store_stats().get("x509_ca", 0) < 1:
            raise RuntimeError("O bundle de certificados SSL não foi carregado.")

        lines = [
            "selftest-ok",
            f"frozen={bool(getattr(sys, 'frozen', False))}",
            f"frpc={os.path.exists(config.FRPC_EXE)}",
            f"frpc_path={config.FRPC_EXE}",
            f"data_dir={config.DATA_DIR}",
            "ssl_ca=loaded",
        ]
        out = config.DATA_DIR / "selftest.txt"
        out.write_text("\n".join(lines), encoding="utf-8")
        sys.exit(0)
    run_gui()
