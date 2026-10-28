from pathlib import Path

import pytest

EXEMPLOS = Path(__file__).parent.parent / "exemplos"


@pytest.fixture
def ofx_exemplo() -> Path:
    return EXEMPLOS / "conta_exemplo.ofx"
