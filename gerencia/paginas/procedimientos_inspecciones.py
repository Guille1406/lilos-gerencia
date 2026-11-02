"""Procedimientos e inspecciones: en una sola página, lo que se hace y se registra (POE, rutinas e inspecciones).
Editar los procedimientos y las plantillas está en páginas ocultas a las que lleva «✏️ Editar».
El equipo no ve esta página, salvo para hacer una inspección que le han encargado por Rumbo (solo esa parte)."""
import streamlit as st

from core import inspecciones_ui, procedimientos, sesion

SECCIONES = ["Procedimientos", "Inspecciones"]

if not sesion.puede("gerente"):   # equipo con una inspección encargada: solo «Mis inspecciones encargadas»
    inspecciones_ui.mostrar()
    st.stop()

st.title("📋 Procedimientos e inspecciones")

# A qué parte se va: «Ver tareas» (Hoy) y «Hacerlo» (Rumbo) dejan elegido el procedimiento o la inspección;
# «← Volver» de los editores deja dicha la parte.
ir_a = st.session_state.pop("pi_ir_a", None)
if st.session_state.get("protocolo_elegido"):
    st.session_state["pi-seccion"] = "Procedimientos"
elif st.session_state.get("insp_elegir"):
    st.session_state["pi-seccion"] = "Inspecciones"
elif ir_a:
    st.session_state["pi-seccion"] = ir_a
st.session_state.setdefault("pi-seccion", "Procedimientos")
seccion = st.segmented_control("Sección", SECCIONES, required=True, key="pi-seccion", label_visibility="collapsed")

if seccion == "Procedimientos":
    procedimientos.pagina()
else:
    inspecciones_ui.mostrar()
