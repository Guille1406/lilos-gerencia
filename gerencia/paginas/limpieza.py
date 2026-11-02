"""Productos de limpieza y desinfección autorizados en el local (Anexo 1 del plan APPCC)."""
import streamlit as st

from core import db, tabla

local_id = st.session_state.local_id
st.title("🧴 Productos de limpieza")
st.caption("Productos autorizados del plan de limpieza y desinfección (Anexo 1). Los códigos (P1, P2…) son los que "
           "aparecen en los protocolos. Actualiza esta lista cada vez que cambie un producto o proveedor.")

productos = db.productos_limpieza(local_id)
proveedores = {p["id"]: p["nombre"] for p in db.proveedores()}

# Avisos de lo que falta para cerrar el anexo
sin_registro = [p["codigo"] for p in productos if not p.get("registro")]
sin_fichas = [p["codigo"] for p in productos if not (p.get("ficha_tecnica") and p.get("ficha_seguridad"))]
if sin_registro:
    st.warning(f"Sin nº de registro o identificador: **{', '.join(sin_registro)}**. Para desinfectantes y lejía es "
               "obligatorio (ver abajo cómo comprobarlo).")
if sin_fichas:
    st.info(f"Faltan fichas técnicas o de seguridad en la carpeta del plan: {', '.join(sin_fichas)}.")

tabla.editar("productos_limpieza", productos, {
    "codigo": st.column_config.TextColumn("Cód.", required=True, width="small"),
    "nombre": st.column_config.TextColumn("Producto", required=True),
    "marca": st.column_config.TextColumn("Marca"),
    "uso": st.column_config.TextColumn("Uso principal"),
    "dosis": st.column_config.TextColumn("Dosis / dilución"),
    "tiempo_contacto": st.column_config.TextColumn("T. contacto"),
    "registro": st.column_config.TextColumn("Nº registro / identificador"),
    "ficha_tecnica": st.column_config.CheckboxColumn("Ficha técnica"),
    "ficha_seguridad": st.column_config.CheckboxColumn("Ficha seguridad"),
    "proveedor_id": st.column_config.SelectboxColumn("Proveedor", options=list(proveedores),
                                                     format_func=lambda i: proveedores.get(i, "—")),
    "peligros": st.column_config.TextColumn("Peligros / notas"),
    "activo": st.column_config.CheckboxColumn("Activo", default=True),
}, fijos={"local_id": local_id}, clave=f"limpieza-{local_id}", obligatorias=("codigo", "nombre"))

with st.expander("Cómo comprobar el número de registro de un desinfectante"):
    st.markdown(
        "- **Formato antiguo español:** termina en **HA** (por ejemplo, 20-20/40-12345-HA).\n"
        "- **Formato actual de biocidas:** empieza por **ES/** o **EU-** (por ejemplo, ES/APP(NA)-2021-04-00123 o "
        "EU-0012345-0000).\n"
        "- Además, la etiqueta debe indicar uso en **industria alimentaria**, superficies en contacto con alimentos "
        "o **TP4**.\n\n"
        "Si no aparece ninguno de los dos datos, el producto no sirve como desinfectante de cocina y debe "
        "sustituirse. Emergencias: Instituto Nacional de Toxicología, **91 562 04 20**."
    )
