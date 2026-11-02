"""Servicios de mantenimiento del local: frío, plagas (DDD), extintores, climatización, electricidad, fontanería…"""
from datetime import date

import streamlit as st

from core import acciones, db, plan

local_id = st.session_state.local_id
st.title("🧯 Servicios de mantenimiento")
st.caption("Empresas externas que revisan el local: friorista, control de plagas, extintores, aire acondicionado… "
           "Cada servicio tiene su última y próxima revisión, y sus visitas quedan en la bitácora.")

servicios = db.servicios(local_id, solo_activos=False)
proveedores = {p["id"]: p for p in db.proveedores()}
por_id = {s["id"]: s for s in servicios}


def fecha(valor):
    return date.fromisoformat(valor) if valor else None


# ── Resumen ──
for s in sorted(servicios, key=lambda s: (not s["activo"], s.get("proxima_revision") or "9999")):
    prov = proveedores.get(s.get("proveedor_id"))
    with st.container(border=True):
        a, b = st.columns([3, 2], vertical_alignment="center")
        a.markdown(f"**{plan.CATEGORIAS_SERVICIO.get(s['categoria'], s['categoria'])} · {s['nombre']}**"
                   + ("" if s["activo"] else " · _dado de baja_") + f"  \n{acciones.linea_revision(s, es_servicio=True)}")
        if s.get("detalle"):
            a.caption(s["detalle"])
        b.markdown(f"📞 **{prov['nombre']}** · {prov.get('telefono') or 'sin teléfono'}" if prov
                   else "📞 _Empresa sin asignar_")
        if s.get("documentacion"):
            b.caption(f"📄 {s['documentacion']}")
if not servicios:
    st.info("Todavía no hay servicios en este local. Añade el primero abajo.")

st.divider()
NUEVO = "__nuevo__"
elegido = st.selectbox("Servicio", [NUEVO] + list(por_id), index=1 if servicios else 0,
                       format_func=lambda i: "➕ Añadir servicio nuevo" if i == NUEVO else por_id[i]["nombre"])
servicio = por_id.get(elegido, {})

tab_ficha, tab_visita, tab_historial = st.tabs(["📄 Ficha", "✅ Registrar visita", "📒 Historial"])

with tab_ficha:
    with st.form(f"servicio-{elegido}"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre *", servicio.get("nombre", ""), placeholder="Control de plagas (DDD)")
        categorias = list(plan.CATEGORIAS_SERVICIO)
        categoria = c2.selectbox("Categoría", categorias, format_func=plan.CATEGORIAS_SERVICIO.get,
                                 index=categorias.index(servicio.get("categoria", "otro")))
        ids_prov = [None] + list(proveedores)
        proveedor_id = st.selectbox(
            "Empresa", ids_prov, format_func=lambda i: "—" if i is None else
            f"{proveedores[i]['nombre']} · {proveedores[i].get('servicio') or ''}",
            index=ids_prov.index(servicio.get("proveedor_id")) if servicio.get("proveedor_id") in ids_prov else 0,
            help="Se dan de alta en la página Proveedores")
        c1, c2, c3, c4 = st.columns(4)
        frecuencias = [None] + list(plan.FRECUENCIAS_REVISION)
        frecuencia = c1.selectbox(
            "Frecuencia", frecuencias, format_func=lambda f: "—" if f is None else plan.FRECUENCIAS_REVISION[f],
            index=frecuencias.index(servicio.get("frecuencia")) if servicio.get("frecuencia") in frecuencias else 0)
        detalle = c2.text_input("Detalle", servicio.get("detalle") or "", placeholder="Trimestral + a demanda")
        ultima = c3.date_input("Última revisión", fecha(servicio.get("ultima_revision")), format="DD/MM/YYYY")
        proxima = c4.date_input("Próxima revisión", fecha(servicio.get("proxima_revision")), format="DD/MM/YYYY",
                                help="Si la dejas vacía, se calcula con la última revisión y la frecuencia")
        documentacion = st.text_input("Documentación", servicio.get("documentacion") or "",
                                      placeholder="Contrato, certificados, nº ROESB…")
        notas = st.text_area("Notas", servicio.get("notas") or "")
        activo = st.checkbox("Activo", value=servicio.get("activo", True))
        if st.form_submit_button("Guardar", type="primary"):
            if not nombre.strip():
                st.error("El nombre es obligatorio.")
            else:
                proxima = proxima or plan.proxima_revision(ultima, frecuencia)
                datos = {
                    "local_id": local_id, "nombre": nombre.strip(), "categoria": categoria,
                    "proveedor_id": proveedor_id, "frecuencia": frecuencia, "detalle": detalle.strip() or None,
                    "ultima_revision": ultima.isoformat() if ultima else None,
                    "proxima_revision": proxima.isoformat() if proxima else None,
                    "documentacion": documentacion.strip() or None, "notas": notas.strip() or None,
                    "activo": activo,
                }
                if elegido == NUEVO:
                    db.table("servicios").insert(datos).execute()
                else:
                    db.table("servicios").update(datos).eq("id", elegido).execute()
                st.toast("Servicio guardado")
                st.rerun()

if elegido == NUEVO:
    st.stop()

with tab_visita:
    if acciones.formulario_evento(servicio, clave=f"visita-{elegido}", es_servicio=True):
        st.toast("Visita guardada en la bitácora")
        st.rerun()

with tab_historial:
    historial = db.bitacora_servicios([elegido])
    if historial:
        st.dataframe(
            [{"Fecha": plan.fecha_es(h["fecha"]), "Tipo": plan.TIPOS_EVENTO.get(h["tipo"], h["tipo"]),
              "Qué se hizo": h["descripcion"], "Quién": h.get("realizado_por") or "—",
              "Nº factura / parte": h.get("numero_factura") or "—", "Coste (€)": h.get("coste")} for h in historial],
            hide_index=True, width="stretch",
        )
    else:
        st.caption("Todavía no hay visitas apuntadas.")
