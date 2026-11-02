"""Lo que el asistente de IA puede consultar de la intranet (solo lectura).

Cada función devuelve datos sencillos (listas y diccionarios) que se pasan tal cual al modelo.
"""
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core import db, plan, rumbo as rumbo_notas, sesion

RAIZ = Path(__file__).resolve().parents[2]
DOCUMENTOS = ["CONTEXTO.md", "README.md", "CHANGELOG.md"]
MAX_FILAS = 200


def _locales() -> dict:
    return {l["id"]: l["nombre"] for l in db.locales()}


def _equipos(local: str | None = None) -> list[dict]:
    return db.equipos(local or None)


def locales_y_personal() -> dict:
    locales = _locales()
    return {
        "locales": [{"id": i, "nombre": n} for i, n in locales.items()],
        "personal": [{"nombre": t["name"], "rol": t.get("rol") or "staff",
                      "local": ", ".join(locales.get(l, l) for l in sesion.sedes(t)) or "sin local asignado"} for t in db.trabajadores()],
    }


def _proveedores() -> dict:
    return {p["id"]: p for p in db.proveedores()}


def _empresa(proveedores: dict, proveedor_id) -> str | None:
    p = proveedores.get(proveedor_id)
    return f"{p['nombre']} ({p.get('servicio') or ''}) · tel. {p.get('telefono') or '—'}" if p else None


def _revision(objeto: dict, campo_frecuencia: str) -> dict:
    proxima = objeto.get("proxima_revision")
    return {"frecuencia_revision": plan.FRECUENCIAS_REVISION.get(objeto.get(campo_frecuencia)),
            "ultima_revision": plan.fecha_es(objeto["ultima_revision"]) if objeto.get("ultima_revision") else None,
            "proxima_revision": plan.fecha_es(proxima) if proxima else None,
            "estado_revision": plan.estado_tarea(date.fromisoformat(proxima))[1] if proxima else None}


def equipos(local: str | None = None) -> list[dict]:
    locales, proveedores = _locales(), _proveedores()
    campos = ("nombre", "tipo", "zona", "marca", "modelo", "numero_serie", "capacidad", "fecha_compra",
              "garantia_hasta", "servicio_tecnico", "contacto_tecnico", "temp_min", "temp_max", "revision_detalle",
              "notas")
    filas = []
    for e in _equipos(local):
        fila = {"local": locales.get(e["local_id"]), "estado": plan.ESTADOS_EQUIPO.get(e["estado"], e["estado"]),
                "empresa_tecnica": _empresa(proveedores, e.get("proveedor_id")),
                **{c: e.get(c) for c in campos}, **_revision(e, "revision_frecuencia")}
        filas.append({k: v for k, v in fila.items() if v not in (None, "")})
    return filas[:MAX_FILAS]


def servicios(local: str | None = None) -> list[dict]:
    locales, proveedores = _locales(), _proveedores()
    filas = []
    for s in db.servicios(local or None):
        fila = {"servicio": s["nombre"], "local": locales.get(s["local_id"]),
                "categoria": plan.CATEGORIAS_SERVICIO.get(s["categoria"], s["categoria"]),
                "empresa": _empresa(proveedores, s.get("proveedor_id")), "detalle": s.get("detalle"),
                "documentacion": s.get("documentacion"), "notas": s.get("notas"), **_revision(s, "frecuencia")}
        filas.append({k: v for k, v in fila.items() if v not in (None, "")})
    return filas


def proveedores() -> list[dict]:
    campos = ("nombre", "servicio", "contacto", "telefono", "email", "documentacion", "notas")
    return [{c: p.get(c) for c in campos if p.get(c)} for p in db.proveedores()]


def productos_limpieza(local: str | None = None) -> list[dict]:
    locales, proveedores = _locales(), _proveedores()
    filas = []
    for local_id in ([local] if local else list(locales)):
        for p in db.productos_limpieza(local_id):
            fila = {"local": locales.get(local_id), "codigo": p["codigo"], "producto": p["nombre"],
                    "marca": p.get("marca"), "uso": p.get("uso"), "dosis": p.get("dosis"),
                    "tiempo_contacto": p.get("tiempo_contacto"), "registro": p.get("registro") or "FALTA",
                    "fichas": "técnica y de seguridad" if p.get("ficha_tecnica") and p.get("ficha_seguridad")
                    else "faltan fichas", "peligros": p.get("peligros"),
                    "proveedor": (proveedores.get(p.get("proveedor_id")) or {}).get("nombre"),
                    "activo": p.get("activo")}
            filas.append({k: v for k, v in fila.items() if v not in (None, "")})
    return filas


