"""Equipos del local: ficha técnica, plan de mantenimiento e historial."""
from datetime import date

import streamlit as st

from core import acciones, db, ia, plan, qr

local_id = st.session_state.local_id
equipos = db.equipos(local_id)
por_id = {e["id"]: e for e in equipos}
proveedores = {p["id"]: p for p in db.proveedores()}


def fecha(valor):
    return date.fromisoformat(valor) if valor else None


# ── Vista rápida al escanear el QR pegado en el equipo: lo mínimo para apuntar algo o corregir la ficha ──
if desde_qr := st.query_params.get("equipo"):
    filas = db.table("equipos").select("*").eq("id", desde_qr).execute().data
    if not filas:
        st.error("Este código QR no corresponde a ningún equipo.")
        st.stop()
    equipo = filas[0]
    st.title(f"🧊 {equipo['nombre']}")
    st.markdown(f"{plan.ESTADOS_EQUIPO[equipo['estado']]} · {equipo['tipo']}"
                + (f" · {equipo['marca']} {equipo.get('modelo') or ''}" if equipo.get("marca") else ""))
    st.markdown(f"🔧 {acciones.linea_revision(equipo)}")
    if prov := proveedores.get(equipo.get("proveedor_id")):
        st.markdown(f"📞 **{prov['nombre']}** · {prov.get('telefono') or 'sin teléfono'}")
    st.subheader("Apuntar algo")
    if acciones.formulario_evento(equipo, clave=f"qr-evento-{desde_qr}"):
        st.toast("Guardado en la bitácora")
        st.rerun()
    with st.expander("✏️ Corregir los datos de la placa"):
        with st.form(f"qr-ficha-{desde_qr}"):
            c1, c2 = st.columns(2)
            marca_qr = c1.text_input("Marca", equipo.get("marca") or "")
            modelo_qr = c2.text_input("Modelo", equipo.get("modelo") or "")
            serie_qr = c1.text_input("Nº de serie", equipo.get("numero_serie") or "")
            capacidad_qr = c2.text_input("Capacidad / potencia", equipo.get("capacidad") or "")
            if st.form_submit_button("Guardar", type="primary"):
                db.table("equipos").update({
                    "marca": marca_qr.strip() or None, "modelo": modelo_qr.strip() or None,
                    "numero_serie": serie_qr.strip() or None, "capacidad": capacidad_qr.strip() or None,
                }).eq("id", desde_qr).execute()
                st.toast("Ficha actualizada")
                st.rerun()
    ultimos = db.bitacora([desde_qr], limite=3)
    if ultimos:
        st.caption("Últimos apuntes: " + " · ".join(
            f"{plan.fecha_es(h['fecha'])} {plan.TIPOS_EVENTO.get(h['tipo'], h['tipo']).lower()}: {h['descripcion']}"
            for h in ultimos))
    if st.button("Ver todos los equipos"):
        st.query_params.clear()
        st.rerun()
    st.stop()

st.title("🧊 Equipos y mobiliario")
tab_lista, tab_ficha, tab_qr = st.tabs(["📋 Lista", "📄 Ficha detallada", "🏷️ Etiquetas QR"])

# ── Lista compacta de todos los equipos ──
with tab_lista:
    if not equipos:
        st.info("Todavía no hay equipos. Añádelos en «Ficha detallada».")
    else:
        def proxima(e):
            if not e.get("proxima_revision"):
                return "⚪ sin fecha" if e.get("revision_frecuencia") in plan.FRECUENCIAS else \
                    plan.FRECUENCIAS_REVISION.get(e.get("revision_frecuencia"), "—")
            icono, _ = plan.estado_tarea(date.fromisoformat(e["proxima_revision"]))
            return f"{icono} {plan.fecha_es(e['proxima_revision'])}"
        st.dataframe([{
            "": plan.ESTADOS_EQUIPO[e["estado"]].split()[0], "Equipo": e["nombre"], "Tipo": e["tipo"],
            "Zona": e.get("zona") or "", "Marca / modelo": " ".join(x for x in (e.get("marca"), e.get("modelo")) if x),
            "Próxima revisión": proxima(e),
            "Empresa": (proveedores.get(e.get("proveedor_id")) or {}).get("nombre", ""),
        } for e in sorted(equipos, key=lambda e: e.get("proxima_revision") or "9999")],
            hide_index=True, width="stretch")

