"""Inspecciones (como SafetyCulture / iAuditor): plantillas de preguntas, puntuación y no conformidades.

Una plantilla es una lista de preguntas agrupadas por secciones. Cuatro tipos de pregunta:
  · texto     → instrucción o encabezado, sin respuesta
  · casilla   → marcar (hecho / no hecho)
  · si_no     → Sí / No / N/A (el «verdadero/falso» de las auditorías)
  · respuesta → texto corto («Tiempo de espera hasta la comanda (min)»)

Las plantillas oficiales (sanidad/APPCC, PRL, emergencias, calidad) viven aquí como datos de Python y se cargan
en Supabase la primera vez. Cualquier protocolo del local se puede inspeccionar sin preparar nada: cada paso se
convierte en «¿Correcto?» (desde_protocolo).
"""
from datetime import date, datetime, timezone

from core import db

FALTA_TABLA = "Falta ejecutar supabase/inspecciones.sql en Supabase."

TIPOS_PREGUNTA = {"texto": "Texto", "casilla": "Casilla", "si_no": "Verdadero/Falso", "respuesta": "Respuesta corta"}
TIPOS_PLANTILLA = {
    "sanidad": "🧪 Sanidad (APPCC)", "prl": "🦺 Riesgos laborales (PRL)", "emergencias": "🧯 Emergencias y PCI",
    "calidad": "⭐ Calidad y cliente", "rutina": "📋 Rutina", "personalizada": "✏️ Personalizada",
}
VALORES = {"si": "Sí", "no": "No", "na": "N/A", "true": "✔", "false": "—"}
FALLA = ("no", "false")            # valores que son una no conformidad
PUNTUABLES = ("si_no", "casilla")


# ─────────────────────────── Plantillas oficiales ───────────────────────────
# Cada pregunta: (enunciado, ayuda, crítica, tipo, puntúa, obligatoria). Con _p() solo se escribe lo que cambia.

def _p(enunciado: str, ayuda: str | None = None, critica: bool = False, tipo: str = "si_no",
       puntua: bool = True, obligatoria: bool = True) -> dict:
    return {"enunciado": enunciado, "ayuda": ayuda, "critica": critica, "tipo": tipo,
            "puntua": puntua and tipo in PUNTUABLES, "obligatoria": obligatoria and tipo != "texto"}


def _texto(enunciado: str) -> dict:
    return _p(enunciado, tipo="texto")


