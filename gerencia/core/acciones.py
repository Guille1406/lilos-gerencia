"""Acciones que escriben en la base de datos (compartidas por varias páginas)."""
from datetime import date

import streamlit as st

from core import db, plan, registro, sesion


def registrar_evento(objeto: dict, tipo: str, descripcion: str, fecha: date, realizado_por: str,
                     coste: float | None = None, tarea: dict | None = None, marcar_operativo: bool = False,
                     es_revision: bool = False, numero_factura: str | None = None, es_servicio: bool = False) -> None:
    """Apunta una intervención en la bitácora (de un equipo o de un servicio) y mantiene al día el plan,
    la última y próxima revisión y el estado del equipo."""
    db.table("bitacora_equipos").insert({
        "equipo_id": None if es_servicio else objeto["id"],
        "servicio_id": objeto["id"] if es_servicio else None,
        "fecha": fecha.isoformat(),
        "tipo": tipo,
        "descripcion": descripcion.strip(),
        "coste": coste or None,
        "realizado_por": realizado_por.strip() or None,
        "tarea_id": tarea["id"] if tarea else None,
        "numero_factura": (numero_factura or "").strip() or None,
    }).execute()

    # Si cumple una tarea del plan, la siguiente vez se cuenta desde la fecha en que se hizo
    if tarea:
        db.table("tareas_mantenimiento").update({
            "proxima_fecha": plan.siguiente_fecha(fecha, tarea["frecuencia"]).isoformat()
        }).eq("id", tarea["id"]).execute()

    # La revisión periódica (técnico, retimbrado, visita de plagas…) mueve la última y la próxima revisión
    if es_revision:
        frecuencia = objeto.get("frecuencia" if es_servicio else "revision_frecuencia")
        proxima = plan.proxima_revision(fecha, frecuencia)
        db.table("servicios" if es_servicio else "equipos").update({
            "ultima_revision": fecha.isoformat(), "proxima_revision": proxima.isoformat() if proxima else None,
        }).eq("id", objeto["id"]).execute()

    # Una avería deja el equipo como averiado; una reparación puede devolverlo a operativo
    if not es_servicio:
        nuevo_estado = "averiado" if tipo == "averia" else ("operativo" if marcar_operativo else None)
        if nuevo_estado and nuevo_estado != objeto.get("estado"):
            db.table("equipos").update({"estado": nuevo_estado}).eq("id", objeto["id"]).execute()


def formulario_evento(objeto: dict, tarea: dict | None = None, clave: str = "evento", es_servicio: bool = False) -> bool:
    """Formulario para apuntar una intervención. Devuelve True si se ha guardado."""
    nombres = [t["name"] for t in db.trabajadores()]
    with st.form(clave, clear_on_submit=True):
        tipos = list(plan.TIPOS_EVENTO)
        tipo = st.selectbox("Tipo", tipos, format_func=plan.TIPOS_EVENTO.get,
                            index=tipos.index("inspeccion" if es_servicio else "mantenimiento"))
        descripcion = st.text_area("Qué se ha hecho", value=tarea["tarea"] if tarea else "",
                                   placeholder="Ej: Revisión anual del técnico, retimbrado, visita trimestral…")
        c1, c2, c3 = st.columns(3)
        fecha = c1.date_input("Fecha", value=date.today(), format="DD/MM/YYYY")
        quien = c2.selectbox("Hecho por", nombres + ["Servicio técnico externo", "Otro"],
                                         index=nombres.index(sesion.nombre()) if sesion.nombre() in nombres else 0) if nombres else \
            c2.text_input("Hecho por")
        coste = c3.number_input("Coste (€)", min_value=0.0, step=5.0, value=0.0)
        c1, c2 = st.columns(2)
        otro = c1.text_input("Empresa o persona (si es externo u otro)")
        factura = c2.text_input("Nº de factura o parte")
        es_revision = st.checkbox(
            "Es la revisión periódica (actualiza la última y la próxima revisión)",
            value=es_servicio and not tarea,
        ) if not tarea else False
        operativo = not es_servicio and objeto.get("estado") in ("averiado", "en_reparacion") and \
            st.checkbox("El equipo vuelve a estar operativo", value=True)
        if st.form_submit_button("Guardar en la bitácora", type="primary"):
            if not descripcion.strip():
                st.error("Escribe qué se ha hecho.")
                return False
            realizado = otro.strip() if otro.strip() else quien
            registrar_evento(objeto, tipo, descripcion, fecha, realizado, coste, tarea, bool(operativo),
                             es_revision, factura, es_servicio)
            return True
    return False


