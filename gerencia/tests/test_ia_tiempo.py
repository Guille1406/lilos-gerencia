"""El asistente nunca se queda «Pensando…»: pasada la hora límite avisa sin llamar a más modelos."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import ia  # noqa: E402


def test_pasada_la_hora_limite_avisa_sin_llamar(monkeypatch):
    monkeypatch.setattr(ia, "_modelos", lambda: ["uno", "dos"])
    monkeypatch.setattr(ia, "_cliente", lambda: pytest.fail("no debe llamar al modelo"))
    monkeypatch.setattr(ia.registro, "apuntar", lambda *a, **k: None)
    with pytest.raises(ia.ErrorIA, match="tardando demasiado"):
        ia._completar([], hasta=time.monotonic() - 1)
