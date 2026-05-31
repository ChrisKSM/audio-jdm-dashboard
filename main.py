# Entry module for Audio JDM Dashboard.
# Loads FastAPI app from wRE_dashboard/backend/main.py so `uvicorn main:app` works.
import importlib.util
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "wRE_dashboard", "backend")

sys.path.insert(0, _BACKEND_DIR)

_spec = importlib.util.spec_from_file_location(
    "jdm_backend_main", os.path.join(_BACKEND_DIR, "main.py")
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

app = _module.app
