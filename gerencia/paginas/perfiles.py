"""Perfiles: quién es quién, su rol, su local y su PIN. Solo el admin: él crea a las personas y asigna los PIN."""
from datetime import datetime, timedelta

import streamlit as st

from core import db, sesion

if not sesion.puede("admin"):
    st.stop()
st.title("👥 Perfiles")
st.caption("Cada persona entra con su PIN de 4 cifras; dirección, con usuario + PIN. Los PIN se dan en persona.")

locales = {l["id"]: l["nombre"] for l in db.locales()}
personas = [t for t in db.trabajadores() if t.get("rol") != "admin"]
try:
    ultimos = {}
    for a in db.table("accesos").select("trabajador_id,created_at").eq("exito", True) \
            .order("created_at", desc=True).limit(500).execute().data:
        ultimos.setdefault(a["trabajador_id"], a["created_at"])
except Exception:
    st.error("Falta ejecutar supabase/acceso.sql en Supabase.")
    st.stop()

# ── Lista compacta ──
st.dataframe(
    [{"Nombre": t["name"], "Rol": sesion.ROLES.get(t.get("rol"), t.get("rol")),
      "Sedes": ", ".join(locales.get(l, l) for l in sesion.sedes(t)) or "Todas", "PIN": "✅" if t.get("pin_hash") else "⏳ sin PIN",
      "Activo": t.get("activo", True),
      "Última entrada": datetime.fromisoformat(ultimos[t["id"]]).astimezone().strftime("%d/%m %H:%M")
      if t["id"] in ultimos else ""}
     for t in sorted(personas, key=lambda t: (not t.get("activo", True), t["name"].lower()))],
    hide_index=True, width="stretch")


# Sin la columna `locales` (falta ejecutar supabase/sedes.sql) solo se guarda la sede principal
CON_COLUMNA_SEDES = any("locales" in t for t in db.trabajadores())
if not CON_COLUMNA_SEDES:
    st.warning("Falta ejecutar supabase/sedes.sql en Supabase para asignar más de una sede. "
               "Mientras tanto solo se guarda la sede principal.")


def _sedes(persona: dict | None, clave: str) -> tuple[list[str], str | None]:
    """Sedes (vacío = todas) y sede principal. Devuelve (sedes, principal)."""
    actuales = sesion.sedes(persona)
    elegidas = st.multiselect("Sedes", list(locales), default=actuales, format_func=locales.get,
                              placeholder="Vacío = todas las sedes", key=f"sedes-{clave}")
    opciones = [None, *locales]
    principal = st.selectbox("Sede principal", opciones, index=opciones.index(actuales[0]) if actuales else 0,
                             format_func=lambda i: locales.get(i, "Ninguna (la primera sede)"),
                             help="La que se elige por defecto al entrar. Tiene que estar entre las sedes.",
                             key=f"principal-{clave}")
    return elegidas, principal


def _datos_sedes(elegidas: list[str], principal: str | None) -> tuple[dict, str | None]:
    """Campos a guardar y, si hay algo mal, el mensaje de error."""
    if principal and elegidas and principal not in elegidas:
        return {}, "La sede principal tiene que estar entre las sedes."
    if principal and not elegidas:
        elegidas = [principal]
    principal = principal or (elegidas[0] if elegidas else None)
    datos = {"local_id": principal}
    if CON_COLUMNA_SEDES:
        datos["locales"] = elegidas or None
    return datos, None


def _comprobar_pin(pin: str, rol: str, excepto: str | None = None) -> str | None:
    if rol in sesion.CON_USUARIO:
        return None if len(pin) >= 6 else "Para dirección, mínimo 6 caracteres."
    if not sesion.pin_valido(pin):
        return f"El PIN tiene que ser de {sesion.LARGO_PIN} cifras."
    if sesion.pin_en_uso(pin, excepto):
        return "Ese PIN ya lo usa otra persona. Elige otro."
    return None


editar, nueva = st.tabs(["Editar persona", "➕ Nueva persona"])

