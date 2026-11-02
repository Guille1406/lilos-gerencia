"""Pruebas de las reglas de «cuándo toca» (plan.py). Ejecutar desde gerencia/: python -m tests.test_plan"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import plan  # noqa: E402


def test_dia_mes_31_en_febrero_y_abril():
    p = {"frecuencia": "mensual", "dia_mes": 31}
    assert plan.ventana(p, date(2026, 2, 27)) is None          # 2026 no es bisiesto: toca el 28
    assert plan.ventana(p, date(2026, 2, 28)) == (date(2026, 2, 28), date(2026, 2, 28))
    assert plan.ventana(p, date(2028, 2, 28)) is None          # bisiesto: toca el 29
    assert plan.ventana(p, date(2028, 2, 29)) == (date(2028, 2, 29), date(2028, 2, 29))
    assert plan.ventana(p, date(2026, 4, 29)) is None
    assert plan.ventana(p, date(2026, 4, 30)) == (date(2026, 4, 30), date(2026, 4, 30))
    assert plan.ventana(p, date(2026, 1, 30)) is None and plan.procedimiento_toca(p, date(2026, 1, 31))


def test_dia_mes_se_queda_pendiente_hasta_fin_de_mes():
    p = {"frecuencia": "mensual", "dia_mes": 15}
    assert plan.ventana(p, date(2026, 6, 14)) is None
    assert plan.ventana(p, date(2026, 6, 15)) == (date(2026, 6, 15), date(2026, 6, 30))
    assert plan.ventana(p, date(2026, 6, 30)) == (date(2026, 6, 15), date(2026, 6, 30))


def test_dia_mes_manda_sobre_semana_mes():
    p = {"frecuencia": "mensual", "dia_mes": 20, "semana_mes": 1}
    assert plan.ventana(p, date(2026, 6, 3)) is None
    assert plan.ventana(p, date(2026, 6, 20)) == (date(2026, 6, 20), date(2026, 6, 30))
    q = {"frecuencia": "mensual", "semana_mes": 1}              # sin dia_mes sigue igual que antes
    assert plan.ventana(q, date(2026, 6, 3)) == (date(2026, 6, 1), date(2026, 6, 7))


def test_dia_mes_con_trimestral_y_anual():
    t = {"frecuencia": "trimestral", "mes_periodo": 2, "dia_mes": 10}
    assert plan.procedimiento_toca(t, date(2026, 5, 10)) and not plan.procedimiento_toca(t, date(2026, 4, 10))
    a = {"frecuencia": "anual", "mes_periodo": 3, "dia_mes": 31}
    assert plan.ventana(a, date(2026, 3, 31)) == (date(2026, 3, 31), date(2026, 3, 31))
    assert not plan.procedimiento_toca(a, date(2026, 4, 30))


def test_veces_dia():
    assert plan.veces_dia({}) == 1
    assert plan.veces_dia({"frecuencia": "diaria", "veces_dia": 2}) == 2
    assert plan.veces_dia({"frecuencia": "mensual", "veces_dia": 3}) == 1
    assert plan.veces_dia({"veces_dia": 9}) == 6
    assert plan.describir_frecuencia({"frecuencia": "diaria", "veces_dia": 2}) == "Diaria · 2 veces al día"
    assert plan.describir_frecuencia({"frecuencia": "mensual", "dia_mes": 15}) == "Mensual · día 15"


if __name__ == "__main__":
    for nombre, f in list(globals().items()):
        if nombre.startswith("test_"):
            f()
            print("ok", nombre)