OFICIALES = [
    {
        "nombre": "Inspección sanitaria (APPCC)", "tipo": "sanidad",
        "descripcion": "Como la visita de un inspector de sanidad: instalaciones, higiene, temperaturas, "
                       "trazabilidad, alérgenos y registros del APPCC.",
        "secciones": [
            ("Antes de empezar", [
                _texto("Recorre el local como lo haría el inspector: recepción → almacén → cámaras → cocina → sala "
                       "→ aseos. Marca N/A lo que no aplique y anota en cada «No» qué se ha visto."),
            ]),
            ("Instalaciones y mantenimiento", [
                _p("Suelos, paredes y techos en buen estado: lisos, lavables, sin desconchados ni humedades",
                   "Reglamento (CE) 852/2004, anexo II (requisitos de los locales)."),
                _p("Lavamanos en la zona de manipulación con agua caliente, jabón y papel de un solo uso",
                   "Grifo de accionamiento no manual: lo exige la normativa de la mayoría de comunidades."),
                _p("Equipos y utensilios en buen estado y de materiales aptos para uso alimentario"),
                _p("Campana y filtros de extracción limpios, sin grasa acumulada ni condensación"),
            ]),
            ("Limpieza y desinfección", [
                _p("Zonas, superficies y equipos limpios en el momento de la visita"),
                _p("Plan de limpieza implantado y registros de limpieza al día"),
                _p("Productos de limpieza identificados, con ficha técnica y guardados aparte de los alimentos"),
                _p("Se evita la contaminación cruzada: tablas y utensilios diferenciados para crudo y cocinado"),
            ]),
            ("Control de plagas", [
                _p("Sin indicios de plagas (excrementos, roeduras, insectos vivos o muertos)", critica=True),
                _p("Contrato con empresa de control de plagas inscrita en el ROESB, con certificados y plano de cebos",
                   "ROESB: Registro Oficial de Establecimientos y Servicios Biocidas."),
                _p("Mosquiteras en las ventanas que se abren y puertas al exterior bien ajustadas"),
            ]),
            ("Agua", [
                _p("Agua de la red pública (o con controles de potabilidad) y filtros/descalcificadores mantenidos",
                   "Real Decreto 3/2023, de criterios de calidad del agua de consumo."),
                _p("Hielo hecho con agua potable, máquina limpia y pala guardada fuera del hielo"),
            ]),
            ("Temperaturas y cadena de frío", [
                _p("Refrigeración entre 0 y 4 °C y congelación a −18 °C o menos, con termómetro visible",
                   "Valores de referencia del plan APPCC; compruébalo con un termómetro propio.", critica=True),
                _p("Temperatura medida en la cámara de refrigeración (°C)", tipo="respuesta"),
                _p("Registros diarios de temperatura completos, con acción correctora cuando hay desvíos"),
                _p("Descongelación en refrigeración y comida caliente mantenida a 65 °C o más", critica=True),
            ]),
            ("Trazabilidad y etiquetado", [
                _p("Ningún alimento caducado en cámaras, almacén ni zona de trabajo", critica=True),
                _p("Elaboraciones, abiertos y descongelados etiquetados con producto, fecha y fecha límite",
                   "La etiquetadora de LilOS cubre este punto.", critica=True),
                _p("Albaranes y etiquetas de origen guardados: se puede saber el proveedor de cada producto",
                   "Reglamento (CE) 178/2002 (trazabilidad)."),
                _p("Almacén ordenado: nada en el suelo, rotación FIFO y crudo por debajo de lo cocinado"),
            ]),
            ("Alérgenos", [
                _p("Información de los 14 alérgenos disponible para el cliente y actualizada (carta, cartel o ficha)",
                   "Reglamento (UE) 1169/2011 y Real Decreto 126/2015 (alimentos sin envasar).", critica=True),
                _p("Fichas de platos con alérgenos al día y el personal sabe responder y evitar el contacto cruzado"),
            ]),
            ("Manipuladores, higiene personal y formación", [
                _p("Ropa de trabajo limpia, pelo recogido, sin joyas y heridas tapadas con apósito impermeable"),
                _p("Formación en higiene alimentaria acreditada para todo el personal que manipula",
                   "Reglamento (CE) 852/2004, anexo II, capítulo XII (formación)."),
            ]),
            ("Residuos", [
                _p("Cubos con tapa de pedal en cocina, vaciados con frecuencia; aceite usado retirado por gestor "
                   "autorizado"),
            ]),
            ("Documentación y registros del APPCC", [
                _p("Plan APPCC (o sistema basado en sus principios) disponible, actualizado y aplicado",
                   "Reglamento (CE) 852/2004."),
                _p("Registros de proveedores, mantenimiento y formación al día y firmados"),
            ]),
        ],
    },
    {
        "nombre": "Prevención de riesgos laborales (PRL)", "tipo": "prl",
        "descripcion": "Como la visita de un técnico de prevención o de la Inspección de Trabajo: gestión de la "
                       "prevención, riesgos de cocina y sala, químicos, electricidad y evacuación.",
        "secciones": [
            ("Gestión de la prevención", [
                _p("Evaluación de riesgos de los puestos hecha y actualizada", "Ley 31/1995 de PRL."),
                _p("Cada persona ha recibido información y formación sobre los riesgos de su puesto (registro firmado)"),
                _p("Se ofrece la vigilancia de la salud (reconocimiento médico) a todo el equipo"),
                _p("Coordinación de actividades con las contratas (limpieza, mantenimiento, plagas…)",
                   "Real Decreto 171/2004 (coordinación de actividades empresariales)."),
            ]),
            ("Cocina y sala", [
                _p("Suelos secos y sin obstáculos; los derrames se limpian al momento"),
                _p("Calzado cerrado y antideslizante en cocina y office"),
                _p("Equipos de protección disponibles y en buen estado: guante anticorte, manoplas térmicas, "
                   "guantes para químicos", "Real Decreto 773/1997 (equipos de protección individual)."),
                _p("Cuchillos afilados y guardados en soporte; guante de malla para mandolina y cortadora"),
                _p("Máquinas (cortadora, picadora, amasadora) con resguardos y paro de emergencia que funcionan",
                   "Real Decreto 1215/1997 (equipos de trabajo).", critica=True),
                _p("Freidoras sin sobrellenar, mangos hacia dentro y medio de extinción para aceite a mano"),
                _p("Lo pesado en estantes bajos y carro disponible para cargas",
                   "Real Decreto 487/1997 (manipulación manual de cargas)."),
            ]),
            ("Productos químicos", [
                _p("Químicos en su envase original etiquetado, nunca en botellas de bebida", critica=True),
                _p("Fichas de datos de seguridad accesibles para el equipo",
                   "Reglamento (CE) 1907/2006 (REACH)."),
            ]),
            ("Instalaciones y emergencias", [
                _p("Cuadro eléctrico cerrado y señalizado; sin cables pelados ni regletas sobrecargadas cerca del agua",
                   critica=True),
                _p("Cámaras frigoríficas con apertura desde dentro y alarma o avisador interior",
                   "Reglamento de seguridad para instalaciones frigoríficas (Real Decreto 552/2019).", critica=True),
                _p("Salidas y recorridos de evacuación libres y señalizados", critica=True),
                _p("Extintores revisados (etiqueta en vigor) y accesibles"),
                _p("Botiquín completo y sin material caducado",
                   "Real Decreto 486/1997 (lugares de trabajo)."),
            ]),
        ],
    },
    {
        "nombre": "Emergencias y protección contra incendios", "tipo": "emergencias",
        "descripcion": "Medios de extinción, señalización, alumbrado de emergencia, salidas y organización ante "
                       "una emergencia.",
        "secciones": [
            ("Antes de empezar", [
                _texto("Durante la visita, prueba el alumbrado de emergencia y abre cada salida."),
            ]),
            ("Medios de extinción", [
                _p("Extintores suficientes, visibles, señalizados y con la revisión trimestral y anual al día",
                   "Real Decreto 513/2017 (RIPCI): revisión trimestral del titular y anual de empresa mantenedora.",
                   critica=True),
                _p("En cocina, extintor adecuado para aceites (clase F) y de CO₂ junto al cuadro eléctrico"),
                _p("Extinción automática de la campana revisada (si la hay)"),
                _p("Bocas de incendio y detección/alarma revisadas (si las hay)", "Real Decreto 513/2017 (RIPCI)."),
            ]),
            ("Evacuación", [
                _p("Salidas de emergencia sin obstáculos y se abren fácilmente sin llave", critica=True),
                _p("Señalización de salidas y de extintores visible (fotoluminiscente)"),
                _p("Alumbrado de emergencia funciona al probarlo"),
            ]),
            ("Organización", [
                _p("El equipo sabe qué hacer: quién avisa, quién evacúa y dónde está el punto de encuentro",
                   "Ley 31/1995 de PRL (medidas de emergencia). El plan de autoprotección depende del aforo."),
                _p("Simulacro o formación de emergencias en el último año"),
                _p("Teléfono 112 y plano de evacuación visibles"),
                _p("Llave de corte del gas accesible y señalizada; revisión de la instalación de gas al día"),
            ]),
        ],
    },
    {
        "nombre": "Calidad y experiencia de cliente", "tipo": "calidad",
        "descripcion": "Visita de cliente misterioso: acogida, tiempos, servicio, producto e instalaciones.",
        "secciones": [
            ("Llegada y acogida", [
                _p("Tiempo hasta ser atendido al entrar (min)", tipo="respuesta"),
                _p("Saludo al momento, con sonrisa y contacto visual"),
                _p("Mesa, carta y cubiertos limpios y en buen estado"),
            ]),
            ("Servicio", [
                _p("Tiempo de espera hasta la comanda (min)", tipo="respuesta"),
                _p("Conoce la carta y recomienda (sugerencia del día, bebida, postre)"),
                _p("Pregunta por alergias o intolerancias"),
                _p("Tiempo desde la comanda hasta el primer plato (min)", tipo="respuesta"),
                _p("Atento sin agobiar: retira platos y ofrece algo más"),
            ]),
            ("Producto", [
                _p("Los platos salen como en la ficha: presentación, ración y temperatura"),
                _p("Café y bebidas correctos"),
            ]),
            ("Instalaciones", [
                _p("Aseos limpios, con papel y jabón"),
                _p("Música, luz y temperatura agradables"),
            ]),
            ("Despedida", [
                _p("Cuenta rápida y correcta; se despide al cliente"),
                _p("Nota general de la visita (1–10)", tipo="respuesta"),
                _p("Lo mejor y lo que hay que mejorar", tipo="respuesta", obligatoria=False),
            ]),
        ],
    },
]


