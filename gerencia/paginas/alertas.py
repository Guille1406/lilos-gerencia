"""Alertas de mantenimiento: qué toca, qué va atrasado y quién responde."""
from datetime import date

import streamlit as st

from core import acciones, avisos, db, ia, plan, sesion

local_id = st.session_state.local_id
st.title("🔔 Alertas de mantenimiento")

horizonte = st.segmented_control("Planificación", list(plan.HORIZONTES), default="Esta semana") or "Esta semana"
limite = plan.limite_horizonte(horizonte)

equipos = {e["id"]: e for e in db.equipos(local_id)}
tareas = db.tareas(list(equipos))
hoy = date.today()
pendientes = [t for t in tareas if date.fromisoformat(t["proxima_fecha"]) <= limite]
atrasadas = [t for t in pendientes if date.fromisoformat(t["proxima_fecha"]) < hoy]
escaladas = [t for t in atrasadas if (hoy - date.fromisoformat(t["proxima_fecha"])).days > plan.DIAS_ESCALADO]
averiados = [e for e in equipos.values() if e["estado"] in ("averiado", "en_reparacion")]

# Revisiones periódicas de equipos (técnico) y servicios (friorista, plagas, extintores…)
servicios = db.servicios(local_id)
revisables = [("🧊", e, False) for e in equipos.values() if e["estado"] != "baja"] + [("🧯", s, True) for s in servicios]
revisiones = sorted([r for r in revisables if r[1].get("proxima_revision")
                     and date.fromisoformat(r[1]["proxima_revision"]) <= limite],
                    key=lambda r: r[1]["proxima_revision"])
sin_fecha = [r[1]["nombre"] for r in revisables if not r[1].get("proxima_revision")
             and r[1].get("frecuencia" if r[2] else "revision_frecuencia") in plan.FRECUENCIAS]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(f"Tareas · {horizonte.lower()}", len(pendientes))
c2.metric("Atrasadas", len(atrasadas))
c3.metric("Escaladas a dirección", len(escaladas))
c4.metric(f"Revisiones · {horizonte.lower()}", len(revisiones))
c5.metric("Equipos averiados", len(averiados))

# Responsables: gerente del local y, como segunda línea, dirección
personal = db.trabajadores()
gerentes = [t["name"] for t in personal if t.get("rol") == "gerente" and sesion.pertenece(t, local_id)]
directivos = [t["name"] for t in personal if t.get("rol") == "directivo"]
st.caption(f"Responsable: **{', '.join(gerentes) or 'gerente sin asignar'}** · "
           f"Segunda línea: **{', '.join(directivos) or 'dirección sin asignar'}**")

# Resumen de la IA: cómo está el local y qué hacer primero
if ia.disponible():
    clave = f"resumen-{local_id}-{horizonte}"
    if st.button("✨ Resumen para el gerente", help="Claude resume la situación y te dice por dónde empezar"):
        local = next((l["nombre"] for l in db.locales() if l["id"] == local_id), "el local")
        try:
            with st.spinner("Preparando el resumen…"):
                st.session_state[clave] = ia.resumen_gerente(local, horizonte, pendientes, atrasadas, escaladas,
                                                             averiados, equipos)
        except ia.ErrorIA as e:
            st.error(str(e))
    if resumen := st.session_state.get(clave):
        st.info(resumen, icon="✨")

st.subheader("Tareas")
if not pendientes:
    st.success(f"Nada pendiente {horizonte.lower()}. ✅")
