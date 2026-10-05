# Permite `pytest etl/tests` desde la raíz del repo importando el paquete costos_etl.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
