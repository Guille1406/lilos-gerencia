"""Pruebas del modo invitado (core/db.py): lee de verdad y nunca escribe. Sin base de datos.
Desde gerencia/: python -m tests.test_solo_lectura"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st  # noqa: E402

from core import db  # noqa: E402


class TablaFalsa:
    """Apunta cada llamada; si alguien llega a escribir, la prueba falla."""

    def __init__(self):
        self.llamadas = []

    def select(self, *a):
        self.llamadas.append("select")
        return self

    def insert(self, *a, **k):
        raise AssertionError("insert llegó a la base")

    update = upsert = delete = insert


def test_lecturas_pasan_y_escrituras_no():
    real = TablaFalsa()
    tabla = db._TablaSoloLectura(real)
    assert tabla.select("*") is real and real.llamadas == ["select"]
    r = tabla.insert({"nombre": "Nevera"}).execute()
    assert r.data[0]["nombre"] == "Nevera" and r.data[0]["id"]          # la pantalla sigue como si se guardara
    assert tabla.upsert([{"a": 1}, {"a": 2}]).execute().data[1]["a"] == 2
    assert tabla.update({"activo": False}).eq("id", "x").in_("y", []).execute().data == []
    assert tabla.delete().eq("id", "x").execute().data == []


def test_sin_invitado_no_hay_bloqueo():
    st.session_state.pop("invitado", None)
    assert not db.solo_lectura()
    st.session_state.invitado = True
    assert db.solo_lectura()
    st.session_state.pop("invitado", None)


if __name__ == "__main__":
    for nombre, prueba in list(globals().items()):
        if nombre.startswith("test_"):
            prueba()
            print("ok", nombre)
