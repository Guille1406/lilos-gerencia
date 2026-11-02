"""🖨️ Dispositivos: los ordenadores con la etiquetadora y la cola de impresión. Solo el admin.

Cada ordenador que abre la etiquetadora aparece aquí solo (manda un latido cada 30 s). El admin le pone nombre,
le asigna el local y marca como PRINCIPAL el que tiene la DYMO: ese imprime lo que se mande desde tablets,
móviles y 🏷️ Imprimir etiqueta.
"""
from datetime import datetime, timezone

import streamlit as st

from core import db, impresion, sesion

if not sesion.puede("admin"):
    st.stop()
st.title("🖨️ Dispositivos")
st.caption("Ordenadores con la etiquetadora. El **principal** de cada local imprime su cola de etiquetas.")

locales = {l["id"]: l["nombre"] for l in db.locales()}
try:
    equipos = impresion.dispositivos()
except Exception:
    st.error("Falta ejecutar supabase/impresion.sql en Supabase.")
    st.stop()


def _hace(fecha: str | None) -> str:
    if not fecha:
        return "nunca"
    segundos = int((datetime.now(timezone.utc) - datetime.fromisoformat(fecha)).total_seconds())
    if segundos < 90:
        return f"hace {max(segundos, 0)} s"
    if segundos < 3600:
        return f"hace {segundos // 60} min"
    if segundos < 86400:
        return f"hace {segundos // 3600} h"
    return datetime.fromisoformat(fecha).astimezone(impresion.ZONA).strftime("%d/%m/%Y %H:%M")


if not equipos:
    st.info("Todavía no se ha registrado ningún ordenador. Aparecen solos al abrir la etiquetadora (Etiquetas.bat) "
            "con la versión nueva y el .env de Supabase.")
else:
    st.dataframe(
        [{"": "🟢" if impresion.en_linea(d) else "⚪", "Nombre": d["nombre"],
          "Local": locales.get(d.get("local_id"), "— sin local —"), "Principal": bool(d.get("principal")),
          "Impresora": d.get("impresora") or "", "Versión": d.get("version") or "",
          "Último latido": _hace(d.get("ultimo_latido")), "Activo": d.get("activo", True)}
         for d in sorted(equipos, key=lambda d: (d.get("local_id") or "~", not d.get("principal"), d["nombre"]))],
        hide_index=True, width="stretch")

    # Locales sin principal en línea
    for lid, nombre in locales.items():
        principales = [d for d in equipos if d.get("local_id") == lid and d.get("principal") and d.get("activo", True)]
        if not principales:
            st.caption(f"⚠️ {nombre}: sin impresora principal.")
        elif not any(impresion.en_linea(d) for d in principales):
            st.caption(f"⚪ {nombre}: la impresora principal no está en línea.")

    # ── Editar un dispositivo ──
    elegido = st.selectbox("Editar", equipos, index=None, placeholder="Elige un ordenador",
                           format_func=lambda d: f"{d['nombre']} · {locales.get(d.get('local_id'), 'sin local')}")
    if elegido:
        with st.form(f"dispositivo-{elegido['id']}"):
            nombre = st.text_input("Nombre", value=elegido["nombre"], max_chars=120,
                                   help="P. ej. «PC cocina Enric Granados»")
            opciones = [None, *locales]
            local = st.selectbox("Local", opciones, format_func=lambda i: locales.get(i, "— sin local —"),
                                 index=opciones.index(elegido.get("local_id")) if elegido.get("local_id") in opciones else 0)
            principal = st.toggle("Principal: imprime la cola de su local", value=bool(elegido.get("principal")))
            activo = st.toggle("Activo", value=elegido.get("activo", True))
            st.caption(f"Id: `{elegido['id']}` (en `dispositivo.local.json` de ese ordenador)")
            if st.form_submit_button("Guardar", type="primary"):
                if principal and not local:
                    st.error("Para ser principal tiene que tener local.")
                elif not nombre.strip():
                    st.error("Ponle un nombre.")
                else:
                    impresion.actualizar_dispositivo(elegido["id"], {"nombre": nombre.strip(), "local_id": local,
                                                                     "principal": principal, "activo": activo})
                    st.toast("Guardado. El ordenador lo nota en menos de 30 s.", icon="✅")
                    st.rerun()

# ── Cola de impresión ──
st.subheader("Cola de impresión")
f1, f2 = st.columns(2)
filtro_local = f1.selectbox("Local", [None, *locales], format_func=lambda i: locales.get(i, "Todos"), key="cola_local")
solo_pendientes = f2.toggle("Solo pendientes y errores", value=True, key="cola_pendientes")
try:
    cola = impresion.trabajos(filtro_local, ["pendiente", "imprimiendo", "error"] if solo_pendientes else None, limite=100)
except Exception as e:
    st.error(f"No se puede leer la cola: {e}")
    st.stop()
if not cola:
    st.success("No hay nada pendiente. ✅" if solo_pendientes else "La cola está vacía.")
    st.stop()

nombres = {d["id"]: d["nombre"] for d in equipos}
tabla = st.dataframe(
    [{"Hora": datetime.fromisoformat(t["created_at"]).astimezone(impresion.ZONA).strftime("%d/%m %H:%M"),
      "Local": locales.get(t["local_id"], t["local_id"]), "Etiqueta": impresion.resumen(t),
      "Estado": impresion.ESTADOS.get(t["estado"], t["estado"]), "Intentos": t.get("intentos") or 0,
      "Pedida por": f"{t.get('solicitado_por') or '—'} ({t.get('origen')})",
      "Impresora": nombres.get(t.get("dispositivo_id"), ""), "Error": t.get("error") or ""} for t in cola],
    hide_index=True, width="stretch", on_select="rerun", selection_mode="multi-row", key="cola_tabla")

seleccion = [cola[i] for i in tabla.selection.rows if i < len(cola)]
b1, b2 = st.columns(2)
reintentables = [t for t in seleccion if t["estado"] in ("error", "cancelada")]
cancelables = [t for t in seleccion if t["estado"] in ("pendiente", "error")]
if b1.button(f"🔁 Reintentar ({len(reintentables)})", disabled=not reintentables, width="stretch"):
    for t in reintentables:
        impresion.reintentar(t["id"])
    st.rerun()
if b2.button(f"✖️ Cancelar ({len(cancelables)})", disabled=not cancelables, width="stretch"):
    for t in cancelables:
        impresion.cancelar(t["id"])
    st.rerun()
st.caption("Selecciona filas para reintentarlas o cancelarlas. Un trabajo que se quedó «Imprimiendo» porque se "
           "cerró la app pasa solo a «Error» al volver a abrirla.")
