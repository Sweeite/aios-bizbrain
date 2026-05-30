import sys
from pathlib import Path

# packs/ and config/ live at the repo root, one level above backend/
sys.path.insert(0, str(Path(__file__).parent.parent))