with editar:
    if not personas:
        st.info("Todavía no hay nadie. Créalo en «Nueva persona».")
    else:
        elegida = st.selectbox("Persona", personas, format_func=lambda t: t["name"], index=None,
                               placeholder="Elige a quién")
        if elegida:
            with st.form(f"editar-{elegida['id']}"):
                c1, c2 = st.columns(2)
                roles = sesion.roles_asignables()
                rol = c1.selectbox("Rol", roles, format_func=sesion.ROLES.get,
                                   index=roles.index(elegida["rol"]) if elegida.get("rol") in roles else 0)
                with c2:
                    sedes_elegidas, principal = _sedes(elegida, elegida["id"])
                usuario = st.text_input("Usuario (solo dirección)", value=elegida.get("usuario") or "")
                pin = st.text_input("Nuevo PIN (déjalo vacío para no cambiarlo)", type="password")
                activo = st.toggle("Activo (puede entrar)", value=elegida.get("activo", True))
                if st.form_submit_button("Guardar", type="primary"):
                    error = _comprobar_pin(pin, rol, elegida["id"]) if pin else None
                    if rol in sesion.CON_USUARIO and not usuario.strip():
                        error = "Dirección necesita un usuario."
                    datos_sedes, error_sedes = _datos_sedes(sedes_elegidas, principal)
                    error = error or error_sedes
                    if error:
                        st.error(error)
                    else:
                        cambios = {"rol": rol, **datos_sedes, "activo": activo,
                                   "usuario": usuario.strip().lower() or None}
                        if pin:
                            cambios["pin_hash"] = sesion.huella(pin)
                        db.table("trabajadores").update(cambios).eq("id", elegida["id"]).execute()
                        st.toast(f"{elegida['name']}: guardado")
                        st.rerun()

            # ── Revisión paso a paso: sin «Todo bien», tiene que marcar cada tarea ──
            st.markdown("**Revisión tarea por tarea**")
            st.caption("Quita el «✅ Todo bien» de un toque: tendrá que marcar cada tarea del protocolo. "
                       "Para quien necesita repasar cómo se hace algo. El motivo solo lo ves tú.")
            try:
                reglas = db.table("paso_a_paso").select("*").eq("trabajador_id", elegida["id"]) \
                    .eq("activo", True).order("created_at").execute().data
            except Exception:
                st.warning("Falta ejecutar supabase/paso_a_paso.sql en Supabase.")
                reglas = None
            if reglas is not None:
                protos = {p["id"]: f"{p['nombre']} · {locales.get(p['local_id'], '')}"
                          for p in db.table("protocolos").select("id,nombre,local_id").eq("activo", True)
                          .neq("tipo", "averia").order("nombre").execute().data
                          if not sesion.sedes(elegida) or p["local_id"] in sesion.sedes(elegida)}
                hoy_iso = datetime.now().date().isoformat()
                for r in reglas:
                    vigente = not r.get("hasta") or r["hasta"] >= hoy_iso
                    a, b = st.columns([5, 1], vertical_alignment="center")
                    a.markdown(f"📋 **{protos.get(r['protocolo_id'], 'Protocolo') if r['protocolo_id'] else 'Todos los protocolos'}**"
                               f" · {('hasta el ' + datetime.fromisoformat(r['hasta']).strftime('%d/%m')) if r.get('hasta') else 'sin fecha de fin'}"
                               + ("" if vigente else " · _terminada_")
                               + (f"  \n<small>{r['motivo']}</small>" if r.get("motivo") else ""),
                               unsafe_allow_html=True)
                    if b.button("Quitar", key=f"quitar-pap-{r['id']}"):
                        db.table("paso_a_paso").update({"activo": False}).eq("id", r["id"]).execute()
                        st.rerun()
                with st.form(f"pap-{elegida['id']}", clear_on_submit=True):
                    c1, c2 = st.columns([3, 2])
                    elegidos = c1.multiselect("Protocolos", list(protos), format_func=protos.get,
                                              placeholder="Vacío = todos los protocolos")
                    dias = c2.selectbox("Durante", [7, 14, 30, 60, None],
                                        format_func=lambda d: f"{d} días" if d else "Hasta que la quite", index=1)
                    motivo = st.text_input("Motivo (privado)", placeholder="Ej: amonestación por la limpieza de suelos")
                    if st.form_submit_button("Activar tarea por tarea"):
                        hasta = (datetime.now().date() + timedelta(days=dias)).isoformat() if dias else None
                        db.table("paso_a_paso").insert([
                            {"trabajador_id": elegida["id"], "protocolo_id": p, "hasta": hasta,
                             "motivo": motivo.strip() or None, "creado_por": sesion.nombre()}
                            for p in (elegidos or [None])]).execute()
                        st.toast(f"{elegida['name']}: revisará tarea por tarea")
                        st.rerun()

