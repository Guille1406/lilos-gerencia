"""🏷️ Imprimir etiqueta: manda una etiqueta a la DYMO del local desde cualquier sitio (también el móvil).

La imprime el ordenador PRINCIPAL del local (el que tiene la DYMO y la etiquetadora abierta). La caducidad se
calcula igual que en la etiquetadora y el responsable es quien ha entrado con su PIN.
"""
from datetime import datetime

import streamlit as st

from core import db, impresion, sesion

st.title("🏷️ Imprimir etiqueta")

# ── Local: dirección y admin, cualquiera; el resto, sus sedes (trabajadores.locales ∪ local_id) ──
locales = {l["id"]: l["nombre"] for l in db.locales()}
local_id = st.session_state.get("local_id")
opciones = impresion.sedes(sesion.sedes(sesion.actual()), list(locales), todas=sesion.puede("directivo"))
if len(opciones) > 1:
    local_id = st.selectbox("Local", opciones, format_func=locales.get,
                            index=opciones.index(local_id) if local_id in opciones else 0, key="imprimir_local")
elif opciones:
    local_id = opciones[0]
if not local_id:
    st.warning("No tienes local asignado. Pide al admin que te lo asigne en 👥 Perfiles.")
    st.stop()

try:
    principales = [d for d in impresion.dispositivos(local_id) if d.get("principal") and d.get("activo", True)]
    catalogo = impresion.productos()
except Exception:
    st.error("Falta ejecutar supabase/impresion.sql en Supabase.")
    st.stop()

if not principales:
    st.warning(f"{locales.get(local_id, local_id)} no tiene ninguna impresora principal. El admin la asigna en "
               "🖨️ Dispositivos. Las etiquetas quedarán en cola hasta entonces.")
elif not any(impresion.en_linea(d) for d in principales):
    st.warning("La impresora del local no está en línea (el ordenador de la DYMO está apagado o sin la etiquetadora "
               "abierta). Las etiquetas quedarán en cola y saldrán cuando se encienda.")
else:
    st.caption("🟢 Imprime: " + ", ".join(f"{d['nombre']} · {d.get('impresora') or 'DYMO'}"
                                         for d in principales if impresion.en_linea(d)))

if not catalogo:
    st.info("No hay productos en el catálogo. Se crean en la etiquetadora (📋 Catálogo).")
    st.stop()

# ── Formulario ──
producto = st.selectbox(
    "Producto", catalogo, index=None, placeholder="Busca el producto…", key="imprimir_producto",
    format_func=lambda p: f"{'🌱 ' if p.get('vegan') else ''}{p['name']} · {impresion.texto_dias(p.get('exp_hours') or 48)}")

c1, c2 = st.columns(2)
copias = c1.number_input("Copias", min_value=1, max_value=impresion.MAX_COPIAS, value=1, step=1, key="imprimir_copias")
lote = c2.text_input("Lote (opcional)", max_chars=30, key="imprimir_lote", placeholder="Sin lote")
forzada = st.selectbox("Caducidad", [None, *impresion.DIAS_FORZADOS], key="imprimir_forzada",
                       format_func=lambda d: "La del producto" if d is None
                       else impresion.texto_dias(impresion.dias_a_horas(d)) + " (forzada)")
es_ahora = st.toggle("Elaborado ahora", value=True, key="imprimir_ahora")
if es_ahora:
    preparacion = impresion.ahora()
else:
    f1, f2 = st.columns(2)
    dia = f1.date_input("Día de elaboración", value=impresion.ahora().date(), format="DD/MM/YYYY", key="imprimir_dia")
    hora = f2.time_input("Hora", value=impresion.ahora().time().replace(second=0, microsecond=0), step=60,
                         key="imprimir_hora")
    preparacion = datetime.combine(dia, hora).replace(tzinfo=impresion.ZONA)

if producto:
    horas = impresion.dias_a_horas(forzada) if forzada is not None else float(producto.get("exp_hours") or 48)
    cad = impresion.caducidad(preparacion, horas)
    with st.container(border=True):
        color = impresion.CATEGORIAS.get(producto.get("category"), "#A8A29E")
        st.markdown(f"<div style='border-right:8px solid {color};padding-right:.5rem'>"
                    f"<b>{producto['name']}</b><br><small>{producto.get('category') or 'General'} · "
                    f"{(producto.get('storage') or 'refrigerado').upper()} · Alérgenos: {producto.get('allergens') or 'Ninguno'}</small>"
                    "</div>", unsafe_allow_html=True)
        st.markdown(f"Elaborado **{impresion.formato(preparacion)}** · Caduca **{impresion.formato(cad)}** · "
                    f"Por **{sesion.nombre()}**")

if st.button("🖨️ Imprimir", type="primary", width="stretch", disabled=not producto):
    preparacion = impresion.ahora() if es_ahora else preparacion   # «ahora» = el momento de pulsar
    datos = impresion.datos_trabajo(producto, preparacion, sesion.nombre(),
                                    horas=impresion.dias_a_horas(forzada) if forzada is not None else None,
                                    lote=lote, copias=int(copias))
    try:
        impresion.encolar(local_id, datos, sesion.nombre(), origen="gerencia")
        st.toast(f"Enviada a la impresora: {producto['name']}", icon="🏷️")
    except Exception as e:
        st.error(f"No se ha podido enviar: {e}")


# ── Últimas etiquetas del local (se actualiza sola) ──
@st.fragment(run_every=4)
def ultimas(local: str) -> None:
    st.subheader("Últimas etiquetas")
    try:
        filas = impresion.trabajos(local, limite=15)
    except Exception as e:
        st.caption(f"No se puede leer la cola: {e}")
        return
    if not filas:
        st.caption("Todavía no se ha mandado ninguna desde aquí.")
        return
    st.dataframe(
        [{"Hora": datetime.fromisoformat(t["created_at"]).astimezone(impresion.ZONA).strftime("%d/%m %H:%M"),
          "Etiqueta": impresion.resumen(t), "Estado": impresion.ESTADOS.get(t["estado"], t["estado"]),
          "Pedida por": t.get("solicitado_por") or "", "Detalle": t.get("error") or ""} for t in filas],
        hide_index=True, width="stretch")


ultimas(local_id)
