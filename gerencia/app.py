"""LilOS · Gerencia. Ejecutar con:  streamlit run gerencia/app.py"""
import json
from pathlib import Path

import streamlit as st

from core import db, ia, registro, sesion

VERSION = json.loads((Path(__file__).resolve().parents[1] / "package.json").read_text(encoding="utf-8"))["version"]

st.set_page_config(page_title="LilOS · Gerencia", page_icon="🛠️", layout="wide")
registro.instalar()   # los avisos y errores de la app van al 🧾 Registro de errores del admin

# Acceso: si se configura APP_PASSWORD (obligatorio al publicar la app), se pide al entrar
password = db.config("APP_PASSWORD")
invitado = db.config("INVITADO_PASSWORD")   # opcional: entra en modo invitado, que lo ve todo y no guarda nada
if password and not st.session_state.get("autenticado"):
    st.title("LilOS · Gerencia")
    with st.form("login"):
        intento = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if intento == password:
                st.session_state.autenticado = True
                st.rerun()
            if invitado and intento == invitado:   # perfil de solo lectura para compartir (muro del máster)
                st.session_state.autenticado = True
                sesion.entrar_invitado()
                st.rerun()
            st.error("Contraseña incorrecta")
    st.stop()

# Quién usa la app: PIN personal (como en Square). Sin entrar no se ve nada.
sesion.refrescar()
sesion.pantalla_acceso()
sesion.marcar_actividad()
persona = sesion.actual()

# Local con el que se trabaja (lo usan todas las páginas)
with st.sidebar:
    if db.solo_lectura():
        st.markdown("👀 **Invitado** · solo lectura")
        st.caption("Puedes probarlo todo: nada de lo que hagas se guarda.")
    else:
        st.markdown(f"👤 **{persona['name']}** · {sesion.ROLES.get(persona.get('rol'), '')}")
    if db.modo_demo():
        st.caption("🧪 Demostración: datos inventados. Lo que cambies se pierde al cerrar la pestaña.")
    try:
        locales = db.locales()
    except Exception:  # la tabla aún no existe en Supabase
        locales = []
    if not locales:
        st.error("No hay locales. Ejecuta supabase/mantenimiento.sql en Supabase.")
        st.stop()
    opciones = {l["id"]: l["nombre"] for l in locales}
    # Dirección y admin ven todos los locales; gerentes y equipo, solo sus sedes (una: fija; varias: selector)
    mis_sedes = [] if sesion.puede("directivo") else [s for s in sesion.sedes(persona) if s in opciones]
    if len(mis_sedes) == 1:
        st.session_state.local_id = mis_sedes[0]
        st.caption(f"📍 {opciones.get(mis_sedes[0], '')}")
    else:
        posibles = mis_sedes or list(opciones)
        actual = st.session_state.get("local_id")
        st.session_state.local_id = st.selectbox(
            "Local", posibles, format_func=opciones.get,
            index=posibles.index(actual) if actual in posibles else 0,
        )

# Páginas según el rol: el equipo ve solo lo del día; gerencia y dirección, todo lo de su nivel
gerente = sesion.puede("gerente")
inspecciones_equipo = False   # el equipo ve Procedimientos e inspecciones solo si le han encargado una inspección por Rumbo
if not gerente:
    try:
        from core import rumbo
        inspecciones_equipo = bool(rumbo.inspecciones_encargadas(persona))
    except Exception:  # falta supabase/rumbo.sql: sin encargos, sin la página
        pass
secciones = {
    # Ejecución: lo que se hace en el día a día. Las rutinas se hacen desde Hoy; editar está en páginas ocultas
    # (se abren con «✏️ Editar» en Procedimientos e inspecciones y vuelven con «← Volver»)
    "Ejecución": [
        st.Page("paginas/hoy.py", title="Hoy", icon="📅", default=True),
        st.Page("paginas/rumbo.py", title="Rumbo", icon="🧭"),
        st.Page("paginas/imprimir.py", title="Imprimir etiqueta", icon="🏷️"),   # a la DYMO del local (cola)
        *([st.Page("paginas/comunicados.py", title="Comunicados", icon="📣"),
           st.Page("paginas/alertas.py", title="Alertas", icon="🔔")] if gerente else []),
        *([st.Page("paginas/procedimientos_inspecciones.py", title="Procedimientos e inspecciones", icon="📋")]
          if gerente or inspecciones_equipo else []),
        *([st.Page("paginas/editar_procedimientos.py", title="Editar procedimientos", icon="✏️", visibility="hidden"),
           st.Page("paginas/plantillas_inspeccion.py", title="Plantillas de inspección", icon="🧩",
                   visibility="hidden")] if gerente else []),
    ],
}
# Base de datos: las páginas que solo guardan datos de referencia (equipos, productos, servicios, proveedores…)
secciones["Base de datos"] = [
    st.Page("paginas/equipos.py", title="Equipos y mobiliario", icon="🧊"),
    *([st.Page("paginas/limpieza.py", title="Productos de limpieza", icon="🧴")] if gerente else []),
    *([st.Page("paginas/servicios.py", title="Servicios", icon="🧯")] if gerente else []),
    *([st.Page("paginas/proveedores.py", title="Proveedores", icon="📇")] if gerente else []),
    st.Page("paginas/bitacora.py", title="Bitácora", icon="📒"),
]
if sesion.puede("admin"):   # los perfiles y los PIN los gestiona solo el admin
    secciones["Administración"] = [
        st.Page("paginas/perfiles.py", title="Perfiles", icon="👥"),
        st.Page("paginas/errores.py", title="Registro de errores", icon="🧾"),
        st.Page("paginas/dispositivos.py", title="Dispositivos", icon="🖨️"),
    ]
secciones[""] = [st.Page("paginas/asistente.py", title="Asistente", icon="✨")]   # solo, al final del menú
pagina = st.navigation(secciones)

# Abajo del menú: cerrar sesión (y el bloqueo automático por inactividad)
with st.sidebar:
    st.caption(("✨ Asistente de IA activo" if ia.disponible() else "Asistente de IA sin configurar")
               + f" · versión {'.'.join(VERSION.split('.')[:2])}")
    if st.button("🚪 Cerrar sesión", width="stretch"):
        sesion.salir()
        st.rerun()
    sesion.vigilar_inactividad(sesion.minutos_bloqueo())

registro.ejecutar_pagina(pagina)   # si una pantalla falla, queda apuntado para el admin
