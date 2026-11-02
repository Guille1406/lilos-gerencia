"""Pruebas de core/impresion.py sin base de datos. Desde gerencia/: python -m tests.test_impresion

La caducidad tiene que salir igual que en la etiquetadora: se compara con lo que imprimió el navegador
(tests/fixtures/etiquetas-navegador.json, generado con el código real de public/index.html).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import impresion  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "etiquetas-navegador.json"


def test_caducidad_igual_que_la_etiquetadora():
    casos = json.loads(FIXTURES.read_text(encoding="utf-8"))["casos"]
    assert len(casos) >= 5
    for c in casos:   # incluye cambios de hora (marzo y octubre) y 30 días
        prep = datetime.fromisoformat(c["prep"])
        assert impresion.formato(prep) == c["esperado"]["prepStr"], c["nombre"]
        assert impresion.formato(impresion.caducidad(prep, c["expHours"])) == c["esperado"]["expStr"], c["nombre"]


def test_datos_del_trabajo():
    producto = {"id": "p1", "name": "Salsa Mayonesa Casera", "category": "Salsas y Aderezos", "storage": "refrigerado",
                "exp_hours": 72, "allergens": "Huevo"}
    prep = datetime(2026, 10, 24, 23, 50, tzinfo=impresion.ZONA)
    d = impresion.datos_trabajo(producto, prep, "Ana", lote=" l-1 ", copias=3)
    assert d["producto"] == "Salsa Mayonesa Casera" and d["alergenos"] == "Huevo" and d["copias"] == 3
    assert d["lote"] == "L-1" and d["responsable"] == "Ana" and d["horas_caducidad"] == 72
    assert datetime.fromisoformat(d["caducidad"]) == impresion.caducidad(prep, 72)
    assert impresion.formato(datetime.fromisoformat(d["caducidad"])) == "27/10/26 22:50"   # pasa el cambio de hora
    forzada = impresion.datos_trabajo(producto, prep, "", horas=impresion.dias_a_horas(0.5), copias=99)
    assert forzada["horas_caducidad"] == 12 and forzada["copias"] == impresion.MAX_COPIAS
    assert forzada["responsable"] == "DESCONOCIDO"


def test_dias_y_textos_como_la_etiquetadora():
    assert [impresion.dias_a_horas(d) for d in (0.5, 1, 1.5, 30)] == [12, 24, 36, 720]
    assert impresion.texto_dias(24) == "1 día"
    assert impresion.texto_dias(12) == "0,5 días"
    assert impresion.texto_dias(72) == "3 días"


def test_sedes():
    locales = ["enric-granados", "madrid", "sagrada-familia"]
    assert impresion.sedes(["madrid", "enric-granados"], locales) == ["madrid", "enric-granados"]
    assert impresion.sedes(["madrid"], locales) == ["madrid"]
    assert impresion.sedes([], locales) == locales                       # sin sede: todas
    assert impresion.sedes(["madrid"], locales, todas=True) == locales   # dirección y admin
    assert impresion.sedes(["borrado"], locales) == locales


def test_en_linea():
    ahora = datetime.fromisoformat("2026-10-19T10:00:00+00:00")
    assert impresion.en_linea({"ultimo_latido": "2026-10-19T09:59:00+00:00"}, ahora)
    assert not impresion.en_linea({"ultimo_latido": "2026-10-19T09:57:00+00:00"}, ahora)
    assert not impresion.en_linea({}, ahora)


if __name__ == "__main__":
    for nombre, prueba in list(globals().items()):
        if nombre.startswith("test_"):
            prueba()
            print("ok", nombre)
