"""Comunicados al equipo con confirmación de lectura (acuse de recibo del plan APPCC, cambios de protocolo…)."""
from datetime import datetime

import streamlit as st

from core import db

local_id = st.session_state.local_id
st.title("📣 Comunicados")
st.caption("Avisos al equipo que cada persona confirma con «He leído y entendido» desde la pantalla Hoy. Sirve como "
           "acuse de recibo: queda quién lo leyó y cuándo.")

try:
    comunicados = db.comunicados(local_id, solo_activos=False)
except Exception:
    st.error("Faltan las tablas de comunicados: ejecuta supabase/comunicados.sql en Supabase.")
    st.stop()
nombres = db.trabajadores_local(local_id)

with st.expander("➕ Nuevo comunicado", expanded=not comunicados):
    with st.form("nuevo-comunicado", clear_on_submit=True):
        titulo = st.text_input("Título *", placeholder="Nuevo plan de limpieza v1.2: léelo y confírmalo")
        texto = st.text_area("Mensaje", placeholder="Qué cambia y qué tiene que hacer cada uno…")
        enlace = st.text_input("Enlace a un documento, foto o vídeo (opcional)")
        c1, c2 = st.columns(2)
        para_todos = c1.checkbox("Para todos los locales")
        autor = c2.selectbox("Lo envía", nombres, index=None, placeholder="Tu nombre") if nombres else \
            c2.text_input("Lo envía")
        if st.form_submit_button("Publicar", type="primary"):
            if not titulo.strip():
                st.error("Pon un título.")
            else:
                db.table("comunicados").insert({
                    "local_id": None if para_todos else local_id, "titulo": titulo.strip(),
                    "texto": texto.strip() or None, "enlace": enlace.strip() or None, "creado_por": autor or None,
                }).execute()
                st.toast("Comunicado publicado: aparecerá en Hoy hasta que todos lo lean")
                st.rerun()

lecturas = db.lecturas([c["id"] for c in comunicados])
for c in comunicados:
    leidos = {l["trabajador"]: l["leido_en"] for l in lecturas if l["comunicado_id"] == c["id"]}
    faltan = [n for n in nombres if n not in leidos]
    with st.container(border=True):
        a, b = st.columns([5, 2], vertical_alignment="center")
        a.markdown(f"**{c['titulo']}**" + ("" if c["activo"] else " · _archivado_")
                   + f"  \n<small>{datetime.fromisoformat(c['created_at']).astimezone().strftime('%d/%m/%Y')}"
                   + (f" · {c['creado_por']}" if c.get("creado_por") else "")
                   + (" · todos los locales" if not c.get("local_id") else "") + "</small>", unsafe_allow_html=True)
        b.markdown(f"**{len(leidos)}/{len(leidos) + len(faltan)}** leído")
        with st.expander("Detalle"):
            if c.get("texto"):
                st.markdown(c["texto"])
            st.markdown("✅ " + (", ".join(f"{n} ({datetime.fromisoformat(t).astimezone().strftime('%d/%m %H:%M')})"
                                          for n, t in leidos.items()) or "nadie todavía"))
            if faltan:
                st.markdown("⏳ Falta: " + ", ".join(faltan))
            if c["activo"] and st.button("Archivar", key=f"archivar-{c['id']}"):
                db.table("comunicados").update({"activo": False}).eq("id", c["id"]).execute()
                st.rerun()
