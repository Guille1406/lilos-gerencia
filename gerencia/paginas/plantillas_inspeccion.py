"""Plantillas de inspección: ver las oficiales, duplicarlas, crear plantillas propias y editar sus preguntas.
Página oculta (no sale en el menú): se abre con «✏️ Editar plantillas» en Procedimientos e inspecciones y vuelve con
«← Volver». Hacer las inspecciones y consultar su historial está en esa misma página."""
import pandas as pd
import streamlit as st

from core import db, sesion, tabla
from core import inspecciones as insp
from core.procedimientos import PAGINA

local_id = st.session_state.local_id

if st.button("← Volver", key="plantillas-volver"):
    st.session_state.pi_ir_a = "Inspecciones"
    st.switch_page(PAGINA)

st.title("🧩 Plantillas de inspección")
st.caption("Las listas de preguntas con las que se hacen las inspecciones (sanidad, PRL, emergencias, calidad o "
           "propias). Las oficiales no se editan, pero se pueden duplicar y adaptar.")

try:
    plantillas = insp.plantillas(local_id, solo_activas=False)
except Exception:
    st.error(insp.FALTA_TABLA)
    st.stop()

# La primera vez se cargan solas las plantillas oficiales (sanidad, PRL, emergencias, calidad)
if not any(p.get("predefinida") for p in plantillas):
    try:
        if insp.cargar_oficiales(plantillas):
            plantillas = insp.plantillas(local_id, solo_activas=False)
    except Exception as e:
        st.warning(f"No se pudieron cargar las plantillas oficiales: {e}")

por_id = {p["id"]: p for p in plantillas}
locales = {l["id"]: l["nombre"] for l in db.locales()}


def _icono(tipo: str | None) -> str:
    return insp.TIPOS_PLANTILLA.get(tipo or "", "✏️ ").split()[0]


COLUMNAS = {
    "orden": st.column_config.NumberColumn("Orden", min_value=1, step=1, width="small"),
    "seccion": st.column_config.TextColumn("Sección", help="Agrupa las preguntas: Cocina, Almacén…"),
    "tipo": st.column_config.SelectboxColumn("Tipo", options=list(insp.TIPOS_PREGUNTA), required=True,
                                             format_func=insp.TIPOS_PREGUNTA.get, default="si_no",
                                             help="Texto: instrucción sin respuesta · Casilla: marcar · "
                                                  "Verdadero/Falso: Sí/No/N/A · Respuesta corta: escribir"),
    "enunciado": st.column_config.TextColumn("Pregunta", required=True, width="large"),
    "ayuda": st.column_config.TextColumn("Ayuda", help="Qué mirar o normativa de referencia"),
    "obligatoria": st.column_config.CheckboxColumn("Obligatoria", default=True),
    "critica": st.column_config.CheckboxColumn("Crítica", default=False,
                                               help="Un «No» aquí es una no conformidad crítica"),
}
NUEVA = "__nueva__"

cuenta = insp.cuenta_preguntas([p["id"] for p in plantillas])
st.dataframe([{
    "Plantilla": f"{_icono(p['tipo'])} {p['nombre']}", "Tipo": insp.TIPOS_PLANTILLA.get(p["tipo"], p["tipo"]),
    "Preguntas": cuenta.get(p["id"], 0), "Local": locales.get(p.get("local_id"), "Todos"),
    "Origen": "Oficial" if p.get("predefinida") else p.get("creado_por") or "—", "Activa": p["activo"],
} for p in sorted(plantillas, key=lambda p: (not p.get("predefinida"), p["nombre"].lower()))],
    hide_index=True, width="stretch")
if st.button("Cargar plantillas oficiales", help="Vuelve a crear las oficiales que falten. No duplica."):
    creadas = insp.cargar_oficiales()
    st.toast(f"{creadas} plantillas oficiales cargadas" if creadas else "Ya estaban todas")
    st.rerun()

if abrir := st.session_state.pop("insp_abrir", None):
    st.session_state["insp-plantilla"] = abrir
opciones = [p["id"] for p in sorted(plantillas, key=lambda p: (not p.get("predefinida"), p["nombre"].lower()))]
elegida = st.selectbox("Plantilla", opciones + [NUEVA], index=None, key="insp-plantilla",
                       placeholder="Elige una para verla, duplicarla o editarla",
                       format_func=lambda i: "➕ Crear plantilla nueva" if i == NUEVA else
                       f"{_icono(por_id[i]['tipo'])} {por_id[i]['nombre']}"
                       + ("" if por_id[i]["activo"] else " (inactiva)"))