# ── Avería de un equipo: un aviso (flag) que deja el equipo averiado, abre el procedimiento y genera un informe ──
def avisar_averia(equipo: dict, que_pasa: str, afecta_alimentos: bool, quien: str) -> str:
    """Apunta la avería en la bitácora (el equipo queda averiado). Devuelve el texto guardado."""
    texto = que_pasa.strip() + (" · AFECTA A ALIMENTOS" if afecta_alimentos else "")
    registrar_evento(equipo, "averia", texto, date.today(), quien)
    return texto


def procedimientos_averia(local_id: str, equipo: dict | None = None) -> list[dict]:
    """Procedimientos de avería (tipo 'averia') del local; primero el que mejor encaja con el equipo
    (los de frío para neveras, congeladores, cámaras…)."""
    lista = [p for p in db.protocolos(local_id) if p.get("tipo") == "averia"]
    frio = bool(equipo) and any(c in (equipo.get("tipo") or "").lower()
                                for c in ("nevera", "congelador", "cámara", "camara", "refriger", "abatidor"))
    lista.sort(key=lambda p: not (frio and any(c in p["nombre"].lower() for c in ("frío", "frio"))))
    return lista


def incidencia_averia(equipo: dict, que_pasa: str) -> str:
    """Texto con el que se registra el procedimiento de avería: así el informe lo relaciona con el equipo."""
    return f"Avería de {equipo['nombre']}: {que_pasa.strip()}"


def informe_averia(equipo: dict, evento: dict) -> str:
    """Informe de una avería en markdown: equipo, cuándo, quién, qué pasa, pasos seguidos y no seguidos,
    acciones posteriores y estado actual del equipo."""
    from datetime import datetime
    creado = datetime.fromisoformat(evento["created_at"]).astimezone() if evento.get("created_at") else None
    actual = next((e for e in db.equipos(equipo.get("local_id")) if e["id"] == equipo["id"]), equipo)
    lineas = [f"# Informe de avería · {equipo['nombre']}", "",
              f"- **Equipo:** {equipo['nombre']} ({equipo.get('tipo') or '—'})"
              + (f" · {equipo['ubicacion']}" if equipo.get("ubicacion") else ""),
              f"- **Fecha y hora:** {plan.fecha_es(evento['fecha'])}" + (f" {creado:%H:%M}" if creado else ""),
              f"- **Avisó:** {evento.get('realizado_por') or '—'}",
              f"- **Qué pasa:** {evento['descripcion']}",
              f"- **Estado del equipo ahora:** {plan.ESTADOS_EQUIPO.get(actual.get('estado'), actual.get('estado') or '—')}",
              f"- **Técnico:** {actual.get('servicio_tecnico') or '—'} {actual.get('contacto_tecnico') or ''}".rstrip()]
    # Procedimiento de avería seguido ese día
    ids = [p["id"] for p in db.protocolos(equipo.get("local_id")) if p.get("tipo") == "averia"]
    nombres = {p["id"]: p["nombre"] for p in db.protocolos(equipo.get("local_id")) if p.get("tipo") == "averia"}
    marca = f"Avería de {equipo['nombre']}"
    registros = [r for r in db.registros_protocolo(ids, 200, desde=evento["fecha"])
                 if r["fecha"] == evento["fecha"] and (r.get("incidencias") or "").startswith(marca)]
    lineas += ["", "## Pasos del procedimiento"]
    if not registros:
        lineas.append("No se registró ningún procedimiento de avería.")
    for r in registros:
        hora = datetime.fromisoformat(r["created_at"]).astimezone().strftime("%H:%M")
        lineas.append(f"**{nombres.get(r['protocolo_id'], 'Procedimiento')}** · {r.get('realizado_por') or '—'} · {hora}")
        filas = db.table("protocolo_registro_pasos").select("hecho, protocolo_pasos(texto, orden)") \
            .eq("registro_id", r["id"]).execute().data
        for f in sorted(filas, key=lambda f: (f.get("protocolo_pasos") or {}).get("orden") or 0):
            lineas.append(f"- [{'x' if f['hecho'] else ' '}] {(f.get('protocolo_pasos') or {}).get('texto', '—')}"
                          f"{'' if f['hecho'] else ' (NO SEGUIDO)'}")
    # Lo que se hizo después en la bitácora del equipo
    despues = [h for h in db.bitacora([equipo["id"]]) if h["id"] != evento["id"]
               and (h["fecha"], h["created_at"]) >= (evento["fecha"], evento["created_at"])]
    lineas += ["", "## Acciones posteriores"]
    if not despues:
        lineas.append("Sin acciones apuntadas todavía.")
    for h in sorted(despues, key=lambda h: (h["fecha"], h["created_at"])):
        lineas.append(f"- {plan.fecha_es(h['fecha'])} · {plan.TIPOS_EVENTO.get(h['tipo'], h['tipo'])}: "
                      f"{h['descripcion']} ({h.get('realizado_por') or '—'})"
                      + (f" · factura/parte {h['numero_factura']}" if h.get("numero_factura") else ""))
    return "\n".join(lineas) + "\n"


