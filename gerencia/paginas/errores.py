"""Registro de errores: todo lo que falla o avisa en las dos apps, en una lista tipo terminal. Solo el admin."""
from datetime import date, datetime, timezone

import streamlit as st

from core import db, sesion

if not sesion.puede("admin"):
    st.stop()
st.title("🧾 Registro de errores")
st.caption("Aquí se acumulan los errores y avisos de la app de gerencia y de la etiquetadora, lo más nuevo primero.")

MARCAS = {"error": "🔴 error", "aviso": "🟠 aviso", "info": "🔵 info"}
LIMITE = 1000

try:
    filas = db.table("registro_errores").select("*").order("created_at", desc=True).limit(LIMITE).execute().data
except Exception:
    st.error("Falta ejecutar supabase/registro_errores.sql en Supabase.")
    st.stop()


def _fecha(f: dict) -> datetime:
    return datetime.fromisoformat(f["created_at"]).astimezone()


hoy, ahora = date.today(), datetime.now().astimezone()
sin_resolver = [f for f in filas if not f["resuelto"]]
c1, c2, c3 = st.columns(3)
c1.metric("Sin resolver hoy", sum(1 for f in sin_resolver if _fecha(f).date() == hoy))
c2.metric("Sin resolver · 7 días", sum(1 for f in sin_resolver if (ahora - _fecha(f)).days < 7))
c3.metric("Sin resolver · total", len(sin_resolver))

# ── Filtros ──
f1, f2, f3, f4 = st.columns([1, 1, 1.4, 1.2], vertical_alignment="bottom")
app = f1.selectbox("App", ["Todas", "gerencia", "etiquetas"])
nivel = f2.selectbox("Nivel", ["Todos", "error", "aviso", "info"])
texto = f3.text_input("Buscar", placeholder="origen, mensaje, persona…")
solo_pendientes = f4.toggle("Solo sin resolver", value=True)

visibles = [f for f in filas
            if (app == "Todas" or f["app"] == app) and (nivel == "Todos" or f["nivel"] == nivel)
            and (not solo_pendientes or not f["resuelto"])
            and (not texto or texto.lower() in " ".join(str(f.get(k) or "") for k in ("origen", "mensaje", "persona", "detalle")).lower())]


def _linea(f: dict) -> str:
    return (f"{_fecha(f):%d/%m %H:%M} · {f['nivel']} · {f['app']} · {f.get('origen') or '—'} · {f['mensaje']}"
            f" · {f.get('persona') or '—'}" + (" · [resuelto]" if f["resuelto"] else ""))


b1, b2 = st.columns([1, 1])
b1.download_button("⬇️ Descargar .txt", "\n".join(_linea(f) for f in visibles) or "Sin registros.",
                   file_name=f"registro-errores-{hoy:%Y%m%d}.txt", mime="text/plain", disabled=not visibles,
                   width="stretch")
if b2.button(f"✅ Marcar todo lo visible como resuelto ({sum(1 for f in visibles if not f['resuelto'])})",
             disabled=not any(not f["resuelto"] for f in visibles), width="stretch"):
    try:
        db.table("registro_errores").update({"resuelto": True, "resuelto_por": sesion.nombre(),
                                             "resuelto_en": datetime.now(timezone.utc).isoformat()}) \
            .in_("id", [f["id"] for f in visibles if not f["resuelto"]]).execute()
        st.rerun()
    except Exception as e:
        st.error(f"No se han podido marcar: {e}")

if not visibles:
    st.success("No hay nada que mostrar con estos filtros. ✅")
    st.stop()

# ── Lista tipo terminal ──
st.caption(f"{len(visibles)} apuntes" + (f" (se leen los últimos {LIMITE})" if len(filas) >= LIMITE else "")
           + " · pulsa una fila para ver el detalle")
tabla = st.dataframe(
    [{"Hora": f"{_fecha(f):%d/%m %H:%M}", "Nivel": MARCAS.get(f["nivel"], f["nivel"]), "App": f["app"],
      "Origen": f.get("origen") or "", "Mensaje": f["mensaje"], "Persona": f.get("persona") or "",
      "Resuelto": f["resuelto"]} for f in visibles],
    hide_index=True, width="stretch", height=min(560, 40 + 35 * len(visibles)),
    on_select="rerun", selection_mode="single-row", key="registro_tabla",
    column_config={"Resuelto": st.column_config.CheckboxColumn(width="small"),
                   "Mensaje": st.column_config.TextColumn(width="large")})

# ── Detalle ──
seleccion = tabla.selection.rows
if seleccion and seleccion[0] < len(visibles):
    f = visibles[seleccion[0]]
    with st.container(border=True):
        st.markdown(f"**{MARCAS.get(f['nivel'], f['nivel'])}** · {f['app']} · {f.get('origen') or '—'} · "
                    f"{_fecha(f):%d/%m/%Y %H:%M:%S}")
        st.markdown(f"{f['mensaje']}")
        st.caption(f"Persona: {f.get('persona') or '—'} · Local: {f.get('local_id') or '—'}")
        if f.get("detalle"):
            st.code(f["detalle"], language=None, wrap_lines=True)
        if f["resuelto"]:
            st.caption(f"✅ Resuelto por {f.get('resuelto_por') or '—'}"
                       + (f" el {datetime.fromisoformat(f['resuelto_en']).astimezone():%d/%m %H:%M}" if f.get("resuelto_en") else ""))
        elif st.button("✅ Marcar resuelto", key=f"resolver-{f['id']}"):
            try:
                db.table("registro_errores").update({"resuelto": True, "resuelto_por": sesion.nombre(),
                                                     "resuelto_en": datetime.now(timezone.utc).isoformat()}) \
                    .eq("id", f["id"]).execute()
                st.rerun()
            except Exception as e:
                st.error(f"No se ha podido marcar: {e}")