if elegida == NUEVA:
    with st.form("insp-nueva-plantilla"):
        c1, c2 = st.columns([3, 2])
        nombre = c1.text_input("Nombre *", placeholder="Revisión de barra")
        tipos = [t for t in insp.TIPOS_PLANTILLA if t != "rutina"]
        tipo = c2.selectbox("Tipo", tipos, index=tipos.index("personalizada"),
                            format_func=insp.TIPOS_PLANTILLA.get)
        descripcion = st.text_area("Descripción", placeholder="Para qué sirve y cuándo se hace")
        todos_locales = st.checkbox("Para todos los locales") if sesion.puede("directivo") else False
        if st.form_submit_button("Crear y añadir preguntas", type="primary"):
            if not nombre.strip():
                st.error("Pon un nombre.")
            else:
                nueva = insp.crear_plantilla({
                    "nombre": nombre.strip(), "tipo": tipo, "descripcion": descripcion.strip() or None,
                    "local_id": None if todos_locales else local_id, "creado_por": sesion.nombre() or None,
                }, [{"orden": 1, "seccion": None, "tipo": "si_no", "enunciado": "Primera pregunta (cámbiala)",
                     "ayuda": None, "obligatoria": True, "critica": False, "puntua": True}])
                st.session_state.insp_abrir = nueva["id"]
                st.rerun()
elif elegida:
    p = por_id[elegida]
    filas = insp.preguntas(elegida)
    editable = not p.get("predefinida") and p["tipo"] != "rutina" \
        and (p.get("local_id") == local_id or sesion.puede("directivo"))
    if p.get("descripcion"):
        st.caption(p["descripcion"])
    if not editable:
        st.info("Plantilla oficial: no se edita, pero puedes duplicarla y adaptar la copia." if p.get("predefinida")
                else "Se crea y se pone al día sola con los pasos del protocolo." if p["tipo"] == "rutina"
                else "Es de todos los locales: la edita dirección. Puedes duplicarla para tu local.")
        st.dataframe([{"Sección": f.get("seccion") or "", "Tipo": insp.TIPOS_PREGUNTA.get(f["tipo"], f["tipo"]),
                       "Pregunta": f["enunciado"], "Crítica": "🔴" if f.get("critica") else "",
                       "Ayuda": f.get("ayuda") or ""} for f in filas], hide_index=True, width="stretch")
    else:
        with st.form(f"insp-datos-{elegida}"):
            c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
            nombre = c1.text_input("Nombre *", p["nombre"])
            activa = c2.checkbox("Activa", value=p["activo"])
            descripcion = st.text_area("Descripción", p.get("descripcion") or "")
            if st.form_submit_button("Guardar datos"):
                if not nombre.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    insp.actualizar_plantilla(elegida, {"nombre": nombre.strip(), "activo": activa,
                                                        "descripcion": descripcion.strip() or None})
                    st.toast("Plantilla guardada")
                    st.rerun()
        st.markdown("**Preguntas** · en orden; añade filas al final y, para borrar, selecciona la fila y pulsa "
                    "la papelera. 🔴 Crítica: un «No» deja la inspección como No conforme.")
        df = pd.DataFrame([{c: f.get(c) for c in ["id", *COLUMNAS]} for f in filas], columns=["id", *COLUMNAS])
        editado = st.data_editor(df, column_config={"id": None, **COLUMNAS}, num_rows="dynamic", hide_index=True,
                                 width="stretch", key=f"insp-preguntas-{elegida}")
        if st.button("💾 Guardar preguntas", type="primary", key=f"insp-guardar-preguntas-{elegida}"):
            limpias = [{c: tabla._valor(v) for c, v in fila.items()} for fila in editado.to_dict("records")]
            altas, cambios, bajas = insp.cambios_preguntas(filas, limpias)
            insp.guardar_preguntas(elegida, altas, cambios, bajas)
            st.toast(f"Preguntas guardadas · {len(altas)} nuevas, {len(cambios)} cambiadas, {len(bajas)} borradas")
            st.rerun()

    with st.form(f"insp-duplicar-{elegida}"):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        nombre_copia = c1.text_input("Duplicar como", f"{p['nombre']} (copia)")
        if c2.form_submit_button("📄 Duplicar", width="stretch") and nombre_copia.strip():
            copia = insp.duplicar(p, filas, nombre_copia.strip(), sesion.nombre() or None, local_id)
            st.session_state.insp_abrir = copia["id"]
            st.toast("Copia creada: ya puedes editarla")
            st.rerun()