def preguntas_oficial(oficial: dict) -> list[dict]:
    """Aplana las secciones de una plantilla oficial en filas de inspeccion_preguntas (con orden)."""
    filas = []
    for seccion, preguntas in oficial["secciones"]:
        for p in preguntas:
            filas.append({**p, "seccion": seccion, "orden": len(filas) + 1})
    return filas


# ─────────────────────────── Puntuación ───────────────────────────

def puntuar(preguntas: list[dict], respuestas: dict) -> dict:
    """respuestas: {pregunta_id: valor}. Cuentan si_no y casilla con «puntua»; N/A y sin responder no cuentan.
    Devuelve {puntos, maximo, porcentaje, criticas, respondidas, total}."""
    puntos = maximo = criticas = respondidas = total = 0
    for p in preguntas:
        if p["tipo"] not in PUNTUABLES:
            continue
        valor = respuestas.get(p["id"])
        if p["tipo"] == "casilla":
            valor = "true" if valor in (True, "true") else "false"
        total += 1
        if valor in (None, ""):
            continue
        respondidas += 1
        if valor in FALLA and p.get("critica"):
            criticas += 1
        if valor == "na" or not p.get("puntua", True):
            continue
        maximo += 1
        puntos += valor in ("si", "true")
    return {"puntos": puntos, "maximo": maximo, "porcentaje": round(100 * puntos / maximo, 1) if maximo else None,
            "criticas": criticas, "respondidas": respondidas, "total": total}


