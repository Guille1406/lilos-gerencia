"""Acceso con PIN personal (como el TPV de Square) y permisos por rol.

Trabajadores y gerentes entran solo con su PIN de 4 cifras; dirección y admin, con usuario + PIN/contraseña.
La app se bloquea sola tras unos minutos sin uso y vuelve a pedir el PIN. El PIN nunca se guarda: solo su
huella (pbkdf2 con sal).
"""
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

import streamlit as st

from core import db

ROLES = {"staff": "Trabajador", "gerente": "Gerente", "directivo": "Dirección", "admin": "Admin"}
NIVEL = {"staff": 0, "gerente": 1, "directivo": 2, "admin": 3}
CON_USUARIO = ("directivo",)            # entran con usuario + PIN/contraseña, nunca solo con PIN
SIN_BLOQUEO = ("admin",)                 # el admin no caduca: se cierra a mano con «Cerrar sesión»
LARGO_PIN = 4
INTENTOS_SESION = 5                      # fallos seguidos en este dispositivo antes de esperar
ESPERA_MINUTOS = 5
INTENTOS_GLOBALES = 20                   # fallos en 10 minutos (todos los dispositivos) antes de pausar
_ITERACIONES = 20_000
# Perfil invitado (muro del máster): ve como un gerente sin sede, todos los locales, pero no guarda nada (db.solo_lectura)
INVITADO = {"id": "00000000-0000-0000-0000-000000000000", "name": "Invitado", "rol": "gerente", "activo": True}


# ── Huella del PIN ──
def huella(clave: str) -> str:
    sal = secrets.token_hex(8)
    return f"{sal}${hashlib.pbkdf2_hmac('sha256', clave.encode(), sal.encode(), _ITERACIONES).hex()}"


def coincide(clave: str, guardada: str | None) -> bool:
    if not guardada or "$" not in guardada:
        return False
    sal, valor = guardada.split("$", 1)
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", clave.encode(), sal.encode(), _ITERACIONES).hex(), valor)


def pin_valido(pin: str) -> bool:
    return pin.isdigit() and len(pin) == LARGO_PIN


def pin_en_uso(pin: str, excepto_id: str | None = None) -> bool:
    """Cada PIN identifica a una persona: no puede repetirse."""
    return any(coincide(pin, t.get("pin_hash")) for t in db.trabajadores() if t["id"] != excepto_id)


# ── Persona que está usando la app ──
def actual() -> dict | None:
    return st.session_state.get("persona")


def nombre() -> str:
    return (actual() or {}).get("name", "")


def nivel(persona: dict | None = None) -> int:
    return NIVEL.get((persona or actual() or {}).get("rol"), -1)


def puede(rol_minimo: str) -> bool:
    return nivel() >= NIVEL[rol_minimo]


def roles_asignables() -> list[str]:
    """El admin asigna cualquier rol por debajo del suyo (dirección, gerencia, trabajador)."""
    return [r for r in ROLES if NIVEL[r] < nivel()]


# ── Sedes: una persona puede pertenecer a más de una ──
def sedes(persona: dict | None) -> list[str]:
    """Sedes de la persona: la principal (local_id) primero y luego el resto de `locales`. Lista vacía = todas
    (dirección y admin, o quien no tiene ninguna asignada). Sin la columna `locales` en la base, solo cuenta local_id."""
    if not persona:
        return []
    principal = persona.get("local_id")
    salida = [principal] if principal else []
    for local in persona.get("locales") or []:
        if local and local not in salida:
            salida.append(local)
    return salida


def pertenece(persona: dict | None, local_id: str | None) -> bool:
    """¿Está asignada expresamente a esa sede? (sin sedes, no: sirve para grupos y visibilidad estrictas)"""
    return bool(local_id) and local_id in sedes(persona)


def en_sede(persona: dict | None, local_id: str | None) -> bool:
    """¿Trabaja en esa sede? Sin sedes asignadas, en todas."""
    lista = sedes(persona)
    return not lista or local_id in lista


def sede_principal(persona: dict | None) -> str | None:
    lista = sedes(persona)
    return lista[0] if lista else None


