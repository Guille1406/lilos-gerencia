"""Editor tipo hoja de cálculo que guarda en Supabase (altas, cambios y bajas)."""
import pandas as pd
import streamlit as st

from core import db


def _valor(v):
    """Pasa los valores del editor (tipos de pandas/numpy, NaN) a tipos normales que entiende Supabase."""
    if hasattr(v, "item"):
        v = v.item()
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def editar(tabla: str, filas: list[dict], columnas: dict, fijos: dict | None = None, clave: str = "editor",
           obligatorias: tuple = (), validar=None, al_guardar=None, archivar: bool = False) -> None:
    """columnas: {campo: st.column_config…}. fijos: valores que se añaden a cada fila nueva (p. ej. local_id).
    Las filas se añaden al final, se editan en su celda y se borran seleccionándolas y pulsando la papelera.
    validar: función sin argumentos que se llama antes de escribir si hay cambios; si devuelve un texto, se muestra
    como error y no se guarda nada. al_guardar: función sin argumentos que se llama tras escribir los cambios.
    archivar: en vez de borrar las filas quitadas, las marca activo = false (para no perder el histórico)."""
    campos = list(columnas)
    df = pd.DataFrame([{c: f.get(c) for c in ["id"] + campos} for f in filas], columns=["id"] + campos)
    editado = st.data_editor(df, column_config={"id": None, **columnas}, num_rows="dynamic", hide_index=True,
                             width="stretch", key=clave)
    if not st.button("💾 Guardar cambios", key=f"{clave}-guardar", type="primary"):
        return
    originales = {f["id"]: f for f in filas}
    vistos = set()
    errores = []
    altas, cambios = [], []
    for fila in editado.to_dict("records"):
        datos = {c: _valor(v) for c, v in fila.items() if c != "id"}
        if not any(v is not None for v in datos.values()):
            continue
        if faltan := [c for c in obligatorias if not datos.get(c)]:
            errores.append(f"Falta {', '.join(faltan)} en una fila")
            continue
        ident = fila.get("id")
        if isinstance(ident, str) and ident in originales:
            vistos.add(ident)
            if any(datos.get(c) != originales[ident].get(c) for c in campos):
                cambios.append((ident, datos))
        else:
            altas.append(datos)
    bajas = set(originales) - vistos
    hay_cambios = bool(altas or cambios or bajas)
    if hay_cambios and validar and (problema := validar()):
        st.error(problema)
        return
    for ident, datos in cambios:
        db.table(tabla).update(datos).eq("id", ident).execute()
    for datos in altas:
        db.table(tabla).insert({**(fijos or {}), **datos}).execute()
    for ident in bajas:
        if archivar:
            db.table(tabla).update({"activo": False}).eq("id", ident).execute()
        else:
            db.table(tabla).delete().eq("id", ident).execute()
    st.cache_data.clear()
    if hay_cambios and al_guardar:
        al_guardar()
    if errores:
        st.error(" · ".join(errores))
    else:
        st.toast("Cambios guardados")
        st.rerun()
