"""Acceso a Supabase para la app de gerencia (mismos datos que la app de etiquetas)."""
import os
from pathlib import Path

import streamlit as st
from supabase import Client, create_client


def _config(key: str) -> str | None:
    """Lee la configuración de .streamlit/secrets.toml y, si no está, del .env de LilOS."""
    try:
        if key in st.secrets:
            return str(st.secrets[key]).strip()
        for seccion in st.secrets.values():   # también si quedó dentro de una sección [algo]
            if hasattr(seccion, "keys") and key in seccion:
                return str(seccion[key]).strip()
    except FileNotFoundError:
        pass
    if key in os.environ:
        return os.environ[key]
    env = Path(__file__).resolve().parents[2] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == key:
                return value.strip().strip("'\"")
    return None


def config(key: str) -> str | None:
    return _config(key)


@st.cache_resource
def client() -> Client:
    url, key = _config("SUPABASE_URL"), _config("SUPABASE_SERVICE_KEY")
    if not url or not key:
        faltan = [n for n, v in (("SUPABASE_URL", url), ("SUPABASE_SERVICE_KEY", key)) if not v]
        try:
            vistas = ", ".join(repr(k) for k in st.secrets.keys()) or "ninguna"
        except FileNotFoundError:
            vistas = "no hay secrets"
        # Diagnóstico (solo nombres, nunca valores): de qué archivos y variables salen las claves
        from streamlit import config as st_config
        archivos = ", ".join(f"{p} ({'existe' if Path(p).exists() else 'no existe'})"
                             for p in st_config.get_option("secrets.files") or [])
        entorno = ", ".join(sorted(k for k in os.environ if "SUPABASE" in k.upper())) or "ninguna"
        st.caption(f"Diagnóstico · archivos de secrets: {archivos or '—'} · variables de entorno con SUPABASE: "
                   f"{entorno} · versión de Streamlit: {st.__version__}")
        st.error(f"Falta {' y '.join(faltan)} en .streamlit/secrets.toml (o en el .env de LilOS). "
                 f"Claves que la app sí ve en Secrets: {vistas}. Revisa que el nombre esté escrito igual, "
                 "en mayúsculas, con el valor entre comillas, y reinicia la app (⋮ → Reboot app).")
        st.stop()
    # Supabase a veces muestra la URL de la API (…/rest/v1/); el cliente necesita solo la base
    from urllib.parse import urlparse
    parts = urlparse(url.strip())
    return create_client(f"{parts.scheme}://{parts.netloc}", key)


def solo_lectura() -> bool:
    """Modo invitado (compañeros y profesor del máster): ve la app pero no guarda, borra ni envía nada."""
    try:
        return bool(st.session_state.get("invitado"))
    except Exception:  # fuera de una sesión de Streamlit (scripts sueltos)
        return False


class _Respuesta:
    def __init__(self, data):
        self.data, self.count = data, None


class _EscrituraBloqueada:
    """Sustituye a insert/update/upsert/delete en modo invitado: acepta cualquier filtro encadenado (.eq, .in_…)
    y al ejecutar no toca la base; devuelve lo que se habría guardado para que la pantalla siga funcionando."""

    def __init__(self, filas):
        self._filas = filas

    def __getattr__(self, _):
        return lambda *a, **k: self

    def execute(self):
        st.toast("👀 Modo invitado: no se ha guardado nada.")
        filas = self._filas if isinstance(self._filas, list) else [self._filas] if self._filas else []
        return _Respuesta([{"id": "00000000-0000-0000-0000-000000000000", **f} for f in filas if isinstance(f, dict)])


class _TablaSoloLectura:
    def __init__(self, tabla):
        self._tabla = tabla

    def __getattr__(self, nombre):
        return getattr(self._tabla, nombre)   # select y demás lecturas, tal cual

    def insert(self, filas, *a, **k):
        return _EscrituraBloqueada(filas)

    upsert = insert

    def update(self, *a, **k):
        return _EscrituraBloqueada(None)

    def delete(self, *a, **k):
        return _EscrituraBloqueada(None)