def _registrar(persona: dict | None, exito: bool, motivo: str) -> None:
    try:
        db.table("accesos").insert({"trabajador_id": (persona or {}).get("id"), "nombre": (persona or {}).get("name"),
                                    "exito": exito, "motivo": motivo}).execute()
    except Exception:  # falta supabase/acceso.sql: no bloquea la entrada
        pass


def _entrar(persona: dict, motivo: str) -> None:
    st.session_state.persona = persona
    st.session_state.ultima_actividad = time.time()
    st.session_state.fallos = 0
    st.session_state.pin = ""
    if sede_principal(persona):
        st.session_state.local_id = sede_principal(persona)
    _registrar(persona, True, motivo)


def entrar_invitado() -> None:
    st.session_state.invitado = True
    st.session_state.persona = dict(INVITADO)
    st.session_state.ultima_actividad = time.time()


def salir() -> None:
    claves = ("persona", "pin", "local_id")
    if st.session_state.get("invitado"):   # el invitado vuelve a la contraseña de la app, no al teclado del PIN
        claves += ("invitado", "autenticado")
    for clave in claves:
        st.session_state.pop(clave, None)


def refrescar() -> None:
    """Relee a la persona (si la desactivan o le cambian el rol, se nota al momento)."""
    persona = actual()
    if not persona or st.session_state.get("invitado"):
        return
    fila = next((t for t in db.trabajadores() if t["id"] == persona["id"]), None)
    if not fila or not fila.get("activo", True):
        salir()
    else:
        st.session_state.persona = fila


# ── Bloqueo por inactividad ──
def minutos_bloqueo() -> int:
    try:
        fila = db.table("ajustes").select("valor").eq("clave", "bloqueo_minutos").execute().data
        return int(fila[0]["valor"]) if fila else 5
    except Exception:
        return 5


def marcar_actividad() -> None:
    """Se llama en cada recarga completa de la app (cada toque de la persona)."""
    if st.session_state.pop("_por_bloqueo", False):
        return
    st.session_state.ultima_actividad = time.time()


@st.fragment(run_every=20)
def vigilar_inactividad(minutos: int) -> None:
    if actual() and actual().get("rol") not in SIN_BLOQUEO and time.time() - st.session_state.get("ultima_actividad", time.time()) > minutos * 60:
        salir()
        st.session_state._por_bloqueo = True
        st.rerun(scope="app")


# ── Pantalla de acceso ──
def _bloqueado() -> str | None:
    hasta = st.session_state.get("espera_hasta", 0)
    if time.time() < hasta:
        return f"Demasiados intentos. Espera {int((hasta - time.time()) // 60) + 1} min."
    try:
        desde = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        fallos = db.table("accesos").select("id", count="exact").eq("exito", False).gte("created_at", desde) \
            .execute().count or 0
        if fallos >= INTENTOS_GLOBALES:
            return "Demasiados intentos fallidos en poco tiempo. Espera unos minutos."
    except Exception:
        pass
    return None


def _fallo(motivo: str) -> None:
    st.session_state.fallos = st.session_state.get("fallos", 0) + 1
    st.session_state.pin = ""
    if st.session_state.fallos >= INTENTOS_SESION:
        st.session_state.espera_hasta = time.time() + ESPERA_MINUTOS * 60
        st.session_state.fallos = 0
    _registrar(None, False, motivo)
    st.session_state.aviso_acceso = "PIN incorrecto" if motivo.startswith("pin") else "Usuario o clave incorrectos"


def _probar_pin(pin: str) -> None:
    persona = next((t for t in db.trabajadores() if t.get("activo", True) and t.get("rol") not in CON_USUARIO
                    and coincide(pin, t.get("pin_hash"))), None)
    _entrar(persona, "pin") if persona else _fallo("pin incorrecto")