# ── Hoja de códigos QR para pegar en cada equipo ──
with tab_qr:
    st.caption("Imprime la hoja y pega cada código en su equipo. Al escanearlo con el móvil se abre la ficha de ese "
               "equipo para apuntar una avería o un mantenimiento, o corregir los datos de la placa.")
    base = (db.config("APP_URL") or "http://localhost:8501").rstrip("/")
    if "localhost" in base:
        st.warning("La app aún no está publicada: los códigos solo funcionarán en este ordenador. Cuando esté online, "
                   "pon su dirección en APP_URL y vuelve a imprimirlos.")
    if equipos:
        local_nombre = next((l["nombre"] for l in db.locales() if l["id"] == local_id), "")
        hoja = qr.hoja_qr(equipos, base, local_nombre)
        st.download_button("⬇️ Descargar hoja para imprimir", hoja, file_name=f"QR-equipos-{local_id}.html",
                           mime="text/html", type="primary")
        st.html(hoja)

with tab_ficha:
    NUEVO = "__nuevo__"
    opciones = [NUEVO] + [e["id"] for e in equipos]
    elegido = st.selectbox(
        "Equipo", opciones,
        format_func=lambda i: "➕ Añadir equipo nuevo" if i == NUEVO else
        f"{plan.ESTADOS_EQUIPO[por_id[i]['estado']].split()[0]} {por_id[i]['nombre']} · {por_id[i]['tipo']}",
        index=1 if equipos else 0,
    )
    equipo = por_id.get(elegido, {})


    # ── Ficha técnica ──
    with st.expander("📄 Ficha técnica", expanded=elegido == NUEVO):
        # La IA lee la placa de características y rellena la ficha; se revisa y se guarda a mano
        ficha = equipo
        if ia.disponible():
            foto = st.file_uploader("📷 Foto de la placa de características", type=["jpg", "jpeg", "png", "webp"],
                                    key=f"placa-{elegido}", help="Claude lee la placa y rellena la ficha por ti")
            if foto and st.button("✨ Rellenar la ficha con IA", key=f"leer-{elegido}"):
                try:
                    with st.spinner("Leyendo la placa…"):
                        st.session_state[f"placa-ia-{elegido}"] = ia.leer_placa(foto.getvalue())
                except ia.ErrorIA as e:
                    st.error(str(e))
            if leido := st.session_state.get(f"placa-ia-{elegido}"):
                ficha = {**equipo, **{k: v for k, v in leido.items() if v is not None}}
                st.success("Ficha rellenada a partir de la foto. Revísala y pulsa «Guardar ficha».")
        with st.form("ficha"):
            c1, c2, c3 = st.columns(3)
            nombre = c1.text_input("Nombre *", ficha.get("nombre", ""), placeholder="Nevera 2 barra")
            tipos = plan.TIPOS_EQUIPO
            tipo = c2.selectbox("Tipo *", tipos, index=tipos.index(ficha["tipo"]) if ficha.get("tipo") in tipos else 0)
            zona = c3.text_input("Zona", ficha.get("zona") or "", placeholder="Cocina, barra, almacén…")
            c1, c2, c3 = st.columns(3)
            marca = c1.text_input("Marca", ficha.get("marca") or "")
            modelo = c2.text_input("Modelo", ficha.get("modelo") or "")
            serie = c3.text_input("Nº de serie", ficha.get("numero_serie") or "")
            c1, c2, c3 = st.columns(3)
            compra = c1.date_input("Fecha de compra", fecha(ficha.get("fecha_compra")), format="DD/MM/YYYY")
            garantia = c2.date_input("Garantía hasta", fecha(ficha.get("garantia_hasta")), format="DD/MM/YYYY")
            estados = list(plan.ESTADOS_EQUIPO)
            estado = c3.selectbox("Estado", estados, format_func=plan.ESTADOS_EQUIPO.get,
                                  index=estados.index(ficha.get("estado", "operativo")))
            c1, c2 = st.columns(2)
            ids_prov = [None] + list(proveedores)
            proveedor_id = c1.selectbox(
                "Empresa técnica", ids_prov, format_func=lambda i: "—" if i is None else
                f"{proveedores[i]['nombre']} · {proveedores[i].get('servicio') or ''}",
                index=ids_prov.index(ficha.get("proveedor_id")) if ficha.get("proveedor_id") in ids_prov else 0,
                help="Se dan de alta en la página Proveedores")
            capacidad = c2.text_input("Capacidad / potencia", ficha.get("capacidad") or "", placeholder="500 L, 1400 W…")
            c1, c2 = st.columns(2)
            tecnico = c1.text_input("Otro servicio técnico", ficha.get("servicio_tecnico") or "",
                                    help="Solo si no está en Proveedores")
            contacto = c2.text_input("Contacto del técnico", ficha.get("contacto_tecnico") or "",
                                     placeholder="Teléfono o email")
            st.markdown("**Revisión periódica**")
            c1, c2, c3, c4 = st.columns(4)
            frecuencias = [None] + list(plan.FRECUENCIAS_REVISION)
            rev_frecuencia = c1.selectbox(
                "Frecuencia", frecuencias, format_func=lambda f: "—" if f is None else plan.FRECUENCIAS_REVISION[f],
                index=frecuencias.index(ficha.get("revision_frecuencia")) if ficha.get("revision_frecuencia") in frecuencias else 0)
            rev_detalle = c2.text_input("Detalle", ficha.get("revision_detalle") or "", placeholder="Anual (mayo) + trimestral")
            rev_ultima = c3.date_input("Última revisión", fecha(ficha.get("ultima_revision")), format="DD/MM/YYYY")
            rev_proxima = c4.date_input("Próxima revisión", fecha(ficha.get("proxima_revision")), format="DD/MM/YYYY",
                                        help="Si la dejas vacía, se calcula con la última revisión y la frecuencia")
            c1, c2 = st.columns(2)
            tmin = c1.number_input("Temperatura mínima (°C)", value=ficha.get("temp_min"), step=0.5,
                                   help="Solo equipos de frío o calor")
            tmax = c2.number_input("Temperatura máxima (°C)", value=ficha.get("temp_max"), step=0.5)
            notas = st.text_area("Notas", ficha.get("notas") or "")

            if st.form_submit_button("Guardar ficha", type="primary"):
                if not nombre.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    datos = {
                        "local_id": local_id, "nombre": nombre.strip(), "tipo": tipo, "zona": zona.strip() or None,
                        "marca": marca.strip() or None, "modelo": modelo.strip() or None,
                        "numero_serie": serie.strip() or None,
                        "fecha_compra": compra.isoformat() if compra else None,
                        "garantia_hasta": garantia.isoformat() if garantia else None,
                        "estado": estado, "servicio_tecnico": tecnico.strip() or None,
                        "contacto_tecnico": contacto.strip() or None,
                        "temp_min": tmin, "temp_max": tmax, "notas": notas.strip() or None,
                        "proveedor_id": proveedor_id, "capacidad": capacidad.strip() or None,
                        "revision_frecuencia": rev_frecuencia, "revision_detalle": rev_detalle.strip() or None,
                        "ultima_revision": rev_ultima.isoformat() if rev_ultima else None,
                    }
                    proxima = rev_proxima or plan.proxima_revision(rev_ultima, rev_frecuencia)
                    datos["proxima_revision"] = proxima.isoformat() if proxima else None
                    if elegido == NUEVO:
                        db.table("equipos").insert(datos).execute()
                        st.toast(f"Equipo «{nombre}» añadido")
                    else:
                        db.table("equipos").update(datos).eq("id", elegido).execute()
                        st.toast("Ficha guardada")
                    st.session_state.pop(f"placa-ia-{elegido}", None)
                    st.rerun()

    if elegido == NUEVO:
        st.stop()

    st.markdown(f"🔧 **Revisión:** {acciones.linea_revision(equipo)}")
    if equipo.get("revision_detalle"):
        st.caption(equipo["revision_detalle"])
    if (prov := proveedores.get(equipo.get("proveedor_id"))):
        st.markdown(f"📞 **{prov['nombre']}** · {prov.get('servicio') or ''} · {prov.get('telefono') or 'sin teléfono'}"
                    + (f" · {prov['contacto']}" if prov.get("contacto") else ""))

    if equipo.get("garantia_hasta") and fecha(equipo["garantia_hasta"]) >= date.today():
        st.info(f"🛡️ En garantía hasta el {plan.fecha_es(equipo['garantia_hasta'])}: antes de pagar una reparación, "
                "llama al servicio técnico.")

    # ── Plan de mantenimiento ──
    st.subheader("🗓️ Plan de mantenimiento")
    tareas = db.tareas([elegido])
    for tarea in tareas:
        icono, estado_txt = plan.estado_tarea(fecha(tarea["proxima_fecha"]))
        a, b, c = st.columns([5, 3, 1], vertical_alignment="center")
        a.markdown(f"{icono} **{tarea['tarea']}** · {tarea['frecuencia']}")
        b.markdown(f"{plan.fecha_es(tarea['proxima_fecha'])} · <small>{estado_txt}</small>", unsafe_allow_html=True)
        if c.button("🗑️", key=f"borrar-{tarea['id']}", help="Quitar del plan (el historial se conserva)"):
            db.table("tareas_mantenimiento").update({"activa": False}).eq("id", tarea["id"]).execute()
            st.rerun()
    if not tareas:
        st.caption("Este equipo no tiene tareas planificadas.")

    with st.form("nueva_tarea", clear_on_submit=True):
        c1, c2, c3 = st.columns([4, 2, 2])
        texto = c1.text_input("Nueva tarea", placeholder="Limpiar condensador")
        frecuencia = c2.selectbox("Frecuencia", list(plan.FRECUENCIAS), index=2)
        primera = c3.date_input("Primera vez", date.today(), format="DD/MM/YYYY")
        if st.form_submit_button("Añadir al plan"):
            if texto.strip():
                db.table("tareas_mantenimiento").insert({
                    "equipo_id": elegido, "tarea": texto.strip(), "frecuencia": frecuencia,
                    "proxima_fecha": primera.isoformat(),
                }).execute()
                st.rerun()
            else:
                st.error("Escribe la tarea.")

    # Plan sugerido por la IA: se eligen las tareas que se quieren añadir
    if ia.disponible():
        clave_plan = f"plan-ia-{elegido}"
        if st.button("✨ Sugerir plan con IA", help="Claude propone las tareas de mantenimiento que le faltan a este equipo"):
            try:
                with st.spinner("Preparando el plan…"):
                    st.session_state[clave_plan] = ia.sugerir_plan(equipo, tareas)
            except ia.ErrorIA as e:
                st.error(str(e))
        if sugeridas := st.session_state.get(clave_plan):
            with st.form(f"form-{clave_plan}"):
                st.markdown("**Plan sugerido por la IA** · marca las tareas que quieras añadir")
                marcadas = []
                for i, s in enumerate(sugeridas):
                    marcadas.append(st.checkbox(f"{s['tarea']} · {s['frecuencia']}", value=True, key=f"{clave_plan}-{i}"))
                    st.caption(s["motivo"])
                c1, c2 = st.columns(2)
                if c1.form_submit_button("Añadir al plan", type="primary"):
                    filas = [{"equipo_id": elegido, "tarea": s["tarea"], "frecuencia": s["frecuencia"],
                              "proxima_fecha": date.today().isoformat()}
                             for s, marcada in zip(sugeridas, marcadas) if marcada]
                    if filas:
                        db.table("tareas_mantenimiento").insert(filas).execute()
                    del st.session_state[clave_plan]
                    st.rerun()
                if c2.form_submit_button("Descartar"):
                    del st.session_state[clave_plan]
                    st.rerun()

    # ── Historial ──
    st.subheader("📒 Historial")
    with st.expander("Apuntar algo en la bitácora de este equipo"):
        if acciones.formulario_evento(equipo, clave="evento-equipo"):
            st.toast("Guardado en la bitácora")
            st.rerun()

    historial = db.bitacora([elegido])

    # Ayuda de la IA ante una avería: qué hacer ya, comprobaciones y si llamar al técnico
    if ia.disponible():
        with st.expander("🩺 ¿Falla algo? Pide ayuda a la IA",
                         expanded=equipo.get("estado") in ("averiado", "en_reparacion")):
            sintoma = st.text_area("¿Qué le pasa?", key=f"sintoma-{elegido}",
                                   placeholder="No enfría bien, la puerta no cierra, hace un ruido raro…")
            if st.button("Pedir ayuda", key=f"ayuda-{elegido}"):
                if not sintoma.strip():
                    st.error("Cuenta qué le pasa al equipo.")
                else:
                    try:
                        with st.spinner("Pensando…"):
                            st.session_state[f"ayuda-ia-{elegido}"] = ia.ayuda_averia(equipo, sintoma.strip(), historial)
                    except ia.ErrorIA as e:
                        st.error(str(e))
            if ayuda := st.session_state.get(f"ayuda-ia-{elegido}"):
                st.markdown(ayuda)
                st.caption("Orientación de la IA: ante la duda, llama al servicio técnico.")

    if historial:
        st.dataframe(
            [{"Fecha": plan.fecha_es(h["fecha"]), "Tipo": plan.TIPOS_EVENTO.get(h["tipo"], h["tipo"]),
              "Qué se hizo": h["descripcion"], "Quién": h.get("realizado_por") or "—",
              "Coste (€)": h.get("coste")} for h in historial],
            hide_index=True, width="stretch",
        )
        gasto = sum(float(h["coste"] or 0) for h in historial)
        st.caption(f"Gasto total registrado en este equipo: **{gasto:,.2f} €**")
    else:
        st.caption("Todavía no hay nada apuntado.")
