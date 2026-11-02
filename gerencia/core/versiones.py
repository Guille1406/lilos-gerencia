"""Historial de versiones de los procedimientos oficiales (POE del APPCC), para que tengan validez legal.

Cada versión guarda una foto («snapshot») del procedimiento y de sus pasos activos, el motivo del cambio, quién lo
hizo y las diferencias con la anterior. Solo se crea una versión nueva si el contenido ha cambiado de verdad.
Todo funciona sin la tabla (supabase/versiones.sql): sin ella no hay historial, pero la app sigue como siempre."""
from difflib import SequenceMatcher

from core import db, plan

FALTA_TABLA = "Falta ejecutar `supabase/versiones.sql` en Supabase: hasta entonces no se guarda el historial de versiones."

# Datos del procedimiento que forman parte de la versión (la «versión» en texto libre no: la pone la propia app)
CAMPOS = ("nombre", "tipo", "categoria", "frecuencia", "dias_semana", "semana_mes", "dia_mes", "mes_periodo",
          "veces_dia", "franja", "hora_limite", "descripcion", "activo")
CAMPOS_PASO = ("texto", "seccion", "producto", "dia_semana", "semana_mes")
_ETIQUETAS = {
    "nombre": "Nombre", "tipo": "Tipo", "categoria": "Categoría", "frecuencia": "Frecuencia",
    "dias_semana": "Días de la semana", "semana_mes": "Semana del mes", "dia_mes": "Día del mes",
    "mes_periodo": "Mes", "veces_dia": "Veces al día", "franja": "Momento", "hora_limite": "Hora límite",
    "descripcion": "Descripción", "activo": "Activo",
}


# ─────────────────────────── La foto del procedimiento ───────────────────────────

def _limpio(valor):
    """Normaliza un valor para poder comparar versiones: vacío = None, horas sin segundos, listas ordenadas."""
    if isinstance(valor, str):
        valor = valor.strip() or None
    if isinstance(valor, list):
        valor = sorted(valor) or None
    return valor


def armar_snapshot(protocolo: dict, pasos: list[dict]) -> dict:
    """Foto de un procedimiento: sus datos y la lista ordenada de pasos activos."""
    datos = {c: _limpio(protocolo.get(c)) for c in CAMPOS}
    if datos["hora_limite"]:
        datos["hora_limite"] = str(datos["hora_limite"])[:5]
    if datos["frecuencia"] is None:
        datos["frecuencia"] = "diaria"
    if datos["veces_dia"] is None:
        datos["veces_dia"] = 1
    if datos["activo"] is None:
        datos["activo"] = True
    activos = [p for p in pasos if p.get("activo", True)]
    activos.sort(key=lambda p: (p.get("orden") is None, p.get("orden") or 0))
    return {"protocolo": datos, "pasos": [{c: _limpio(p.get(c)) for c in CAMPOS_PASO} for p in activos]}


def snapshot(protocolo_id: str) -> dict:
    """Foto actual (sin caché) del procedimiento y sus pasos activos, tal como están ahora en la base de datos."""
    protocolo = db.table("protocolos").select("*").eq("id", protocolo_id).execute().data[0]
    pasos = (db.table("protocolo_pasos").select("*").eq("protocolo_id", protocolo_id).eq("activo", True)
             .order("orden").execute().data)
    return armar_snapshot(protocolo, pasos)


# ─────────────────────────── Diferencias entre dos versiones ───────────────────────────

def _texto(campo: str, valor) -> str:
    if valor is None or valor == "":
        return "—"
    if campo == "frecuencia":
        return plan.FRECUENCIAS_POE.get(valor, str(valor)).lower()
    if campo == "dias_semana":
        return ", ".join(plan.DIAS_CORTOS.get(d, str(d)) for d in valor)
    if campo == "semana_mes":
        return plan.SEMANAS_MES.get(valor, str(valor))
    if campo == "mes_periodo":
        return str(plan.MESES.get(valor) or plan.MESES_TRIMESTRE.get(valor) or valor)
    if campo == "franja":
        return plan.FRANJAS.get(valor, str(valor)).split(" ", 1)[-1].lower()
    if campo == "categoria":
        return plan.CATEGORIAS.get(valor, str(valor)).split(" ", 1)[-1]
    if campo == "tipo":
        return plan.TIPOS_PROTOCOLO.get(valor, str(valor)).split(" ", 1)[-1].lower()
    if campo == "activo":
        return "sí" if valor else "no"
    if campo == "descripcion":
        return f"«{valor}»"
    return str(valor)