def resultado(porcentaje: float | None, criticas: int) -> str:
    """≥ 90 % sin críticas: Conforme · 70–89 %: Mejorable · < 70 % o alguna crítica: No conforme."""
    if criticas:
        return "No conforme"
    if porcentaje is None:
        return "Sin puntuar"
    if porcentaje >= 90:
        return "Conforme"
    return "Mejorable" if porcentaje >= 70 else "No conforme"


ICONO_RESULTADO = {"Conforme": "🟢", "Mejorable": "🟠", "No conforme": "🔴", "Sin puntuar": "⚪"}


def fallos(preguntas: list[dict], respuestas: dict, extras: dict | None = None) -> list[dict]:
    """Preguntas con «No» (o casilla sin marcar), con su comentario y acción correctiva. Las críticas, primero."""
    extras = extras or {}
    salida = []
    for p in preguntas:
        if p["tipo"] not in PUNTUABLES:
            continue
        valor = respuestas.get(p["id"])
        if p["tipo"] == "casilla":
            valor = "true" if valor in (True, "true") else "false"
        if valor in FALLA:
            salida.append({**p, **extras.get(p["id"], {})})
    return sorted(salida, key=lambda p: not p.get("critica"))


def pendientes(preguntas: list[dict], respuestas: dict) -> list[dict]:
    """Obligatorias sin responder (las casillas siempre tienen valor)."""
    return [p for p in preguntas if p.get("obligatoria", True) and p["tipo"] in ("si_no", "respuesta")
            and not str(respuestas.get(p["id"]) or "").strip()]


