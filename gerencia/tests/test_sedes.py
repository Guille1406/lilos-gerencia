"""Pruebas de las sedes de cada persona (core/sesion.py y core/rumbo.py), sin base de datos. Desde gerencia/: python -m tests.test_sedes"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import rumbo, sesion  # noqa: E402


def p(id, rol="staff", local_id=None, locales=None, **extra):
    return {"id": id, "name": id, "rol": rol, "local_id": local_id, "locales": locales, "activo": True, **extra}


def test_sedes_principal_primero_sin_repetir():
    assert sesion.sedes(p("a", local_id="madrid", locales=["enric-granados", "madrid"])) == ["madrid", "enric-granados"]
    assert sesion.sedes(p("a", locales=["madrid", "madrid"])) == ["madrid"]


def test_sedes_sin_columna_o_vacio():
    assert sesion.sedes({"id": "a", "local_id": "madrid"}) == ["madrid"]       # sin la columna: solo local_id
    assert sesion.sedes(p("a")) == [] and sesion.sedes(None) == []


def test_pertenece_y_en_sede():
    varias = p("a", locales=["enric-granados", "madrid"])
    assert sesion.pertenece(varias, "madrid") and not sesion.pertenece(varias, "sagrada-familia")
    ninguna = p("b")
    assert not sesion.pertenece(ninguna, "madrid") and sesion.en_sede(ninguna, "madrid")   # sin sedes = todas
    assert not sesion.en_sede(varias, "sagrada-familia")


def test_miembros_grupo_incluye_a_quien_tiene_la_sede():
    personal = [p("uno", local_id="enric-granados", locales=["enric-granados"]),
                p("dos", local_id="enric-granados", locales=["enric-granados", "madrid"]),
                p("tres", local_id="sagrada-familia", locales=["sagrada-familia"]),
                p("sin"), p("baja", locales=["madrid"], activo=False), p("jefe", "gerente", locales=["madrid"])]
    assert [t["id"] for t in rumbo.miembros_grupo(personal, "madrid")] == ["dos"]
    assert [t["id"] for t in rumbo.miembros_grupo(personal, "enric-granados")] == ["uno", "dos"]


def test_gerente_varias_sedes():
    g = p("g", "gerente", local_id="enric-granados", locales=["enric-granados", "madrid"])
    assert rumbo.puede_encargar(g, p("x", locales=["madrid"]))
    assert not rumbo.puede_encargar(g, p("y", locales=["sagrada-familia"]))
    assert rumbo.locales_para_grupo(g, ["enric-granados", "madrid", "sagrada-familia"]) == ["enric-granados", "madrid"]
    notas = [{"id": 1, "local_id": "madrid"}, {"id": 2, "local_id": "sagrada-familia"}]
    assert [n["id"] for n in rumbo.visibles(g, notas)] == [1]


if __name__ == "__main__":
    for nombre, f in list(globals().items()):
        if nombre.startswith("test_"):
            f()
            print("ok", nombre)
