"""Pruebas del historial de versiones (core/versiones.py), sin base de datos. Desde gerencia/: python -m tests.test_versiones"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import versiones  # noqa: E402

BASE = {"nombre": "Aseos", "tipo": "limpieza", "categoria": "appcc", "frecuencia": "diaria", "veces_dia": 1,
        "descripcion": "", "activo": True, "hora_limite": "10:00:00"}
PASOS = [
    {"orden": 2, "texto": "Fregar el suelo", "producto": "P1", "activo": True},
    {"orden": 1, "texto": "Vaciar papeleras", "seccion": "Sala", "activo": True},
    {"orden": 3, "texto": "Paso borrado", "activo": False},
]


def foto(**cambios):
    return versiones.armar_snapshot({**BASE, **cambios}, PASOS)


def test_snapshot_ordena_y_normaliza():
    f = foto()
    assert [p["texto"] for p in f["pasos"]] == ["Vaciar papeleras", "Fregar el suelo"]   # por orden, sin inactivos
    assert f["protocolo"]["hora_limite"] == "10:00" and f["protocolo"]["descripcion"] is None
    assert foto(descripcion="  ") == f                                                    # vacío = nada


def test_diferencias_frecuencia_y_campos():
    d = versiones.diferencias(foto(), foto(frecuencia="semanal", dias_semana=[3, 1], veces_dia=2))
    assert "Frecuencia: diaria → semanal" in d
    assert "Días de la semana: — → L, X" in d
    assert "Veces al día: 1 → 2" in d


def test_diferencias_pasos():
    a = foto()
    b = versiones.armar_snapshot(BASE, [
        {"orden": 1, "texto": "Vaciar papeleras", "seccion": "Sala"},
        {"orden": 2, "texto": "Fregar el suelo y las paredes", "producto": "P1"},
        {"orden": 3, "texto": "Reponer papel higiénico"},
    ])
    assert versiones.diferencias(a, b) == [
        "Paso cambiado: Fregar el suelo → Fregar el suelo y las paredes",
        "Paso añadido: Reponer papel higiénico"]
    c = versiones.armar_snapshot(BASE, [{"orden": 1, "texto": "Vaciar papeleras", "seccion": "Sala"}])
    assert versiones.diferencias(a, c) == ["Paso quitado: Fregar el suelo (producto P1)"]
    d = versiones.armar_snapshot(BASE, [{"orden": 1, "texto": "Vaciar papeleras", "seccion": "Sala"},
                                        {"orden": 2, "texto": "Fregar el suelo", "producto": "P2"}])
    assert versiones.diferencias(a, d) == ["Paso cambiado: Fregar el suelo → producto: P1 → P2"]


def test_diferencias_orden_y_sin_cambios():
    a = foto()
    b = versiones.armar_snapshot(BASE, [{"orden": 1, "texto": "Fregar el suelo", "producto": "P1"},
                                        {"orden": 2, "texto": "Vaciar papeleras", "seccion": "Sala"}])
    assert versiones.diferencias(a, b) == ["Orden de los pasos cambiado"]
    assert versiones.diferencias(a, foto()) == []
    assert versiones.diferencias(None, a) == ["Versión inicial"]


def test_solo_hay_version_nueva_si_cambia():
    f = foto()
    v1 = versiones.nueva_version(None, f, " Alta ", "Ana")
    assert v1["version"] == 1 and v1["motivo"] == "Alta" and v1["resumen"] == "Versión inicial"
    ultima = {"version": 1, "snapshot": f}
    assert versiones.nueva_version(ultima, foto(), "nada", "Ana") is None            # idéntico: no hay versión
    v2 = versiones.nueva_version(ultima, foto(frecuencia="semanal"), "Cambio", "Ana")
    assert v2["version"] == 2 and v2["resumen"] == "Frecuencia: diaria → semanal"


def test_guardar_version_con_tabla_y_sin_ella():
    class Q:   # consulta falsa: guarda lo insertado y devuelve lo que haya
        def __init__(self, tablas, nombre):
            self.t, self.n, self.fila = tablas, nombre, None

        def select(self, *a): return self
        def eq(self, *a): return self
        def order(self, *a, **k): return self
        def limit(self, *a): return self
        def insert(self, fila): self.fila = {"id": "x", **fila}; self.t.setdefault(self.n, []).append(self.fila); return self
        def update(self, *a): return self

        def execute(self):
            r = type("R", (), {})()
            r.data = [self.fila] if self.fila else sorted(self.t.get(self.n, []), key=lambda f: -f["version"])[:1]
            return r

    tablas = {}
    original = (versiones.db.table, versiones.snapshot)
    try:
        versiones.db.table = lambda n: Q(tablas, n)
        estado = {"f": foto()}
        versiones.snapshot = lambda _id: estado["f"]
        assert versiones.guardar_version("p", "Alta", "Ana")["version"] == 1
        assert versiones.guardar_version("p", "Otra vez", "Ana") is None
        estado["f"] = foto(frecuencia="mensual")
        assert versiones.guardar_version("p", "Cambio", "Ana")["version"] == 2

        def sin_tabla(_n):
            raise RuntimeError("relation does not exist")
        versiones.db.table = sin_tabla
        assert versiones.guardar_version("p", "x") is None and versiones.ultima("p") is None
        assert versiones.listar("p") == [] and not versiones.disponible()
    finally:
        versiones.db.table, versiones.snapshot = original


def test_markdown_imprimible():
    f = foto()
    md = versiones.como_markdown({"version": 3, "motivo": "Nueva norma", "cambiado_por": "Ana", "snapshot": f,
                                  "created_at": "2026-10-19T08:00:00+00:00", "resumen": "Paso añadido: X"})
    assert md.startswith("# Procedimiento Aseos · versión 3 · vigente desde 19/10/2026")
    assert "Nueva norma" in md and "Vaciar papeleras" in md and "Paso añadido: X" in md


if __name__ == "__main__":
    for nombre, f in list(globals().items()):
        if nombre.startswith("test_"):
            f()
            print("ok", nombre)