# ─────────────────────────── Rutinas (protocolos) como inspección ───────────────────────────

def desde_protocolo(protocolo: dict, pasos: list[dict] | None = None) -> dict:
    """Plantilla en memoria a partir de los pasos activos de un protocolo: cada paso es «¿Correcto?» (Sí/No/N/A).
    No hace falta prepararla; al guardar la inspección se guarda como plantilla de tipo «rutina»."""
    pasos = db.pasos(protocolo["id"]) if pasos is None else pasos
    preguntas = []
    for paso in sorted(pasos, key=lambda p: p.get("orden") or 0):
        if not paso.get("activo", True):
            continue
        texto = paso["texto"] + (f" ({paso['producto']})" if paso.get("producto") else "")
        preguntas.append({"id": f"paso-{paso['id']}", "orden": len(preguntas) + 1, "seccion": paso.get("seccion"),
                          "tipo": "si_no", "enunciado": texto, "ayuda": "¿Correcto?", "obligatoria": True,
                          "critica": False, "puntua": True})
    return {"id": None, "nombre": f"Rutina · {protocolo['nombre']}", "tipo": "rutina",
            "descripcion": protocolo.get("descripcion"), "local_id": protocolo.get("local_id"),
            "protocolo_id": protocolo["id"], "predefinida": False, "activo": True, "preguntas": preguntas}


# ─────────────────────────── Base de datos ───────────────────────────

def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _campos_pregunta(p: dict) -> dict:
    return {k: p.get(k) for k in ("orden", "seccion", "tipo", "enunciado", "ayuda", "obligatoria", "critica", "puntua")}


def plantillas(local_id: str | None = None, solo_activas: bool = True) -> list[dict]:
    """Plantillas de todos los locales y las del local (lanza excepción si falta la tabla: la página lo avisa)."""
    query = db.table("inspeccion_plantillas").select("*").order("nombre")
    if local_id:
        query = query.or_(f"local_id.eq.{local_id},local_id.is.null")
    if solo_activas:
        query = query.eq("activo", True)
    return query.execute().data


def preguntas(plantilla_id: str) -> list[dict]:
    return (db.table("inspeccion_preguntas").select("*").eq("plantilla_id", plantilla_id)
            .order("orden").execute().data)


def cuenta_preguntas(plantilla_ids: list[str]) -> dict[str, int]:
    if not plantilla_ids:
        return {}
    cuenta = {}
    for f in db.table("inspeccion_preguntas").select("plantilla_id, tipo").in_("plantilla_id", plantilla_ids) \
            .execute().data:
        if f["tipo"] != "texto":
            cuenta[f["plantilla_id"]] = cuenta.get(f["plantilla_id"], 0) + 1
    return cuenta


def crear_plantilla(datos: dict, filas: list[dict]) -> dict:
    plantilla = db.table("inspeccion_plantillas").insert(datos).execute().data[0]
    if filas:
        db.table("inspeccion_preguntas").insert(
            [{**_campos_pregunta(p), "plantilla_id": plantilla["id"]} for p in filas]).execute()
    return plantilla