def protocolos(local: str | None = None, nombre: str | None = None, dias_registros: int = 14) -> list[dict]:
    """Protocolos con sus pasos y los registros firmados de los últimos días."""
    locales = _locales()
    desde = date.today() - timedelta(days=int(dias_registros))
    salida = []
    for local_id in ([local] if local else list(locales)):
        for p in db.protocolos(local_id):
            if nombre and nombre.lower() not in p["nombre"].lower():
                continue
            pasos = [{"seccion": x.get("seccion"), "tarea": x["texto"], "producto": x.get("producto"),
                      "solo_el_dia": plan.DIAS_SEMANA.get(x.get("dia_semana")),
                      "solo_la_semana_del_mes": x.get("semana_mes")} for x in db.pasos(p["id"])]
            registros = [{"fecha": plan.fecha_es(r["fecha"]), "turno": r.get("turno"),
                          "hecho_por": r.get("realizado_por"), "verificado_por": r.get("verificado_por"),
                          "completo": r["completado"], "incidencias": r.get("incidencias")}
                         for r in db.registros_protocolo([p["id"]], 100) if date.fromisoformat(r["fecha"]) >= desde]
            franja, limite = plan.franja(p), plan.hora_limite(p)
            salida.append({"protocolo": p["nombre"], "local": locales.get(local_id),
                           "categoria": plan.CATEGORIAS[plan.categoria(p)],
                           "tipo": plan.TIPOS_PROTOCOLO.get(p["tipo"], p["tipo"]),
                           "frecuencia": plan.describir_frecuencia(p),
                           "momento": plan.FRANJAS[franja] if franja else p.get("momento"),
                           "hora_limite": f"{limite:%H:%M}" if limite else None,
                           "toca_hoy": plan.procedimiento_toca(p, date.today()),
                           "descripcion": p.get("descripcion"),
                           "pasos": [{k: v for k, v in x.items() if v} for x in pasos],
                           f"registros_ultimos_{dias_registros}_dias": registros})
    return salida


def tareas(local: str | None = None, dias: int = 30, solo_atrasadas: bool = False) -> list[dict]:
    locales = _locales()
    por_id = {e["id"]: e for e in _equipos(local)}
    hoy, limite = date.today(), date.today() + timedelta(days=int(dias))
    filas = []
    for t in db.tareas(list(por_id)):
        proxima = date.fromisoformat(t["proxima_fecha"])
        if proxima > limite or (solo_atrasadas and proxima >= hoy):
            continue
        e = por_id[t["equipo_id"]]
        filas.append({"tarea": t["tarea"], "equipo": e["nombre"], "local": locales.get(e["local_id"]),
                      "frecuencia": t["frecuencia"], "proxima_fecha": plan.fecha_es(proxima),
                      "estado": plan.estado_tarea(proxima)[1]})
    return filas[:MAX_FILAS]


def bitacora(local: str | None = None, dias: int = 180, equipo: str | None = None,
             tipo: str | None = None) -> dict:
    locales = _locales()
    por_id = {e["id"]: e for e in _equipos(local)} | {s["id"]: s for s in db.servicios(local or None)}
    if equipo:
        por_id = {i: e for i, e in por_id.items() if equipo.lower() in e["nombre"].lower()}
    desde = date.today() - timedelta(days=int(dias))
    filas = [h for h in db.bitacora(list(por_id), limite=1000) + db.bitacora_servicios(list(por_id), 1000)
             if date.fromisoformat(h["fecha"]) >= desde and (not tipo or h["tipo"] == tipo)]
    filas.sort(key=lambda h: h["fecha"], reverse=True)
    return {
        "apuntes": [{"fecha": plan.fecha_es(h["fecha"]),
                     "equipo_o_servicio": por_id[h.get("equipo_id") or h.get("servicio_id")]["nombre"],
                     "local": locales.get(por_id[h.get("equipo_id") or h.get("servicio_id")]["local_id"]),
                     "numero_factura": h.get("numero_factura"),
                     "tipo": plan.TIPOS_EVENTO.get(h["tipo"], h["tipo"]), "descripcion": h["descripcion"],
                     "coste_eur": float(h["coste"]) if h.get("coste") is not None else None,
                     "realizado_por": h.get("realizado_por")} for h in filas][:MAX_FILAS],
        "total_apuntes": len(filas),
        "gasto_total_eur": round(sum(float(h["coste"] or 0) for h in filas), 2),
    }