def _detalle_paso(paso: dict) -> str:
    extra = []
    if paso.get("seccion"):
        extra.append(f"sección {paso['seccion']}")
    if paso.get("producto"):
        extra.append(f"producto {paso['producto']}")
    if paso.get("dia_semana"):
        extra.append(f"solo {plan.DIAS_SEMANA.get(paso['dia_semana'], paso['dia_semana']).lower()}")
    if paso.get("semana_mes"):
        extra.append(f"semana {paso['semana_mes']} del mes")
    return f" ({', '.join(extra)})" if extra else ""


def _cambios_paso(a: dict, b: dict) -> str:
    partes = []
    for campo, etiqueta in (("seccion", "sección"), ("producto", "producto"), ("dia_semana", "día"),
                            ("semana_mes", "semana del mes")):
        if a.get(campo) != b.get(campo):
            va = plan.DIAS_SEMANA.get(a.get(campo)) if campo == "dia_semana" else a.get(campo)
            vb = plan.DIAS_SEMANA.get(b.get(campo)) if campo == "dia_semana" else b.get(campo)
            partes.append(f"{etiqueta}: {va or '—'} → {vb or '—'}")
    return "; ".join(partes)


def diferencias(a: dict | None, b: dict) -> list[str]:
    """Qué cambió de la foto `a` (anterior) a la `b` (nueva), en frases. Con `a` vacío es la versión inicial."""
    if not a:
        return ["Versión inicial"]
    lineas = []
    pa, pb = a.get("protocolo") or {}, b.get("protocolo") or {}
    for campo in CAMPOS:
        if pa.get(campo) != pb.get(campo):
            lineas.append(f"{_ETIQUETAS[campo]}: {_texto(campo, pa.get(campo))} → {_texto(campo, pb.get(campo))}")

    viejos = list(a.get("pasos") or [])
    nuevos = list(b.get("pasos") or [])
    # 1) pasos idénticos: se emparejan y no cuentan como cambio
    for p in list(viejos):
        if p in nuevos:
            viejos.remove(p)
            nuevos.remove(p)
    # 2) mismo texto pero otros datos (sección, producto, día…): paso cambiado
    for p in list(viejos):
        igual = next((q for q in nuevos if q["texto"] == p["texto"]), None)
        if igual:
            viejos.remove(p)
            nuevos.remove(igual)
            lineas.append(f"Paso cambiado: {p['texto']} → {_cambios_paso(p, igual)}")
    # 3) texto parecido: paso reescrito
    for p in list(viejos):
        mejor, razon = None, 0.0
        for q in nuevos:
            r = SequenceMatcher(None, (p["texto"] or "").lower(), (q["texto"] or "").lower()).ratio()
            if r > razon:
                mejor, razon = q, r
        if mejor is not None and razon >= 0.6:
            viejos.remove(p)
            nuevos.remove(mejor)
            extra = _cambios_paso(p, mejor)
            lineas.append(f"Paso cambiado: {p['texto']} → {mejor['texto']}" + (f" ({extra})" if extra else ""))
    lineas += [f"Paso quitado: {p['texto']}{_detalle_paso(p)}" for p in viejos]
    lineas += [f"Paso añadido: {p['texto']}{_detalle_paso(p)}" for p in nuevos]

    # Orden: solo si los pasos que siguen igual en ambas versiones han cambiado de posición
    comunes_a = [p["texto"] for p in a.get("pasos") or [] if p["texto"] in {q["texto"] for q in b.get("pasos") or []}]
    comunes_b = [p["texto"] for p in b.get("pasos") or [] if p["texto"] in {q["texto"] for q in a.get("pasos") or []}]
    if comunes_a != comunes_b and sorted(comunes_a) == sorted(comunes_b):
        lineas.append("Orden de los pasos cambiado")
    return lineas


# ─────────────────────────── Guardar y consultar versiones ───────────────────────────