def cargar_oficiales(existentes: list[dict] | None = None) -> int:
    """Crea las plantillas oficiales que falten (por nombre). Se puede repetir: no duplica. Devuelve cuántas creó."""
    if existentes is None:
        existentes = plantillas(solo_activas=False)
    ya = {p["nombre"] for p in existentes if p.get("predefinida")}
    creadas = 0
    for oficial in OFICIALES:
        if oficial["nombre"] in ya:
            continue
        crear_plantilla({"nombre": oficial["nombre"], "tipo": oficial["tipo"], "descripcion": oficial["descripcion"],
                         "predefinida": True, "creado_por": "LilOS"}, preguntas_oficial(oficial))
        creadas += 1
    return creadas


def duplicar(plantilla: dict, filas: list[dict], nombre: str, creado_por: str, local_id: str | None) -> dict:
    """Copia editable (las oficiales no se tocan: se duplican y se adapta la copia)."""
    tipo = "personalizada" if plantilla.get("tipo") == "rutina" else plantilla.get("tipo") or "personalizada"
    return crear_plantilla({"nombre": nombre, "tipo": tipo, "descripcion": plantilla.get("descripcion"),
                            "local_id": local_id, "predefinida": False, "creado_por": creado_por}, filas)


def actualizar_plantilla(plantilla_id: str, cambios: dict) -> None:
    db.table("inspeccion_plantillas").update(cambios).eq("id", plantilla_id).execute()


def cambios_preguntas(originales: list[dict], editadas: list[dict]) -> tuple[list[dict], list[tuple[str, dict]], list[str]]:
    """Compara la tabla editada con la guardada: (altas, cambios [(id, datos)], bajas). Las filas nuevas sin orden
    van al final; las vacías se ignoran; sin tipo, Verdadero/Falso."""
    por_id = {p["id"]: p for p in originales}
    siguiente = max([int(f.get("orden") or 0) for f in editadas] + [0]) + 1
    altas, cambios, vistos = [], [], set()
    for fila in editadas:
        if not str(fila.get("enunciado") or "").strip():
            continue
        datos = _campos_pregunta(fila)
        datos["enunciado"] = datos["enunciado"].strip()
        datos["tipo"] = datos.get("tipo") or "si_no"
        datos["obligatoria"] = bool(datos.get("obligatoria")) if datos.get("obligatoria") is not None else True
        datos["critica"] = bool(datos.get("critica"))
        datos["puntua"] = datos["tipo"] in PUNTUABLES if datos.get("puntua") is None else bool(datos["puntua"])
        if not datos.get("orden"):
            datos["orden"] = siguiente
            siguiente += 1
        datos["orden"] = int(datos["orden"])
        ident = fila.get("id")
        if isinstance(ident, str) and ident in por_id:
            vistos.add(ident)
            if any(datos.get(k) != por_id[ident].get(k) for k in datos):
                cambios.append((ident, datos))
        else:
            altas.append(datos)
    return altas, cambios, [i for i in por_id if i not in vistos]


def guardar_preguntas(plantilla_id: str, altas: list[dict], cambios: list[tuple[str, dict]], bajas: list[str]) -> None:
    for ident, datos in cambios:
        db.table("inspeccion_preguntas").update(datos).eq("id", ident).execute()
    if altas:
        db.table("inspeccion_preguntas").insert([{**a, "plantilla_id": plantilla_id} for a in altas]).execute()
    for ident in bajas:
        db.table("inspeccion_preguntas").delete().eq("id", ident).execute()


