"""Impresión de etiquetas por cola (supabase/impresion.sql).

Desde gerencia (o el móvil, cuando la app esté publicada) se añade un trabajo a `cola_impresion`; el ordenador
PRINCIPAL del local (el que tiene la DYMO y ejecuta la etiquetadora, ver impresion/agente.js) lo imprime y lo
marca como impresa. Aquí está la lógica común de las páginas 🏷️ Imprimir etiqueta y 🖨️ Dispositivos.

La caducidad se calcula EXACTAMENTE como la etiquetadora (public/index.html, handlePrintAction):
    caducidad = preparación + horas del producto (exp_hours), sumadas en tiempo absoluto
                (JS: new Date(now.getTime() + horas * 3600 * 1000)), o las horas de la «caducidad forzada».
Las fechas se mandan en ISO con zona y el ordenador del local las imprime en su hora (Europe/Madrid).
"""
from datetime import datetime, timedelta, timezone

from core import db

try:
    from zoneinfo import ZoneInfo
    ZONA = ZoneInfo("Europe/Madrid")           # los tres locales (Barcelona y Madrid) van con esta hora
except Exception:  # pragma: no cover - sin base de datos de zonas: la del sistema
    ZONA = datetime.now().astimezone().tzinfo

ESTADOS = {"pendiente": "⏳ En cola", "imprimiendo": "🖨️ Imprimiendo", "impresa": "✅ Impresa",
           "error": "⚠️ Error", "cancelada": "✖️ Cancelada"}
EN_LINEA_SEGUNDOS = 120                        # un dispositivo está en línea si su latido es de hace < 2 min
MAX_COPIAS = 20

# Mismas categorías y colores que la etiquetadora (appccCategories en public/index.html)
CATEGORIAS = {
    "Salsas y Aderezos": "#C0392B", "Carnes Cocinadas": "#8E44AD", "Lácteos y Quesos": "#2980B9",
    "Masas y Repostería": "#D35400", "Vegetales Procesados": "#27AE60", "Pescados y Mariscos": "#16A085",
    "Secos y Despensa": "#7F8C8D",
}
# Caducidad forzada (reenvasados), como el desplegable de la barra superior (EXP_OVERRIDE_DAYS)
DIAS_FORZADOS = [0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 10, 14, 21, 30]


# ── Cálculos (iguales que en la etiquetadora) ──
def dias_a_horas(dias: float) -> int:
    """daysToHours de la etiquetadora: Math.round(d * 24)."""
    return int(_redondear(float(dias) * 24))


def _redondear(x: float) -> float:
    """Math.round de JavaScript (las mitades hacia arriba, no al par como round() de Python)."""
    import math
    return math.floor(x + 0.5)


def texto_dias(horas: float) -> str:
    """formatDays de la etiquetadora: «3 días», «1 día», «0,5 días»."""
    d = float(horas) / 24
    texto = f"{_redondear(d * 10) / 10:g}".replace(".", ",")
    return f"{texto} {'día' if d == 1 else 'días'}"


def ahora() -> datetime:
    return datetime.now(ZONA)


def caducidad(preparacion: datetime, horas: float) -> datetime:
    """Preparación + horas en tiempo absoluto (igual que JS), devuelta en hora de Madrid."""
    if preparacion.tzinfo is None:
        preparacion = preparacion.replace(tzinfo=ZONA)
    return (preparacion.astimezone(timezone.utc) + timedelta(milliseconds=float(horas) * 3600 * 1000)).astimezone(ZONA)


def formato(fecha: datetime) -> str:
    """formatDateTime de la etiquetadora: dd/mm/aa hh:mm (hora de Madrid)."""
    return fecha.astimezone(ZONA).strftime("%d/%m/%y %H:%M")


def datos_trabajo(producto: dict, preparacion: datetime, responsable: str, horas: float | None = None,
                  lote: str = "", copias: int = 1) -> dict:
    """Contenido de cola_impresion.datos (lo que necesita la etiqueta). `horas` = caducidad forzada."""
    horas = float(producto.get("exp_hours") or 48) if horas is None else float(horas)
    if preparacion.tzinfo is None:
        preparacion = preparacion.replace(tzinfo=ZONA)
    return {
        "producto": producto["name"], "producto_id": producto.get("id"), "categoria": producto.get("category"),
        "conservacion": producto.get("storage"), "alergenos": producto.get("allergens") or "Ninguno",
        "preparacion": preparacion.isoformat(), "caducidad": caducidad(preparacion, horas).isoformat(),
        "horas_caducidad": horas, "responsable": responsable or "DESCONOCIDO",
        "lote": (lote or "").strip().upper(), "copias": max(1, min(MAX_COPIAS, int(copias or 1))),
    }


def sedes(sedes_persona: list[str], locales: list[str], todas: bool = False) -> list[str]:
    """Locales a los que puede mandar etiquetas: todos (dirección/admin) o sus sedes (sesion.sedes: local_id y
    `locales`). Como en el resto de la app, quien no tiene ninguna sede asignada trabaja en todas."""
    propias = [] if todas else [l for l in sedes_persona if l in locales]
    return propias or list(locales)


def en_linea(dispositivo: dict, momento: datetime | None = None) -> bool:
    latido = dispositivo.get("ultimo_latido")
    if not latido:
        return False
    return ((momento or datetime.now(timezone.utc)) - datetime.fromisoformat(latido)).total_seconds() < EN_LINEA_SEGUNDOS


# ── Base de datos ──
def productos() -> list[dict]:
    """El catálogo de la etiquetadora (tabla productos, como db.js listProducts)."""
    return db.table("productos").select("id,name,category,storage,exp_hours,allergens,vegan").order("name").execute().data


def dispositivos(local_id: str | None = None) -> list[dict]:
    query = db.table("dispositivos").select("*").order("nombre")
    if local_id:
        query = query.eq("local_id", local_id)
    return query.execute().data


def encolar(local_id: str, datos: dict, solicitado_por: str, origen: str = "gerencia") -> dict:
    fila = {"local_id": local_id, "datos": datos, "solicitado_por": solicitado_por or None, "origen": origen,
            "estado": "pendiente", "intentos": 0}
    return db.table("cola_impresion").insert(fila).execute().data[0]


def trabajos(local_id: str | None = None, estados: list[str] | None = None, limite: int = 30) -> list[dict]:
    query = db.table("cola_impresion").select("*").order("created_at", desc=True).limit(limite)
    if local_id:
        query = query.eq("local_id", local_id)
    if estados:
        query = query.in_("estado", estados)
    return query.execute().data


def actualizar_dispositivo(dispositivo_id: str, cambios: dict) -> None:
    db.table("dispositivos").update(cambios).eq("id", dispositivo_id).execute()


def reintentar(trabajo_id: str) -> None:
    """Vuelve a poner en cola un trabajo con error (o cancelado); sigue por la copia que faltaba."""
    db.table("cola_impresion").update({"estado": "pendiente", "intentos": 0, "error": None}) \
        .eq("id", trabajo_id).in_("estado", ["error", "cancelada"]).execute()


def cancelar(trabajo_id: str) -> None:
    db.table("cola_impresion").update({"estado": "cancelada"}) \
        .eq("id", trabajo_id).in_("estado", ["pendiente", "error"]).execute()


def resumen(trabajo: dict) -> str:
    d = trabajo.get("datos") or {}
    copias = int(d.get("copias") or 1)
    return f"{d.get('producto', '—')}" + (f" ×{copias}" if copias > 1 else "")