def table(name: str):
    tabla = client().table(name)
    return _TablaSoloLectura(tabla) if solo_lectura() else tabla


@st.cache_data(ttl=300)
def locales() -> list[dict]:
    return table("locales").select("*").order("nombre").execute().data


def equipos(local_id: str | None = None) -> list[dict]:
    query = table("equipos").select("*").order("nombre")
    if local_id:
        query = query.eq("local_id", local_id)
    return query.execute().data


def tareas(equipo_ids: list[str] | None = None, solo_activas: bool = True) -> list[dict]:
    query = table("tareas_mantenimiento").select("*").order("proxima_fecha")
    if solo_activas:
        query = query.eq("activa", True)
    if equipo_ids is not None:
        if not equipo_ids:
            return []
        query = query.in_("equipo_id", equipo_ids)
    return query.execute().data


def bitacora(equipo_ids: list[str] | None = None, limite: int = 200) -> list[dict]:
    query = table("bitacora_equipos").select("*").order("fecha", desc=True).order("created_at", desc=True).limit(limite)
    if equipo_ids is not None:
        if not equipo_ids:
            return []
        query = query.in_("equipo_id", equipo_ids)
    return query.execute().data


def trabajadores() -> list[dict]:
    return table("trabajadores").select("*").order("name").execute().data


# ── APPCC ──
@st.cache_data(ttl=60)
def proveedores() -> list[dict]:
    return table("proveedores").select("*").order("nombre").execute().data


def servicios(local_id: str | None = None, solo_activos: bool = True) -> list[dict]:
    query = table("servicios").select("*").order("nombre")
    if local_id:
        query = query.eq("local_id", local_id)
    if solo_activos:
        query = query.eq("activo", True)
    return query.execute().data


def bitacora_servicios(servicio_ids: list[str], limite: int = 200) -> list[dict]:
    if not servicio_ids:
        return []
    return (table("bitacora_equipos").select("*").in_("servicio_id", servicio_ids)
            .order("fecha", desc=True).order("created_at", desc=True).limit(limite).execute().data)


def productos_limpieza(local_id: str) -> list[dict]:
    return table("productos_limpieza").select("*").eq("local_id", local_id).order("codigo").execute().data


def protocolos(local_id: str, solo_activos: bool = True) -> list[dict]:
    query = table("protocolos").select("*").eq("local_id", local_id).order("nombre")
    if solo_activos:
        query = query.eq("activo", True)
    return query.execute().data


def pasos(protocolo_id: str) -> list[dict]:
    return (table("protocolo_pasos").select("*").eq("protocolo_id", protocolo_id).eq("activo", True)
            .order("orden").execute().data)


def registros_protocolo(protocolo_ids: list[str], limite: int = 100, desde: str | None = None) -> list[dict]:
    """Registros firmados, los más recientes primero. Con `desde` (AAAA-MM-DD), solo a partir de esa fecha."""
    if not protocolo_ids:
        return []
    query = table("protocolo_registros").select("*").in_("protocolo_id", protocolo_ids)
    if desde:
        query = query.gte("fecha", desde)
    return query.order("fecha", desc=True).order("created_at", desc=True).limit(limite).execute().data


def trabajadores_local(local_id: str) -> list[str]:
    """Nombres del personal del local (y de quien no tiene local asignado)."""
    from core import sesion
    return [t["name"] for t in trabajadores() if sesion.en_sede(t, local_id)]


# ── Comunicados con confirmación de lectura ──
def comunicados(local_id: str, solo_activos: bool = True) -> list[dict]:
    query = table("comunicados").select("*").or_(f"local_id.eq.{local_id},local_id.is.null") \
        .order("created_at", desc=True)
    if solo_activos:
        query = query.eq("activo", True)
    return query.execute().data


def lecturas(comunicado_ids: list[str]) -> list[dict]:
    if not comunicado_ids:
        return []
    return table("comunicado_lecturas").select("*").in_("comunicado_id", comunicado_ids).execute().data