def nueva_version(ultima_version: dict | None, foto: dict, motivo: str, por: str | None) -> dict | None:
    """Fila de la versión que habría que guardar, o None si la foto no ha cambiado desde la última."""
    if ultima_version and ultima_version.get("snapshot") == foto:
        return None
    anterior = ultima_version.get("snapshot") if ultima_version else None
    return {"version": (ultima_version["version"] + 1) if ultima_version else 1, "motivo": motivo.strip(),
            "cambiado_por": por or None, "snapshot": foto, "resumen": "\n".join(diferencias(anterior, foto))}


def ultima(protocolo_id: str) -> dict | None:
    """Versión vigente (la más reciente) o None si no hay ninguna o falta la tabla."""
    try:
        filas = (db.table("procedimiento_versiones").select("*").eq("protocolo_id", protocolo_id)
                 .order("version", desc=True).limit(1).execute().data)
    except Exception:
        return None
    return filas[0] if filas else None


def listar(protocolo_id: str) -> list[dict]:
    """Todas las versiones, la más reciente primero (vacío si no hay o falta la tabla)."""
    try:
        return (db.table("procedimiento_versiones").select("*").eq("protocolo_id", protocolo_id)
                .order("version", desc=True).execute().data)
    except Exception:
        return []


def disponible() -> bool:
    """¿Existe ya la tabla de versiones en Supabase?"""
    try:
        db.table("procedimiento_versiones").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def numero_vigente(protocolo_id: str) -> int | None:
    v = ultima(protocolo_id)
    return v["version"] if v else None


def guardar_version(protocolo_id: str, motivo: str, por: str | None = None) -> dict | None:
    """Guarda una versión nueva con el estado actual, solo si ha cambiado desde la última (la primera es la v1).
    Devuelve la fila creada, o None si no había cambios o falta la tabla."""
    try:
        fila = nueva_version(ultima(protocolo_id), snapshot(protocolo_id), motivo, por)
        if not fila:
            return None
        creada = db.table("procedimiento_versiones").insert({"protocolo_id": protocolo_id, **fila}).execute().data[0]
    except Exception:
        return None
    try:   # la «versión» del propio procedimiento queda al día
        db.table("protocolos").update({"version": f"v{creada['version']}"}).eq("id", protocolo_id).execute()
    except Exception:
        pass
    return creada


# ─────────────────────────── Para imprimir y firmar ───────────────────────────

def _fecha_hora(valor) -> str:
    return f"{plan.fecha_es(valor)}" if valor else "—"


def como_markdown(version: dict, vigente_hasta=None) -> str:
    """Texto en Markdown de una versión, para imprimir y firmar."""
    foto = version.get("snapshot") or {}
    datos, pasos = foto.get("protocolo") or {}, foto.get("pasos") or []
    desde = _fecha_hora(version.get("created_at"))
    titulo = f"# Procedimiento {datos.get('nombre', '')} · versión {version['version']} · vigente desde {desde}"
    lineas = [titulo, ""]
    if vigente_hasta:
        lineas += [f"*Sustituida el {_fecha_hora(vigente_hasta)} por una versión posterior.*", ""]
    lineas += [f"- **Categoría:** {_texto('categoria', datos.get('categoria'))}",
               f"- **Cuándo toca:** {plan.describir_frecuencia(datos)}"
               + (f" · {plan.texto_franja(datos)}" if plan.texto_franja(datos) else "")]
    if datos.get("hora_limite"):
        lineas.append(f"- **Hora límite:** {datos['hora_limite']}")
    lineas += [f"- **Motivo del cambio:** {version.get('motivo') or '—'}",
               f"- **Cambiado por:** {version.get('cambiado_por') or '—'}"]
    if datos.get("descripcion"):
        lineas += ["", datos["descripcion"]]
    lineas += ["", "## Pasos", ""]
    seccion, n = object(), 0
    for p in pasos:
        if p.get("seccion") != seccion:
            seccion = p.get("seccion")
            if seccion:
                lineas += ["", f"### {seccion}", ""]
        n += 1
        lineas.append(f"{n}. {p['texto']}{_detalle_paso({**p, 'seccion': None})}")
    if not pasos:
        lineas.append("*Sin pasos.*")
    if version.get("resumen"):
        lineas += ["", "## Cambios respecto a la versión anterior", ""] + [f"- {x}" for x in version["resumen"].split("\n")]
    lineas += ["", "---", "", "Revisado y aprobado por: ____________________    Fecha: ____ / ____ / ________", ""]
    return "\n".join(lineas)