def rumbo(persona: str | None = None, estado: str = "abierto") -> list[dict]:
    """Encargos de Rumbo (órdenes, objetivos, proyectos) que puede ver quien pregunta, con su avance."""
    quien = sesion.actual()
    nombres = {t["id"]: t["name"] for t in db.trabajadores()}
    locales = _locales()
    notas = rumbo_notas.visibles(quien, rumbo_notas.todas([estado] if estado != "todos" else None))
    if persona:
        ids = {i for i, n in nombres.items() if persona.lower() in n.lower()}
        notas = [n for n in notas if ids & {n.get("para_id"), n.get("a_cargo_id")}]
    ve_valoracion = sesion.nivel(quien) >= sesion.NIVEL["gerente"]
    filas = []
    for n in sorted(notas, key=rumbo_notas.orden):
        hechas, total = rumbo_notas.progreso(n.get("contenido"))
        fila = {"titulo": n["titulo"], "tipo": n["tipo"], "para": nombres.get(n.get("para_id")),
                "a_cargo": nombres.get(n.get("a_cargo_id")), "encargado_por": nombres.get(n.get("creado_por_id")),
                "local": locales.get(n.get("local_id")), "vence": plan.fecha_es(n["vence"]) if n.get("vence") else None,
                "situacion_vencimiento": rumbo_notas.vence_texto(n.get("vence")) if n["estado"] == "abierto" else None,
                "prioridad": n.get("prioridad"), "estado": n["estado"],
                "casillas_hechas": f"{hechas}/{total}" if total else None,
                "pendiente": [c["texto"] for c in rumbo_notas.pendientes(n.get("contenido"))][:10] or None,
                "propiedades": n.get("propiedades") or None}
        if ve_valoracion:
            fila |= {"valoracion": n.get("valoracion"), "comentario_valoracion": n.get("comentario_valoracion")}
        filas.append({k: v for k, v in fila.items() if v not in (None, "")})
    return filas[:MAX_FILAS]


def catalogo() -> list[dict]:
    filas = db.table("productos").select("*").order("name").execute().data
    return [{"producto": p["name"], "categoria": p.get("category"), "conservacion": p.get("storage"),
             "caducidad_dias": round(p.get("exp_hours", 0) / 24, 1), "alergenos": p.get("allergens"),
             "vegano": bool(p.get("vegan"))} for p in filas][:MAX_FILAS]


def etiquetas(dias: int = 7, producto: str | None = None) -> dict:
    desde = (datetime.now(timezone.utc) - timedelta(days=int(dias))).isoformat()
    query = (db.table("registro_appcc").select("*").gte("fecha_impresion", desde)
             .order("fecha_impresion", desc=True).limit(1000))
    if producto:
        query = query.ilike("producto", f"%{producto}%")
    filas = query.execute().data
    por_producto, por_persona = {}, {}
    for f in filas:
        por_producto[f["producto"]] = por_producto.get(f["producto"], 0) + 1
        por_persona[f["responsable"]] = por_persona.get(f["responsable"], 0) + 1
    return {
        "total_etiquetas": len(filas),
        "por_producto": dict(sorted(por_producto.items(), key=lambda x: -x[1])),
        "por_persona": dict(sorted(por_persona.items(), key=lambda x: -x[1])),
        "ultimas": [{"impresa": datetime.fromisoformat(f["fecha_impresion"]).astimezone().strftime("%d/%m/%Y %H:%M"),
                     "producto": f["producto"], "preparacion": f["preparacion"], "caducidad": f["caducidad"],
                     "responsable": f["responsable"]} for f in filas[:50]],
        "nota": "El registro no guarda el local de cada etiqueta.",
    }


def documentacion(consulta: str) -> list[dict]:
    """Búsqueda sencilla por palabras en los apartados de la documentación del proyecto."""
    palabras = [p for p in re.findall(r"\w+", consulta.lower()) if len(p) > 3]
    apartados = []
    for nombre in DOCUMENTOS:
        ruta = RAIZ / nombre
        if not ruta.exists():
            continue
        for bloque in re.split(r"\n(?=#{1,3} )", ruta.read_text(encoding="utf-8")):
            puntos = sum(bloque.lower().count(p) for p in palabras)
            if puntos:
                apartados.append((puntos, nombre, bloque.strip()[:3000]))
    apartados.sort(key=lambda x: -x[0])
    return [{"documento": n, "texto": t} for _, n, t in apartados[:4]] or [{"resultado": "Nada encontrado"}]