def _tecla(t: str) -> None:
    st.session_state.aviso_acceso = None
    if t == "⌫":
        st.session_state.pin = st.session_state.get("pin", "")[:-1]
    elif len(st.session_state.get("pin", "")) < LARGO_PIN:
        st.session_state.pin = st.session_state.get("pin", "") + t
        if len(st.session_state.pin) == LARGO_PIN:
            _probar_pin(st.session_state.pin)


def pantalla_acceso(local: str = "") -> None:
    """Muestra el teclado del PIN y detiene la página hasta que alguien entra."""
    if actual():
        return
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl']{display:none}"
                "[class*='st-key-tecla-'] button{height:3.4rem}[class*='st-key-tecla-'] button p{font-size:1.5rem}</style>", unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        st.markdown("<h2 style='text-align:center;margin-bottom:0'>LilOS</h2>"
                    f"<p style='text-align:center;color:#78716C'>{local or 'Introduce tu PIN'}</p>",
                    unsafe_allow_html=True)
        espera = _bloqueado()
        if espera:
            st.error(espera)
            st.stop()
        if st.session_state.get("como_invitado"):   # muro del máster: solo la contraseña de invitado, sin PIN
            with st.form("acceso-invitado"):
                clave = st.text_input("Contraseña de invitado", type="password")
                if st.form_submit_button("Entrar", type="primary", width="stretch"):
                    if clave and hmac.compare_digest(clave, db.config("INVITADO_PASSWORD") or ""):
                        st.session_state.como_invitado = False
                        entrar_invitado()
                        st.rerun()
                    _fallo("invitado incorrecto")
            if st.session_state.get("aviso_acceso"):
                st.error("Contraseña incorrecta")
            st.button("← Entrar con PIN", on_click=lambda: st.session_state.update(como_invitado=False),
                      type="tertiary")
            st.stop()
        if st.session_state.get("con_usuario"):
            with st.form("acceso-usuario"):
                usuario = st.text_input("Usuario")
                clave = st.text_input("PIN o contraseña", type="password")
                if st.form_submit_button("Entrar", type="primary", width="stretch"):
                    persona = next((t for t in db.trabajadores() if t.get("activo", True)
                                    and (t.get("usuario") or "").lower() == usuario.strip().lower()), None)
                    if persona and coincide(clave, persona.get("pin_hash")):
                        _entrar(persona, "usuario")
                        st.rerun()
                    _fallo("usuario incorrecto")
            if st.session_state.get("aviso_acceso"):
                st.error(st.session_state.aviso_acceso)
            st.button("← Entrar con PIN", on_click=lambda: st.session_state.update(con_usuario=False),
                      type="tertiary")
            st.stop()

        if db.modo_demo():
            from core import demo
            st.info("**Versión de demostración, con datos inventados.** Prueba con el PIN "
                    + " o ".join(f"**{pin}** ({rol.lower()})" for rol, pin in demo.PINES.items())
                    + f". Dirección: usuario **{demo.USUARIO_DIRECCION[0]}**, PIN **{demo.USUARIO_DIRECCION[1]}**.")
        puntos = len(st.session_state.get("pin", ""))
        st.markdown(f"<p style='text-align:center;font-size:2rem;letter-spacing:.6rem;margin:.2rem 0'>"
                    f"{'●' * puntos}{'○' * (LARGO_PIN - puntos)}</p>", unsafe_allow_html=True)
        if st.session_state.get("aviso_acceso"):
            st.markdown(f"<p style='text-align:center;color:#B91C1C'>{st.session_state.aviso_acceso}</p>",
                        unsafe_allow_html=True)
        for fila in (("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9"), ("", "0", "⌫")):
            for col, t in zip(st.columns(3), fila):
                if t:
                    col.button(t, key=f"tecla-{t}", on_click=_tecla, args=(t,), width="stretch")
        st.button("Dirección: entrar con usuario", on_click=lambda: st.session_state.update(con_usuario=True),
                  type="tertiary", width="stretch")
        if db.config("INVITADO_PASSWORD"):
            st.button("👀 Entrar como invitado", on_click=lambda: st.session_state.update(como_invitado=True,
                      aviso_acceso=None), type="tertiary", width="stretch")
    if actual():
        st.rerun()
    st.stop()
