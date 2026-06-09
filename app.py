"""Streamlit entrypoint — run from the project root:

    streamlit run app.py

Why this file exists: `streamlit run src/app/main.py` puts src/app/ on sys.path
(not the project root), so `import src.config` fails. Running this root-level
entrypoint guarantees the project root is importable, then delegates to the app.
"""

import os
import sys

# Make the project root importable so `import src.*` works no matter the CWD.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app.main import main  # noqa: E402  (must come after sys.path tweak)

main()