with nueva:
    with st.form("nueva-persona", clear_on_submit=True):
        nombre = st.text_input("Nombre *", placeholder="Como aparecerá en etiquetas y registros")
        c1, c2 = st.columns(2)
        roles = sesion.roles_asignables()
        rol = c1.selectbox("Rol", roles, format_func=sesion.ROLES.get)
        with c2:
            sedes_elegidas, principal = _sedes(None, "nueva")
        usuario = st.text_input("Usuario (solo dirección)")
        pin = st.text_input(f"PIN * ({sesion.LARGO_PIN} cifras; dirección: mínimo 6 caracteres)", type="password",
                            help="Dáselo en persona.")
        if st.form_submit_button("Crear", type="primary"):
            error = ("Pon un nombre." if not nombre.strip() else
                     "Dirección necesita un usuario." if rol in sesion.CON_USUARIO and not usuario.strip() else
                     _comprobar_pin(pin, rol))
            datos_sedes, error_sedes = _datos_sedes(sedes_elegidas, principal)
            error = error or error_sedes
            if error:
                st.error(error)
            else:
                db.table("trabajadores").insert({
                    "id": str(int(datetime.now().timestamp() * 1000)), "name": nombre.strip(), "rol": rol,
                    **datos_sedes, "usuario": usuario.strip().lower() or None, "pin_hash": sesion.huella(pin),
                }).execute()
                st.toast(f"{nombre.strip()} ya puede entrar con su PIN")
                st.rerun()

# ── Tu PIN (admin): entras con el teclado como los demás y tu sesión no caduca ──
st.divider()
st.subheader("Tu PIN de admin")
st.caption("Con él entras desde el teclado numérico. Tu sesión no se bloquea sola: ciérrala con «Cerrar sesión» "
           "si usas una tablet del local. Sigues pudiendo entrar con tu usuario y este PIN.")
with st.form("pin-admin", clear_on_submit=True):
    c1, c2 = st.columns(2)
    nuevo = c1.text_input(f"Nuevo PIN ({sesion.LARGO_PIN} cifras)", type="password")
    otra = c2.text_input("Repítelo", type="password")
    if st.form_submit_button("Guardar mi PIN"):
        error = ("No coinciden." if nuevo != otra else _comprobar_pin(nuevo, "admin", sesion.actual()["id"]))
        if error:
            st.error(error)
        else:
            db.table("trabajadores").update({"pin_hash": sesion.huella(nuevo)}).eq("id", sesion.actual()["id"]).execute()
            st.success("Guardado. La próxima vez entra con el teclado.")

# ── Bloqueo automático por inactividad ──
st.divider()
st.subheader("Bloqueo automático (todos menos el admin)")
opciones = [1, 2, 5, 10, 15, 30, 60]
actual = sesion.minutos_bloqueo()
minutos = st.select_slider("Pedir el PIN otra vez tras estos minutos sin usar la app", opciones,
                           value=actual if actual in opciones else 5)
if minutos != actual:
    db.table("ajustes").upsert({"clave": "bloqueo_minutos", "valor": str(minutos)}).execute()
    st.toast(f"Bloqueo a los {minutos} min")
