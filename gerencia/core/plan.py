"""Cálculo de fechas del plan de mantenimiento y estado de las alertas."""
from datetime import date, time, timedelta

from dateutil.relativedelta import relativedelta

FRECUENCIAS = {
    "semanal": relativedelta(weeks=1),
    "quincenal": relativedelta(weeks=2),
    "mensual": relativedelta(months=1),
    "trimestral": relativedelta(months=3),
    "cuatrimestral": relativedelta(months=4),
    "semestral": relativedelta(months=6),
    "anual": relativedelta(years=1),
    "quinquenal": relativedelta(years=5),
}

# Revisiones de equipos y servicios: además de las periódicas, las que no tienen fecha fija
SIN_PERIODO = {"segun_fabricante": "Según fabricante", "segun_contrato": "Según contrato", "a_demanda": "A demanda"}
FRECUENCIAS_REVISION = {**{f: f.capitalize() for f in FRECUENCIAS}, **SIN_PERIODO}

# Desplegable de planificación: hasta qué fecha mirar
HORIZONTES = {
    "Esta semana": relativedelta(weeks=1),
    "Este mes": relativedelta(months=1),
    "Este trimestre": relativedelta(months=3),
}

# Si una tarea lleva más de estos días de retraso, pasa a los directivos
DIAS_ESCALADO = 7

TIPOS_EQUIPO = ["Nevera", "Congelador", "Cámara frigorífica", "Mesa refrigerada", "Abatidor", "Horno", "Freidora",
                "Plancha", "Gofrera", "Fogón / cocina", "Microondas", "Batidora / amasadora", "Lavavajillas",
                "Cafetera", "Molino de café", "Filtro de agua", "Máquina de hielo", "Campana extractora", "Lavamanos",
                "Mesón / mesa de trabajo", "Estantería", "Otro"]

CATEGORIAS_SERVICIO = {
    "frio": "❄️ Frío (friorista)", "maquinaria": "🔧 Maquinaria", "cafetera": "☕ Cafetera", "agua": "💧 Agua y filtros",
    "plagas": "🐀 Control de plagas (DDD)", "extintores": "🧯 Extintores y PCI", "climatizacion": "🌬️ Climatización",
    "electricidad": "⚡ Electricidad", "fontaneria": "🚰 Fontanería", "campana": "🔥 Campana y conductos",
    "otro": "📌 Otro",
}

TIPOS_PROTOCOLO = {
    "apertura": "🌅 Apertura", "cierre": "🌙 Cierre", "limpieza": "🧽 Limpieza", "averia": "🚨 Avería",
    "maquinaria": "⚙️ Maquinaria", "otro": "📋 Otro",
}

DIAS_SEMANA = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes", 6: "Sábado", 7: "Domingo"}

TIPOS_EVENTO = {
    "mantenimiento": "Mantenimiento",
    "inspeccion": "Inspección / revisión",
    "limpieza": "Limpieza",
    "reparacion": "Reparación",
    "averia": "Avería",
    "cambio_pieza": "Cambio de pieza",
    "otro": "Otro",
}

ESTADOS_EQUIPO = {
    "operativo": "🟢 Operativo",
    "averiado": "🔴 Averiado",
    "en_reparacion": "🟠 En reparación",
    "baja": "⚫ De baja",
}


def siguiente_fecha(desde: date, frecuencia: str) -> date:
    return desde + FRECUENCIAS[frecuencia]


def estado_tarea(proxima: date, hoy: date | None = None) -> tuple[str, str]:
    """Devuelve (icono, texto) según lo cerca o atrasada que esté la tarea."""
    hoy = hoy or date.today()
    dias = (proxima - hoy).days
    if dias < -DIAS_ESCALADO:
        return "🚨", f"Atrasada {-dias} días · escalada a dirección"
    if dias < 0:
        return "🔴", f"Atrasada {-dias} día{'s' if dias != -1 else ''}"
    if dias == 0:
        return "🟠", "Vence hoy"
    if dias <= 7:
        return "🟡", f"En {dias} día{'s' if dias != 1 else ''}"
    return "🟢", f"En {dias} días"


