"""Modo demostración: arranca sin claves, recorre las páginas con cada rol y guarda solo en la sesión."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
SOLO_ADMIN = {"dispositivos", "errores", "perfiles"}   # en la demo no hay cuenta de admin
PAGINAS = sorted(p.stem for p in (Path(__file__).resolve().parents[1] / "paginas").glob("*.py") if p.stem not in SOLO_ADMIN)


def entrar(pin: str | None = "1111") -> AppTest:
    app = AppTest.from_file(APP, default_timeout=60).run()
    for tecla in pin or "":
        next(b for b in app.button if b.key == f"tecla-{tecla}").click()
        app.run()
    return app


def test_pide_pin_y_explica_la_demo():
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception
    assert "demostración" in app.info[0].value


@pytest.mark.parametrize("pin", ["1111", "2222"])
def test_entra_con_los_pines_de_prueba(pin):
    app = entrar(pin)
    assert not app.exception
    assert app.session_state.persona["id"].startswith("demo-")


def test_pin_incorrecto_no_entra():
    app = entrar("9999")
    assert "persona" not in app.session_state


@pytest.mark.parametrize("pagina", PAGINAS)
def test_ninguna_pagina_falla(pagina):
    app = entrar("1111")
    app.switch_page(f"paginas/{pagina}.py").run()
    assert not app.exception, [e.value for e in app.exception]


def test_datos_inventados_y_consultas():
    from core import demo, sesion  # noqa: F401
    datos = demo.datos_iniciales()
    assert all(t["tarea"] for t in datos["tareas_mantenimiento"])
    assert {p["telefono"][:6] for p in datos["proveedores"]} == {"600 00"}
    assert all(p["email"].endswith(".invalid") for p in datos["proveedores"])
