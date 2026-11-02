"""Registro de errores y avisos de la app: todo lo que falla se apunta en Supabase para que el admin lo vea en
«🧾 Registro de errores». Apuntar NUNCA debe romper nada: si la tabla no existe o no hay red, se escribe en stderr.

Uso habitual:
    registro.error("IA", "La IA no responde", detalle=traceback_o_datos)
    registro.aviso("Notion", "Notion no responde")
    with registro.capturar("Rumbo · crear"):        # apunta la excepción y la vuelve a lanzar
        ...
    @registro.capturar("Avisos", relanzar=False)    # apunta la excepción y la traga
    def enviar(): ...
En app.py:  registro.instalar()  y  registro.ejecutar_pagina(pagina)  en lugar de  pagina.run().
"""
import json
import logging
import sys
import time
import traceback
from contextlib import ContextDecorator

import streamlit as st

from core import db, sesion

APP = "gerencia"
NIVELES = ("error", "aviso", "info")
SEGUNDOS_REPETIDO = 60                       # el mismo apunte dentro de este margen (en la misma sesión) se salta
_MAX_MENSAJE, _MAX_DETALLE = 500, 8000
_recientes_proceso: dict[tuple, float] = {}  # respaldo cuando no hay sesión de Streamlit (p. ej. enviar_avisos.py)

try:  # excepciones con las que Streamlit controla el flujo (st.stop, st.rerun, st.switch_page…): no son fallos
    from streamlit.runtime.scriptrunner_utils.exceptions import ScriptControlException as _Control
except Exception:  # pragma: no cover - otra versión de Streamlit
    _Control = ()


def _recientes() -> dict:
    try:
        return st.session_state.setdefault("_registro_recientes", {})
    except Exception:
        return _recientes_proceso


def _repetido(origen: str, mensaje: str) -> bool:
    ahora, memoria, clave = time.time(), _recientes(), (origen, mensaje)
    if ahora - memoria.get(clave, 0) < SEGUNDOS_REPETIDO:
        return True
    memoria[clave] = ahora
    for k in [k for k, t in memoria.items() if ahora - t > SEGUNDOS_REPETIDO * 5]:   # no crece sin límite
        memoria.pop(k, None)
    return False


def _local() -> str | None:
    try:
        return st.session_state.get("local_id")
    except Exception:
        return None


def _persona() -> str:
    try:
        return sesion.nombre() or ""
    except Exception:
        return ""


def apuntar(nivel: str, origen: str, mensaje: str, detalle=None) -> bool:
    """Apunta un suceso en el registro. Nunca lanza errores. Devuelve si se guardó en Supabase."""
    try:
        nivel = nivel if nivel in NIVELES else "error"
        origen, mensaje = str(origen or "")[:200], str(mensaje or "")[:_MAX_MENSAJE]
        if _repetido(origen, mensaje):
            return False
        if detalle is not None and not isinstance(detalle, str):
            detalle = json.dumps(detalle, ensure_ascii=False, default=str)
        fila = {"app": APP, "nivel": nivel, "origen": origen, "mensaje": mensaje,
                "detalle": (detalle or None) and detalle[:_MAX_DETALLE],
                "persona": _persona() or None, "local_id": _local()}
        try:
            db.table("registro_errores").insert(fila).execute()
            return True
        except (Exception, _Control) as e:   # falta supabase/registro_errores.sql, sin red, st.stop() por falta de claves…
            print(f"[registro] no se pudo guardar ({type(e).__name__}): {nivel} · {origen} · {mensaje}", file=sys.stderr)
            return False
    except BaseException as e:   # apuntar jamás rompe la app
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        try:
            print(f"[registro] fallo interno: {e!r}", file=sys.stderr)
        except Exception:
            pass
        return False


def error(origen: str, mensaje: str, detalle=None) -> bool:
    return apuntar("error", origen, mensaje, detalle)


def aviso(origen: str, mensaje: str, detalle=None) -> bool:
    return apuntar("aviso", origen, mensaje, detalle)


def excepcion(origen: str, exc: BaseException, mensaje: str | None = None) -> bool:
    """Apunta una excepción con su traceback completo."""
    texto = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return apuntar("error", origen, mensaje or f"{type(exc).__name__}: {exc}", texto)


class capturar(ContextDecorator):
    """Context manager / decorador: apunta la excepción que ocurra dentro. `relanzar=False` la traga."""

    def __init__(self, origen: str, relanzar: bool = True):
        self.origen, self.relanzar = origen, relanzar

    def __enter__(self):
        return self

    def __exit__(self, tipo, exc, tb):
        if exc is None or not isinstance(exc, Exception):   # st.stop(), st.rerun(), Ctrl+C… pasan sin tocar
            return False
        excepcion(self.origen, exc)
        return not self.relanzar


def ejecutar_pagina(pagina) -> None:
    """Sustituye a `pagina.run()`: si la página falla, lo apunta y muestra un aviso amable en vez del traceback."""
    try:
        pagina.run()
    except Exception as e:   # st.stop / st.rerun / st.switch_page son BaseException: pasan de largo
        origen = str(getattr(pagina, "title", None) or getattr(pagina, "url_path", None) or "página")
        excepcion(origen, e)
        st.error("Algo ha fallado en esta pantalla. Ya ha quedado apuntado para el admin.")
        try:
            if sesion.puede("admin"):
                st.exception(e)
        except Exception:
            pass


class ManejadorRegistro(logging.Handler):
    """Envía al registro los WARNING o superiores de los loggers propios (no el ruido interno de Streamlit)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < logging.WARNING:
                return
            texto = None
            if record.exc_info:
                texto = "".join(traceback.format_exception(*record.exc_info))
            apuntar("error" if record.levelno >= logging.ERROR else "aviso", record.name, record.getMessage(), texto)
        except Exception:
            pass


# Solo nuestros paquetes (core.*, paginas.*) y el logger «lilos»; nunca streamlit, tornado, httpx…
LOGGERS_PROPIOS = ("lilos", "core", "paginas")


def instalar() -> None:
    """Conecta el registro con el logging de Python. Se puede llamar en cada recarga: solo actúa una vez."""
    for nombre in LOGGERS_PROPIOS:
        logger = logging.getLogger(nombre)
        if not any(isinstance(h, ManejadorRegistro) for h in logger.handlers):
            logger.addHandler(ManejadorRegistro(level=logging.WARNING))
