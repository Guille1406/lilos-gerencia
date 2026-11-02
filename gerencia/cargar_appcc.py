"""Carga el APPCC de un local (proveedores, equipos, servicios, productos de limpieza y protocolos) desde un JSON.

Uso, desde la raíz del repositorio (el JSON con datos reales no se publica):
    python gerencia/cargar_appcc.py datos-del-local.json

No duplica: lo que ya existe (mismo nombre o código en el mismo local) se deja como está.
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import db  # noqa: E402


def main(ruta: str) -> None:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    local = datos["local_id"]
    t = db.table

    # Proveedores (comunes a todos los locales)
    existentes = {p["nombre"]: p["id"] for p in t("proveedores").select("id, nombre").execute().data}
    for p in datos.get("proveedores", []):
        if p["nombre"] not in existentes:
            existentes[p["nombre"]] = t("proveedores").insert(p).execute().data[0]["id"]
    proveedor = lambda nombre: existentes[nombre] if nombre else None  # noqa: E731

    # Equipos con su revisión periódica y tareas del plan
    ya = {e["nombre"] for e in t("equipos").select("nombre").eq("local_id", local).execute().data}
    n_equipos = 0
    for e in datos.get("equipos", []):
        if e["nombre"] in ya:
            continue
        tareas = e.pop("tareas", [])
        proveedor_id = proveedor(e.pop("proveedor", None))
        fila = {**e, "local_id": local, "proveedor_id": proveedor_id}
        equipo_id = t("equipos").insert(fila).execute().data[0]["id"]
        for tarea in tareas:
            t("tareas_mantenimiento").insert({**tarea, "equipo_id": equipo_id,
                                              "proxima_fecha": tarea.get("proxima_fecha") or date.today().isoformat()}).execute()
        n_equipos += 1

    # Servicios de mantenimiento del local
    ya = {s["nombre"] for s in t("servicios").select("nombre").eq("local_id", local).execute().data}
    n_servicios = 0
    for s in datos.get("servicios", []):
        if s["nombre"] not in ya:
            proveedor_id = proveedor(s.pop("proveedor", None))
            t("servicios").insert({**s, "local_id": local, "proveedor_id": proveedor_id}).execute()
            n_servicios += 1

    # Productos de limpieza (Anexo 1)
    ya = {p["codigo"] for p in t("productos_limpieza").select("codigo").eq("local_id", local).execute().data}
    n_productos = 0
    for p in datos.get("productos_limpieza", []):
        if p["codigo"] not in ya:
            proveedor_id = proveedor(p.pop("proveedor", None))
            t("productos_limpieza").insert({**p, "local_id": local, "proveedor_id": proveedor_id}).execute()
            n_productos += 1

    # Protocolos con sus pasos
    ya = {p["nombre"] for p in t("protocolos").select("nombre").eq("local_id", local).execute().data}
    n_protocolos = 0
    for p in datos.get("protocolos", []):
        if p["nombre"] in ya:
            continue
        pasos = p.pop("pasos", [])
        protocolo_id = t("protocolos").insert({**p, "local_id": local}).execute().data[0]["id"]
        if pasos:
            t("protocolo_pasos").insert([{**paso, "protocolo_id": protocolo_id, "orden": i + 1}
                                         for i, paso in enumerate(pasos)]).execute()
        n_protocolos += 1

    print(f"Local {local}: {len(existentes)} proveedores en total · {n_equipos} equipos · {n_servicios} servicios · "
          f"{n_productos} productos de limpieza · {n_protocolos} protocolos nuevos")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
