import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src import config as C  # noqa: E402
from src import datos  # noqa: E402
from src.modelo import entrenar  # noqa: E402


@pytest.fixture(autouse=True)
def bd_temporal(tmp_path, monkeypatch):
    """Cada prueba usa su propia bitácora SQLite."""
    monkeypatch.setattr(C, "RUTA_BD", tmp_path / "prueba.db")


@pytest.fixture(scope="session")
def base():
    return datos.leer_base()


@pytest.fixture(scope="session")
def modelo(base):
    return entrenar(base)
