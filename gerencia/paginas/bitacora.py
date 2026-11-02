"""Bitácora del local (registro de intervenciones): apuntar cualquier evento y ver el historial de equipos y servicios."""
import streamlit as st

from core import acciones, db, plan

local_id = st.session_state.local_id
st.title("📒 Bitácora")
st.caption("Registro de intervenciones del APPCC: mantenimientos, revisiones, averías, reparaciones y visitas de "
           "empresas. Anota el nº de factura o parte y guarda el papel en la carpeta del plan.")

equipos = {e["id"]: e for e in db.equipos(local_id)}
servicios = {s["id"]: s for s in db.servicios(local_id)}
if not equipos and not servicios:
    st.info("Primero añade los equipos o servicios del local en sus páginas.")
    st.stop()

st.subheader("Apuntar una intervención")
opciones = [("equipo", i) for i in equipos] + [("servicio", i) for i in servicios]
elegido = st.selectbox(
    "Equipo o servicio", opciones,
    format_func=lambda o: f"🧊 {equipos[o[1]]['nombre']} · {equipos[o[1]]['tipo']}" if o[0] == "equipo"
    else f"🧯 {servicios[o[1]]['nombre']}")
es_servicio = elegido[0] == "servicio"
objeto = (servicios if es_servicio else equipos)[elegido[1]]
tarea = None
if not es_servicio and (tareas := db.tareas([elegido[1]])):
    tarea = st.selectbox("¿Cumple una tarea del plan?", [None] + tareas,
                         format_func=lambda t: "No" if t is None else f"{t['tarea']} ({t['frecuencia']})")
if acciones.formulario_evento(objeto, tarea, clave=f"evento-{elegido[1]}-{tarea['id'] if tarea else 'libre'}",
                              es_servicio=es_servicio):
    st.toast("Guardado en la bitácora")
    st.rerun()

st.subheader("Historial del local")
historial = sorted(db.bitacora(list(equipos)) + db.bitacora_servicios(list(servicios)),
                   key=lambda h: (h["fecha"], h["created_at"]), reverse=True)
tipos = st.multiselect("Filtrar por tipo", list(plan.TIPOS_EVENTO), format_func=plan.TIPOS_EVENTO.get)
filas = [h for h in historial if not tipos or h["tipo"] in tipos]
if filas:
    st.dataframe(
        [{"Fecha": plan.fecha_es(h["fecha"]),
          "Equipo / servicio": equipos[h["equipo_id"]]["nombre"] if h.get("equipo_id") in equipos
          else servicios.get(h.get("servicio_id"), {}).get("nombre", "—"),
          "Tipo": plan.TIPOS_EVENTO.get(h["tipo"], h["tipo"]), "Qué se hizo": h["descripcion"],
          "Quién": h.get("realizado_por") or "—", "Nº factura / parte": h.get("numero_factura") or "—",
          "Coste (€)": h.get("coste")} for h in filas],
        hide_index=True, width="stretch",
    )
    st.caption(f"Gasto en lo mostrado: **{sum(float(h['coste'] or 0) for h in filas):,.2f} €**")
else:
    st.caption("No hay eventos apuntados.")

averias = [h for h in historial if h["tipo"] == "averia" and h.get("equipo_id") in equipos]
if averias:
    st.subheader("Informe de una avería")
    elegida = st.selectbox(
        "Avería", averias, key="informe-averia", format_func=lambda h:
        f"{plan.fecha_es(h['fecha'])} · {equipos[h['equipo_id']]['nombre']} · {h['descripcion'][:60]}")
    acciones.boton_informe_averia(equipos[elegida["equipo_id"]], elegida, clave="informe-averia-boton")