def asegurar_rutina(plantilla: dict, creado_por: str) -> tuple[str, dict[str, str]]:
    """Guarda (o pone al día) la plantilla de tipo «rutina» de un protocolo. Devuelve su id y el paso de los ids
    provisionales («paso-…») a los ids reales de las preguntas."""
    existentes = db.table("inspeccion_plantillas").select("*").eq("protocolo_id", plantilla["protocolo_id"]) \
        .eq("tipo", "rutina").execute().data
    if existentes:
        plantilla_id = existentes[0]["id"]
        guardadas = preguntas(plantilla_id)
    else:
        plantilla_id = db.table("inspeccion_plantillas").insert({
            "nombre": plantilla["nombre"], "tipo": "rutina", "descripcion": plantilla.get("descripcion"),
            "local_id": plantilla.get("local_id"), "protocolo_id": plantilla["protocolo_id"],
            "predefinida": False, "creado_por": creado_por}).execute().data[0]["id"]
        guardadas = []
    por_texto = {(g.get("seccion"), g["enunciado"]): g for g in guardadas}
    ids, usadas = {}, set()
    for p in plantilla["preguntas"]:
        g = por_texto.get((p.get("seccion"), p["enunciado"]))
        if g and g["id"] not in usadas:
            usadas.add(g["id"])
            if g.get("orden") != p["orden"]:
                db.table("inspeccion_preguntas").update({"orden": p["orden"]}).eq("id", g["id"]).execute()
        else:
            g = db.table("inspeccion_preguntas").insert({**_campos_pregunta(p), "plantilla_id": plantilla_id}) \
                .execute().data[0]
        ids[p["id"]] = g["id"]
    for g in guardadas:   # pasos que ya no están en el protocolo (el historial guarda su copia)
        if g["id"] not in usadas:
            db.table("inspeccion_preguntas").delete().eq("id", g["id"]).execute()
    return plantilla_id, ids


def guardar_inspeccion(plantilla: dict, filas: list[dict], respuestas: dict, extras: dict, local_id: str,
                       inspector: str, fecha: date, notas: str | None = None) -> dict:
    """Guarda la inspección cerrada con sus respuestas. Si viene de una rutina, guarda antes su plantilla."""
    ids = {p["id"]: p["id"] for p in filas}
    plantilla_id = plantilla.get("id")
    if plantilla.get("tipo") == "rutina" and not plantilla_id:
        plantilla_id, ids = asegurar_rutina({**plantilla, "preguntas": filas}, inspector)
    nota = puntuar(filas, respuestas)
    inspeccion = db.table("inspecciones").insert({
        "plantilla_id": plantilla_id, "plantilla": plantilla["nombre"], "local_id": local_id,
        "inspector": inspector or None, "fecha": fecha.isoformat(), "estado": "cerrada",
        "puntos": nota["puntos"], "maximo": nota["maximo"], "porcentaje": nota["porcentaje"],
        "criticas": nota["criticas"], "notas": (notas or "").strip() or None, "cerrada_en": _ahora(),
    }).execute().data[0]
    filas_respuesta = []
    for p in filas:
        if p["tipo"] == "texto":
            continue
        valor = respuestas.get(p["id"])
        if p["tipo"] == "casilla":
            valor = "true" if valor in (True, "true") else "false"
        extra = extras.get(p["id"], {})
        filas_respuesta.append({
            "inspeccion_id": inspeccion["id"], "pregunta_id": ids.get(p["id"]),
            "valor": (str(valor).strip() or None) if valor is not None else None,
            "comentario": (extra.get("comentario") or "").strip() or None,
            "accion_correctiva": (extra.get("accion_correctiva") or "").strip() or None,
            "seccion": p.get("seccion"), "tipo": p["tipo"], "enunciado": p["enunciado"],
            "critica": bool(p.get("critica")),
        })
    if filas_respuesta:
        db.table("inspeccion_respuestas").insert(filas_respuesta).execute()
    return inspeccion


def inspecciones(local_id: str | None = None, limite: int = 300) -> list[dict]:
    query = db.table("inspecciones").select("*").order("fecha", desc=True).order("created_at", desc=True) \
        .limit(limite)
    if local_id:
        query = query.eq("local_id", local_id)
    return query.execute().data


def respuestas(inspeccion_id: str) -> list[dict]:
    return db.table("inspeccion_respuestas").select("*").eq("inspeccion_id", inspeccion_id).execute().data


# ─────────────────────────── Informe y encargo ───────────────────────────

def _fecha_es(valor) -> str:
    return date.fromisoformat(str(valor)[:10]).strftime("%d/%m/%Y")