def proxima_revision(ultima: date | None, frecuencia: str | None) -> date | None:
    """Próxima revisión recomendada a partir de la última (solo si la frecuencia es periódica)."""
    return siguiente_fecha(ultima, frecuencia) if ultima and frecuencia in FRECUENCIAS else None


def semana_del_mes(dia: date) -> int:
    return (dia.day - 1) // 7 + 1


def paso_toca(paso: dict, dia: date) -> bool:
    """Un paso de protocolo toca hoy si no tiene día de la semana / semana del mes, o si coinciden."""
    return ((not paso.get("dia_semana") or paso["dia_semana"] == dia.isoweekday())
            and (not paso.get("semana_mes") or paso["semana_mes"] == semana_del_mes(dia)))


# ── Procedimientos (POE del APPCC) y rutinas: categoría, frecuencia (como en iAuditor) y momento del día ──
CATEGORIAS = {"appcc": "📋 Procedimiento (POE)", "rutina": "🔁 Rutina"}
FRECUENCIAS_POE = {"diaria": "Diaria", "semanal": "Semanal", "mensual": "Mensual", "trimestral": "Trimestral",
                   "anual": "Anual"}
FRANJAS = {"apertura": "🌅 Apertura", "turno": "☀️ Durante el turno", "cierre": "🌙 Cierre"}
DIAS_CORTOS = {1: "L", 2: "M", 3: "X", 4: "J", 5: "V", 6: "S", 7: "D"}
SEMANAS_MES = {1: "1ª", 2: "2ª", 3: "3ª", 4: "4ª", 5: "última"}   # 5 = los últimos 7 días del mes
MESES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun", 7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct",
         11: "Nov", 12: "Dic"}
MESES_TRIMESTRE = {1: "1º (ene·abr·jul·oct)", 2: "2º (feb·may·ago·nov)", 3: "3º (mar·jun·sep·dic)"}
_ORDEN_FRANJA = {"apertura": 0, "turno": 1, None: 1, "cierre": 2}
_CLAVES_APPCC = ("aseo", "baño", "bano", "limpieza", "temperatura", "averia", "avería")


def categoria(protocolo: dict) -> str:
    """'appcc' o 'rutina'. Si la columna aún no existe (antes de procedimientos.sql), se deduce igual que el SQL."""
    if protocolo.get("categoria") in CATEGORIAS:
        return protocolo["categoria"]
    if protocolo.get("tipo") in ("apertura", "cierre"):
        return "rutina"
    texto = f"{protocolo.get('nombre', '')} {protocolo.get('tipo', '')}".lower()
    return "appcc" if any(c in texto for c in _CLAVES_APPCC) else "rutina"


def franja(protocolo: dict) -> str | None:
    """Apertura, durante el turno o cierre. Sin la columna, se deduce del tipo (apertura / cierre)."""
    if "franja" in protocolo:
        return protocolo["franja"] if protocolo["franja"] in FRANJAS else None
    return protocolo.get("tipo") if protocolo.get("tipo") in ("apertura", "cierre") else None


def texto_franja(protocolo: dict) -> str | None:
    """«Durante el turno», «Cierre»… sin icono; nada si ya lo dice el nombre (la Apertura es de apertura)."""
    valor = franja(protocolo)
    if not valor or valor in protocolo.get("nombre", "").lower():
        return None
    return FRANJAS[valor].split(" ", 1)[1]


def orden_franja(protocolo: dict) -> int:
    return _ORDEN_FRANJA.get(franja(protocolo), 1)


def _ultimo_dia_mes(dia: date) -> date:
    return dia + relativedelta(day=31)