def boton_informe_averia(equipo: dict, evento: dict, clave: str) -> None:
    """Botón para descargar el informe (.md) de una avería."""
    try:
        texto = informe_averia(equipo, evento)
    except Exception as e:  # sin conexión o datos raros: no rompe la página
        registro.excepcion("Averías · informe", e)
        st.caption(f"No se ha podido preparar el informe: {e}")
        return
    st.download_button("📄 Informe de la avería", texto, file_name=f"averia-{equipo['nombre']}-{evento['fecha']}.md".replace(" ", "_"),
                       mime="text/markdown", key=clave, type="tertiary")


def ultima_averia(equipo_id: str) -> dict | None:
    return next((h for h in db.bitacora([equipo_id], 50) if h["tipo"] == "averia"), None)


def linea_revision(objeto: dict, es_servicio: bool = False) -> str:
    """Texto corto con la frecuencia y el estado de la próxima revisión."""
    frecuencia = objeto.get("frecuencia" if es_servicio else "revision_frecuencia")
    partes = [plan.FRECUENCIAS_REVISION.get(frecuencia, "Sin frecuencia")]
    if objeto.get("ultima_revision"):
        partes.append(f"última: {plan.fecha_es(objeto['ultima_revision'])}")
    if objeto.get("proxima_revision"):
        icono, estado = plan.estado_tarea(date.fromisoformat(objeto["proxima_revision"]))
        partes.append(f"{icono} próxima: {plan.fecha_es(objeto['proxima_revision'])} ({estado.lower()})")
    elif frecuencia in plan.FRECUENCIAS:
        partes.append("⚪ falta la fecha de la próxima revisión")
    return " · ".join(partes)


def registrar_protocolo(protocolo_id: str, quien: str, dia: date, marcados: dict[str, bool], turno: str | None = None,
                        incidencias: str | None = None) -> None:
    """Guarda un protocolo hecho y firmado: el registro y qué pasos se hicieron."""
    hechos = sum(marcados.values())
    datos = {
        "protocolo_id": protocolo_id, "fecha": dia.isoformat(), "turno": (turno or "").strip() or None,
        "realizado_por": quien, "completado": hechos == len(marcados),
        "incidencias": (incidencias or "").strip() or None,
    }
    try:   # versión del procedimiento en vigor al firmar (si existe el historial de versiones)
        from core import versiones
        if (vigente := versiones.numero_vigente(protocolo_id)) is not None:
            datos["version"] = vigente
    except Exception:
        pass
    try:
        registro = db.table("protocolo_registros").insert(datos).execute().data[0]
    except Exception:
        if "version" not in datos:
            raise
        datos.pop("version")   # falta la columna `version` (supabase/versiones.sql): se registra sin ella
        registro = db.table("protocolo_registros").insert(datos).execute().data[0]
    if marcados:
        db.table("protocolo_registro_pasos").insert(
            [{"registro_id": registro["id"], "paso_id": i, "hecho": v} for i, v in marcados.items()]).execute()
    # Si alguien le había encargado este procedimiento por Rumbo, queda hecho solo (nunca rompe el registro)
    try:
        from core import rumbo
        rumbo.completar_procedimiento(sesion.actual(), protocolo_id)
    except Exception:
        pass


# ── Revisión paso a paso: a quien la tenga se le quita «Todo bien» y marca cada tarea ──
TODOS = "*"


def obligados_paso_a_paso(trabajador_id: str) -> set[str]:
    """Protocolos que esta persona tiene que revisar tarea por tarea (TODOS = todos). Vacío si ninguno."""
    try:
        filas = db.table("paso_a_paso").select("protocolo_id,hasta").eq("trabajador_id", trabajador_id)             .eq("activo", True).execute().data
    except Exception:  # falta supabase/paso_a_paso.sql: todo sigue como siempre
        return set()
    hoy = date.today().isoformat()
    return {f["protocolo_id"] or TODOS for f in filas if not f.get("hasta") or f["hasta"] >= hoy}


def va_paso_a_paso(protocolo_id: str, obligados: set[str]) -> bool:
    return TODOS in obligados or protocolo_id in obligados


def registro_rapido(protocolo: dict, pasos_de_hoy: list[dict], clave: str, width="stretch", tipo="secondary") -> bool:
    """Un toque: registra todas las tareas de hoy como hechas, firmadas por quien ha entrado con su PIN."""
    if st.button("✅ Todo bien", key=clave, width=width, type=tipo):
        registrar_protocolo(protocolo["id"], sesion.nombre(), date.today(), {p["id"]: True for p in pasos_de_hoy})
        return True
    return False
