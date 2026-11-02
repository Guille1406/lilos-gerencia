"""Mete la «Limpieza de la plancha» dentro del protocolo de «Cierre» de cada local.

La plancha se limpia cada día al cierre: como rutina aparte era un registro más en Hoy. Este script, en cada local:
  1. copia los pasos activos del protocolo «Limpieza de la plancha» al final del «Cierre» (mismo texto, producto,
     día de la semana y semana del mes; sección «Plancha» si no tenían), con el `orden` que les toca;
  2. desactiva el protocolo de la plancha (activo = false). Sus registros antiguos se conservan.

Es idempotente: si el paso ya está en el Cierre (mismo texto) no se vuelve a copiar.

Uso, desde la carpeta LilOS (sin --aplicar solo enseña lo que haría):
    gerencia/.venv/Scripts/python gerencia/migraciones/plancha_en_cierre.py [--aplicar]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import db  # noqa: E402

SECCION = "Plancha"


def _es_plancha(protocolo: dict) -> bool:
    return (protocolo.get("nombre") or "").strip().lower().startswith("limpieza de la plancha")


def _es_cierre(protocolo: dict) -> bool:
    return (protocolo.get("nombre") or "").strip().lower() == "cierre" or protocolo.get("tipo") == "cierre"


def main(aplicar: bool) -> None:
    t = db.table
    protocolos = t("protocolos").select("*").execute().data
    locales = sorted({p["local_id"] for p in protocolos})
    for local in locales:
        del_local = [p for p in protocolos if p["local_id"] == local]
        planchas = [p for p in del_local if _es_plancha(p)]
        cierres = [p for p in del_local if _es_cierre(p) and p.get("activo", True)]
        if not planchas:
            print(f"· {local}: no tiene protocolo de plancha; nada que hacer")
            continue
        if not cierres:
            print(f"! {local}: tiene plancha pero no un «Cierre» activo; se deja como está")
            continue
        cierre = next((c for c in cierres if c["nombre"].strip().lower() == "cierre"), cierres[0])

        pasos_cierre = t("protocolo_pasos").select("*").eq("protocolo_id", cierre["id"]).execute().data
        ya = {(p["texto"] or "").strip().lower() for p in pasos_cierre if p.get("activo", True)}
        orden = max((p["orden"] for p in pasos_cierre), default=0)

        nuevos = []
        for plancha in planchas:
            pasos = (t("protocolo_pasos").select("*").eq("protocolo_id", plancha["id"]).eq("activo", True)
                     .order("orden").execute().data)
            for paso in pasos:
                if (paso["texto"] or "").strip().lower() in ya:
                    continue
                orden += 1
                ya.add((paso["texto"] or "").strip().lower())
                nuevos.append({"protocolo_id": cierre["id"], "orden": orden, "seccion": paso.get("seccion") or SECCION,
                               "texto": paso["texto"], "producto": paso.get("producto"),
                               "dia_semana": paso.get("dia_semana"), "semana_mes": paso.get("semana_mes"),
                               "activo": True})

        a_desactivar = [p for p in planchas if p.get("activo", True)]
        print(f"· {local}: {len(nuevos)} pasos de la plancha al final de «{cierre['nombre']}» "
              f"(tenía {len(pasos_cierre)}) · {len(a_desactivar)} protocolo(s) de plancha a desactivar")
        for paso in nuevos:
            print(f"    {paso['orden']:>3}. {paso['texto']}" + (f"  [{paso['producto']}]" if paso["producto"] else ""))

        if aplicar:
            if nuevos:
                t("protocolo_pasos").insert(nuevos).execute()
            for plancha in a_desactivar:
                t("protocolos").update({"activo": False}).eq("id", plancha["id"]).execute()

    print("Hecho." if aplicar else "Simulación: no se ha cambiado nada. Repite con --aplicar para guardarlo.")


if __name__ == "__main__":
    main("--aplicar" in sys.argv[1:])
