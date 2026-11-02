"""Proveedores y empresas técnicas (comunes a todos los locales)."""
import streamlit as st

from core import db, tabla

st.title("📇 Proveedores")
st.caption("Empresas técnicas y proveedores de todos los locales: maquinaria, frío, plagas, extintores, productos de "
           "limpieza… Se asignan a cada equipo, servicio y producto. Añade filas al final; para borrar, "
           "selecciona la fila y pulsa la papelera.")

tabla.editar("proveedores", db.proveedores(), {
    "nombre": st.column_config.TextColumn("Nombre", required=True),
    "servicio": st.column_config.TextColumn("Qué hace"),
    "contacto": st.column_config.TextColumn("Contacto"),
    "telefono": st.column_config.TextColumn("Teléfono"),
    "email": st.column_config.TextColumn("Email"),
    "documentacion": st.column_config.TextColumn("Documentación", help="CIF, nº ROESB, contrato…"),
    "notas": st.column_config.TextColumn("Notas"),
}, clave="proveedores", obligatorias=("nombre",))
