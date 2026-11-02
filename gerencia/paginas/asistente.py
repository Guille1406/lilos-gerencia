"""Asistente del gerente: chat que consulta la intranet de LilOS (y, si hace falta, internet)."""
import streamlit as st

from core import ia

local_id = st.session_state.local_id
st.title("✨ Asistente")

if not ia.disponible():
    st.warning("El asistente necesita una clave de IA (IA_API_KEY o GEMINI_API_KEY) en .streamlit/secrets.toml.")
    st.stop()

st.caption("Pregunta lo que quieras sobre tus locales: mantenimiento, averías y gastos, catálogo y caducidades, "
           "etiquetas impresas, personal… Consulta los datos reales de la intranet y, si hace falta, internet.")

chat = st.session_state.setdefault("chat_asistente", [])

SUGERENCIAS = [
    "¿Qué tengo pendiente esta semana y por dónde empiezo?",
    "¿Qué equipos han dado más problemas y cuánto nos han costado?",
    "¿Qué se ha etiquetado esta semana y quién lo hizo?",
    "¿Cuántos días puede durar una mayonesa casera según la normativa?",
]

pregunta = st.chat_input("Escribe tu pregunta…")
if not chat and not pregunta:
    st.markdown("**Prueba con:**")
    for i, sugerencia in enumerate(SUGERENCIAS):
        if st.button(sugerencia, key=f"sugerencia-{i}"):
            pregunta = sugerencia

for mensaje in chat:
    with st.chat_message(mensaje["role"]):
        st.markdown(mensaje["content"])

if pregunta:
    chat.append({"role": "user", "content": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)
    with st.chat_message("assistant"):
        with st.status("Pensando…", expanded=False) as estado:
            try:
                respuesta = ia.asistente(chat[-20:], local_id, al_consultar=lambda paso: estado.write(f"{paso}…"))
                estado.update(label="Listo", state="complete")
            except ia.ErrorIA as e:
                respuesta = f"⚠️ {e}"
                estado.update(label="No se ha podido responder", state="error")
        st.markdown(respuesta)
    chat.append({"role": "assistant", "content": respuesta})

if chat and st.button("🗑️ Empezar de nuevo"):
    st.session_state.chat_asistente = []
    st.rerun()
