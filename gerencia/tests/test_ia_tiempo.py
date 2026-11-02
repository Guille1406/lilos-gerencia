"""El asistente nunca se queda «Pensando…»: pasada la hora límite avisa sin llamar a más modelos."""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import ia  # noqa: E402


def test_pasada_la_hora_limite_avisa_sin_llamar(monkeypatch):
    monkeypatch.setattr(ia, "_modelos", lambda: ["uno", "dos"])
    monkeypatch.setattr(ia, "_cliente", lambda: pytest.fail("no debe llamar al modelo"))
    monkeypatch.setattr(ia.registro, "apuntar", lambda *a, **k: None)
    with pytest.raises(ia.ErrorIA, match="tardando demasiado"):
        ia._completar([], hasta=time.monotonic() - 1)


class _ClienteFalso:
    """Devuelve un 503 las `fallos` primeras veces y después una respuesta."""

    def __init__(self, fallos):
        self.fallos, self.llamadas = fallos, 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **_):
        self.llamadas += 1
        if self.llamadas <= self.fallos:
            respuesta = httpx.Response(503, request=httpx.Request("POST", "http://ia.invalid"))
            raise openai.InternalServerError("saturado", response=respuesta, body=None)
        return SimpleNamespace(choices=[SimpleNamespace(message="hola")])


def _preparar(monkeypatch, cliente):
    monkeypatch.setattr(ia, "_modelos", lambda: ["uno", "dos"])
    monkeypatch.setattr(ia, "_cliente", lambda: cliente)
    monkeypatch.setattr(ia, "PAUSA_ENTRE_RONDAS", 0)
    monkeypatch.setattr(ia.registro, "apuntar", lambda *a, **k: None)


def test_distingue_no_conectar_de_no_contestar():
    peticion = httpx.Request("POST", "http://ia.invalid")
    error = openai.APITimeoutError(request=peticion)
    assert ia._motivo(error) == "sin respuesta a tiempo"
    error.__cause__ = httpx.ConnectTimeout("sin conexión")
    assert ia._motivo(error) == "sin conexión a tiempo"


def test_si_se_satura_reintenta_y_responde(monkeypatch):
    _preparar(monkeypatch, _ClienteFalso(fallos=3))
    assert ia._completar([]) == "hola"


def test_si_sigue_saturada_avisa_con_el_motivo(monkeypatch):
    cliente = _ClienteFalso(fallos=99)
    _preparar(monkeypatch, cliente)
    with pytest.raises(ia.ErrorIA, match=r"saturada.*503, 503, 503, 503"):
        ia._completar([])
    assert cliente.llamadas == 2 * ia.RONDAS