for tarea in pendientes:
    equipo = equipos[tarea["equipo_id"]]
    icono, estado = plan.estado_tarea(date.fromisoformat(tarea["proxima_fecha"]))
    with st.container(border=True):
        a, b, c = st.columns([5, 3, 2], vertical_alignment="center")
        a.markdown(f"{icono} **{tarea['tarea']}** · {equipo['nombre']}  \n"
                   f"<small>{equipo['tipo']} · {equipo.get('zona') or 'sin zona'} · {tarea['frecuencia']}</small>",
                   unsafe_allow_html=True)
        b.markdown(f"{plan.fecha_es(tarea['proxima_fecha'])}  \n<small>{estado}</small>", unsafe_allow_html=True)
        if c.toggle("Hecho", key=f"hecho-{tarea['id']}"):
            if acciones.formulario_evento(equipo, tarea, clave=f"form-{tarea['id']}"):
                st.toast("Guardado en la bitácora. Próxima fecha actualizada.")
                st.rerun()

st.subheader("Revisiones de equipos y servicios")
if not revisiones:
    st.success(f"Ninguna revisión {horizonte.lower()}. ✅")
proveedores = {p["id"]: p for p in db.proveedores()}
for icono_tipo, objeto, es_servicio in revisiones:
    icono, estado = plan.estado_tarea(date.fromisoformat(objeto["proxima_revision"]))
    prov = proveedores.get(objeto.get("proveedor_id"))
    with st.container(border=True):
        a, b, c = st.columns([5, 3, 2], vertical_alignment="center")
        detalle = objeto.get("detalle" if es_servicio else "revision_detalle") or \
            plan.FRECUENCIAS_REVISION.get(objeto.get("frecuencia" if es_servicio else "revision_frecuencia"), "")
        a.markdown(f"{icono} {icono_tipo} **{objeto['nombre']}**  \n<small>{detalle}"
                   + (f" · 📞 {prov['nombre']} {prov.get('telefono') or ''}" if prov else "") + "</small>",
                   unsafe_allow_html=True)
        b.markdown(f"{plan.fecha_es(objeto['proxima_revision'])}  \n<small>{estado}</small>", unsafe_allow_html=True)
        if c.toggle("Hecha", key=f"rev-{objeto['id']}"):
            if acciones.formulario_evento(objeto, clave=f"form-rev-{objeto['id']}", es_servicio=es_servicio):
                st.toast("Revisión guardada. Próxima fecha actualizada.")
                st.rerun()
if sin_fecha:
    st.caption(f"⚪ Sin fecha de próxima revisión (complétala en su ficha): {', '.join(sin_fecha)}")

with st.expander("📧 Avisos por email a ops@lilobrunch.com"):
    st.caption("Solo llega un email cuando se vence una fecha de mantenimiento (tarea del plan o revisión de un "
               "equipo o servicio). Si a los 7 días sigue sin hacerse, llega otro de escalado a dirección. "
               "La comprobación se hace sola cada mañana.")
    if not avisos.configurado():
        st.warning("Para enviar emails falta configurar SMTP_USUARIO y SMTP_CLAVE.")
    if st.button("Ver lo que está vencido ahora"):
        st.session_state.vencidos = avisos.recopilar(todos=True)
    if (vencidos := st.session_state.get("vencidos")) is not None:
        if not vencidos:
            st.success("No hay nada vencido. ✅")
        else:
            asunto, _, cuerpo_html = avisos.componer(vencidos)
            st.markdown(f"**{asunto}**")
            st.html(cuerpo_html)
            if avisos.configurado() and st.button("📨 Enviar este aviso ahora"):
                try:
                    st.success(f"Enviado a {', '.join(avisos.enviar(*avisos.componer(vencidos)))}")
                except Exception as e:  # credenciales, red… se muestra tal cual
                    st.error(f"No se ha podido enviar: {e}")

if averiados:
    st.subheader("Equipos averiados")
    for equipo in averiados:
        st.markdown(f"{plan.ESTADOS_EQUIPO[equipo['estado']]} · **{equipo['nombre']}** "
                    f"({equipo['tipo']}) · técnico: {equipo.get('servicio_tecnico') or '—'} "
                    f"{equipo.get('contacto_tecnico') or ''}")
        evento = acciones.ultima_averia(equipo["id"])
        if evento:
            acciones.boton_informe_averia(equipo, evento, clave=f"informe-{equipo['id']}")