def ventana(protocolo: dict, dia: date) -> tuple[date, date] | None:
    """Días en que toca el procedimiento alrededor de `dia`: (desde, hasta), o None si ese día no toca.
    Diaria y semanal: solo ese día. Mensual, trimestral y anual: desde el día del mes elegido hasta fin de mes, o
    la semana elegida (o el mes entero si no hay ninguno); se queda pendiente toda esa ventana hasta que alguien
    lo registra. Si hay día del mes y semana a la vez, manda el día del mes.
    Sin columnas nuevas (antes de procedimientos.sql) todo es diario."""
    frecuencia = protocolo.get("frecuencia") or "diaria"
    if frecuencia == "semanal":
        dias = protocolo.get("dias_semana") or []
        return (dia, dia) if not dias or dia.isoweekday() in dias else None
    if frecuencia not in ("mensual", "trimestral", "anual"):
        return dia, dia
    mes = protocolo.get("mes_periodo")
    if frecuencia == "trimestral" and mes and (dia.month - 1) % 3 + 1 != mes:
        return None
    if frecuencia == "anual" and mes and dia.month != mes:
        return None
    inicio, fin = dia.replace(day=1), _ultimo_dia_mes(dia)
    semana = protocolo.get("semana_mes")
    if protocolo.get("dia_mes"):   # día concreto del mes (manda sobre la semana): desde ese día hasta fin de mes
        inicio = dia.replace(day=min(protocolo["dia_mes"], fin.day))   # mes corto: el último día
    elif semana == 5:   # la última semana: los últimos 7 días del mes
        inicio = fin - timedelta(days=6)
    elif semana:
        inicio = dia.replace(day=(semana - 1) * 7 + 1)
        fin = inicio + timedelta(days=6)
    return (inicio, fin) if inicio <= dia <= fin else None


def procedimiento_toca(protocolo: dict, dia: date) -> bool:
    """Si el procedimiento toca ese día según su frecuencia. Cada paso, además, tiene su propia regla (paso_toca)."""
    return ventana(protocolo, dia) is not None


def veces_dia(protocolo: dict) -> int:
    """Cuántas veces al día hay que hacerlo (1–6). Solo cuenta en diarias y semanales; sin la columna, 1."""
    if (protocolo.get("frecuencia") or "diaria") not in ("diaria", "semanal"):
        return 1
    try:
        return max(1, min(6, int(protocolo.get("veces_dia") or 1)))
    except (TypeError, ValueError):
        return 1


def texto_veces(protocolo: dict) -> str | None:
    """«2 veces al día» (nada si es una sola vez)."""
    veces = veces_dia(protocolo)
    return f"{veces} veces al día" if veces > 1 else None


def hora_limite(protocolo: dict) -> time | None:
    valor = protocolo.get("hora_limite")
    if not valor:
        return None
    return valor if isinstance(valor, time) else time.fromisoformat(str(valor)[:8])


def describir_frecuencia(protocolo: dict) -> str:
    """Texto corto: «Diaria», «Semanal · L X V», «Mensual · 2ª semana», «Anual · Mar, última semana»…"""
    frecuencia = protocolo.get("frecuencia") or "diaria"
    texto = FRECUENCIAS_POE.get(frecuencia, "Diaria")
    partes = []
    if frecuencia == "semanal" and protocolo.get("dias_semana"):
        partes.append(" ".join(DIAS_CORTOS[d] for d in sorted(protocolo["dias_semana"])))
    if frecuencia == "trimestral" and protocolo.get("mes_periodo"):
        partes.append(f"{protocolo['mes_periodo']}º mes del trimestre")
    if frecuencia == "anual" and protocolo.get("mes_periodo"):
        partes.append(MESES[protocolo["mes_periodo"]])
    if frecuencia in ("mensual", "trimestral", "anual"):
        if protocolo.get("dia_mes"):
            partes.append(f"día {protocolo['dia_mes']}")
        elif protocolo.get("semana_mes"):
            partes.append(f"{SEMANAS_MES[protocolo['semana_mes']]} semana")
    if texto_veces(protocolo):
        partes.append(texto_veces(protocolo))
    return f"{texto} · {', '.join(partes)}" if partes else texto


def limite_horizonte(nombre: str, hoy: date | None = None) -> date:
    return (hoy or date.today()) + HORIZONTES[nombre]


def fecha_es(valor) -> str:
    if not valor:
        return "—"
    if isinstance(valor, str):
        valor = date.fromisoformat(valor[:10])
    return valor.strftime("%d/%m/%Y")


def hoy_mas(dias: int) -> date:
    return date.today() + timedelta(days=dias)