def respuestas_como_preguntas(filas: list[dict]) -> tuple[list[dict], dict, dict]:
    """Del historial (copia de cada pregunta) a (preguntas, respuestas, extras) para puntuar y listar fallos."""
    preguntas_, valores, extras = [], {}, {}
    for r in filas:
        preguntas_.append({"id": r["id"], "seccion": r.get("seccion"), "tipo": r.get("tipo") or "si_no",
                           "enunciado": r.get("enunciado") or "", "critica": bool(r.get("critica")), "puntua": True})
        valores[r["id"]] = r.get("valor")
        extras[r["id"]] = {"comentario": r.get("comentario"), "accion_correctiva": r.get("accion_correctiva")}
    return preguntas_, valores, extras


def informe_md(inspeccion: dict, filas: list[dict], local: str = "") -> str:
    """Informe en markdown de una inspección guardada (para descargar o enviar)."""
    pct, criticas = inspeccion.get("porcentaje"), inspeccion.get("criticas") or 0
    res = resultado(float(pct) if pct is not None else None, criticas)
    lineas = [f"# {inspeccion.get('plantilla') or 'Inspección'}", "",
              f"- **Local:** {local or inspeccion.get('local_id') or '—'}",
              f"- **Fecha:** {_fecha_es(inspeccion['fecha'])}",
              f"- **Inspector/a:** {inspeccion.get('inspector') or '—'}",
              f"- **Resultado:** {res}" + (f" · {float(pct):g} %" if pct is not None else "")
              + f" · {criticas} crítica(s)", ""]
    preguntas_, valores, extras = respuestas_como_preguntas(filas)
    malas = fallos(preguntas_, valores, extras)
    if malas:
        lineas += ["## No conformidades", ""]
        for m in malas:
            lineas.append(f"- {'**CRÍTICA** · ' if m.get('critica') else ''}{m.get('seccion') or ''}"
                          f"{' · ' if m.get('seccion') else ''}{m['enunciado']}")
            if m.get("comentario"):
                lineas.append(f"  - Observación: {m['comentario']}")
            if m.get("accion_correctiva"):
                lineas.append(f"  - Acción correctiva: {m['accion_correctiva']}")
        lineas.append("")
    lineas += ["## Respuestas", ""]
    seccion = object()
    for p in preguntas_:
        if p.get("seccion") != seccion:
            seccion = p.get("seccion")
            if seccion:
                lineas += ["", f"### {seccion}", ""]
        valor = valores.get(p["id"])
        texto = VALORES.get(valor, valor) if p["tipo"] in PUNTUABLES else (valor or "—")
        lineas.append(f"- {p['enunciado']}: **{texto or '—'}**")
    if inspeccion.get("notas"):
        lineas += ["", "## Notas", "", inspeccion["notas"]]
    return "\n".join(lineas) + "\n"


def texto_encargo(nombre: str, fecha: date, nota: dict, malas: list[dict]) -> tuple[str, str]:
    """(título, contenido markdown) del encargo de Rumbo con una casilla por cada cosa que falla."""
    titulo = f"Corregir: {nombre} {fecha.strftime('%d/%m/%Y')}"
    cabecera = f"Inspección «{nombre}» del {fecha.strftime('%d/%m/%Y')}"
    if nota.get("porcentaje") is not None:
        cabecera += f" · {nota['porcentaje']:g} %"
    cabecera += f" · {resultado(nota.get('porcentaje'), nota.get('criticas', 0))}"
    lineas = [cabecera, ""]
    for m in malas:
        linea = f"- [ ] {'🔴 ' if m.get('critica') else ''}{m['enunciado']}"
        if m.get("accion_correctiva"):
            linea += f" → {m['accion_correctiva'].strip()}"
        elif m.get("comentario"):
            linea += f" ({m['comentario'].strip()})"
        lineas.append(linea)
    return titulo, "\n".join(lineas)
