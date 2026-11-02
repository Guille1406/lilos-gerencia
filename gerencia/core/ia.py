"""Asistente de IA de la app de gerencia, con modelos gratuitos.

Habla con cualquier proveedor compatible con la API de OpenAI (por defecto, el plan gratuito de Google Gemini; también
Groq, OpenRouter u Ollama en local), así que se cambia de modelo sin tocar código, solo la configuración:
    IA_API_KEY   clave del proveedor (si falta, se usa GEMINI_API_KEY)
    IA_BASE_URL  dirección del proveedor (por defecto, la de Gemini)
    IA_MODELOS   modelos a probar en orden, separados por comas (si uno está saturado se pasa al siguiente)
    TAVILY_API_KEY  opcional: búsquedas en internet (plan gratuito); sin ella se consulta la Wikipedia

Funciones: el asistente del gerente (chat que consulta la intranet y, si hace falta, internet), leer la placa de un
equipo desde una foto, sugerir su plan de mantenimiento, orientar ante una avería y resumir el estado del local.
"""
import base64
import io
import json
from datetime import date

import httpx
import openai
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError

from core import db, intranet, plan, registro

GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODELOS_GEMINI = "gemini-flash-lite-latest,gemini-3.5-flash-lite,gemini-flash-latest"

SISTEMA = (
    "Eres el asistente del gerente de Lilo Brunch, un grupo de tres restaurantes de brunch en España (Lilo Sagrada "
    "Familia y Lilo Enric Granados en Barcelona, Lilo Madrid). Conoces su intranet, LilOS: equipos y su "
    "mantenimiento, bitácora de averías y reparaciones, catálogo de productos con caducidades y alérgenos, "
    "etiquetas impresas (registro APPCC), servicios de mantenimiento (frío, plagas, extintores…), proveedores, "
    "productos de limpieza y protocolos del plan APPCC (apertura, cierre, limpieza) con sus registros firmados, personal y los "
    "encargos de Rumbo (órdenes, objetivos y proyectos de cada persona). Escribe en español de España, claro y "
    "práctico, para alguien que "
    "lo lee en el móvil en mitad del servicio. Ten siempre presente la seguridad alimentaria (APPCC). No inventes "
    "datos: si algo no está en la intranet ni lo encuentras, dilo."
)


class ErrorIA(Exception):
    """Error que se puede mostrar tal cual al usuario."""


def _fallo(mensaje: str, nivel: str = "error") -> ErrorIA:
    """Apunta el fallo en el registro del admin y devuelve el error para lanzarlo."""
    registro.apuntar(nivel, "IA", mensaje)
    return ErrorIA(mensaje)


def _clave() -> str | None:
    return db.config("IA_API_KEY") or db.config("GEMINI_API_KEY")


def disponible() -> bool:
    return bool(_clave())


def _modelos() -> list[str]:
    base = db.config("IA_BASE_URL") or GEMINI
    por_defecto = MODELOS_GEMINI if base == GEMINI else ""
    return [m.strip() for m in (db.config("IA_MODELOS") or por_defecto).split(",") if m.strip()]


@st.cache_resource
def _cliente() -> openai.OpenAI:
    return openai.OpenAI(api_key=_clave(), base_url=db.config("IA_BASE_URL") or GEMINI, max_retries=0, timeout=40)


def _completar(mensajes: list[dict], herramientas: list[dict] | None = None, json_salida: bool = False):
    """Una llamada al modelo; si está saturado o sin cuota, prueba el siguiente de la lista."""
    extra = {"tools": herramientas} if herramientas else {}
    if json_salida:
        extra["response_format"] = {"type": "json_object"}
    ultimo = None
    for modelo in _modelos():
        try:
            respuesta = _cliente().chat.completions.create(model=modelo, messages=mensajes, **extra)
            return respuesta.choices[0].message
        except (openai.RateLimitError, openai.InternalServerError, openai.APITimeoutError) as e:
            ultimo = e  # cuota gratuita agotada o modelo saturado: siguiente modelo
        except openai.AuthenticationError:
            raise _fallo("La clave de la IA no es válida.")
        except openai.NotFoundError:
            raise _fallo(f"El modelo «{modelo}» no existe en este proveedor. Revisa IA_MODELOS.")
        except openai.APIConnectionError:
            raise _fallo("No hay conexión con la IA. Revisa internet.")
        except openai.APIStatusError as e:
            raise _fallo(f"La IA no ha podido responder ({e.status_code}).")
    if isinstance(ultimo, openai.RateLimitError):
        raise _fallo("Se ha agotado la cuota gratuita de la IA por ahora. Prueba dentro de un rato.")
    raise _fallo("La IA está saturada en este momento. Prueba otra vez en un minuto.")


def _texto(prompt: str) -> str:
    mensaje = _completar([{"role": "system", "content": SISTEMA}, {"role": "user", "content": prompt}])
    return (mensaje.content or "").strip()


def _json(contenido, formato: str) -> dict:
    mensaje = _completar([
        {"role": "system", "content": SISTEMA + f"\nResponde solo con un objeto JSON con esta forma: {formato}"},
        {"role": "user", "content": contenido},
    ], json_salida=True)
    texto = (mensaje.content or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        raise _fallo("La IA no ha devuelto una respuesta válida. Prueba otra vez.")


# ─────────────────────────── Asistente del gerente (chat con herramientas) ───────────────────────────

def _herramienta(nombre: str, descripcion: str, propiedades: dict | None = None, requeridas: list | None = None):
    return {"type": "function", "function": {
        "name": nombre, "description": descripcion,
        "parameters": {"type": "object", "properties": propiedades or {}, "required": requeridas or []},
    }}


_LOCAL = {"type": "string", "description": "id del local (sagrada-familia, enric-granados, madrid); vacío = todos"}
HERRAMIENTAS = [
    _herramienta("ver_locales_y_personal", "Locales del grupo y trabajadores con su rol (staff, gerente, directivo)."),
    _herramienta("ver_equipos", "Equipos y maquinaria con su ficha técnica, estado, garantía, empresa técnica y "
                 "revisión periódica (última y próxima).",
                 {"local": _LOCAL}),
    _herramienta("ver_tareas", "Plan de mantenimiento: tareas activas con su próxima fecha y si van atrasadas.",
                 {"local": _LOCAL,
                  "dias": {"type": "integer", "description": "mirar hasta dentro de N días (por defecto 30)"},
                  "solo_atrasadas": {"type": "boolean"}}),
    _herramienta("ver_bitacora", "Bitácora (registro de intervenciones) de equipos y servicios: mantenimientos, "
                 "revisiones, averías, reparaciones, visitas de empresas, quién, nº de factura y cuánto costó.",
                 {"local": _LOCAL,
                  "dias": {"type": "integer", "description": "últimos N días (por defecto 180)"},
                  "equipo": {"type": "string", "description": "parte del nombre del equipo"},
                  "tipo": {"type": "string", "enum": list(plan.TIPOS_EVENTO)}}),
    _herramienta("ver_servicios", "Servicios de mantenimiento del local (friorista, control de plagas DDD, extintores y "
                 "PCI, climatización, electricidad, fontanería…) con su empresa, última y próxima revisión.",
                 {"local": _LOCAL}),
    _herramienta("ver_proveedores", "Proveedores y empresas técnicas con su teléfono, contacto y documentación."),
    _herramienta("ver_productos_limpieza", "Productos de limpieza y desinfección autorizados (Anexo 1 del APPCC): "
                 "código P1…, uso, dosis, tiempo de contacto, nº de registro, fichas y peligros.", {"local": _LOCAL}),
    _herramienta("ver_protocolos", "Procedimientos (POE del APPCC: limpieza, aseos, temperaturas, averías) y rutinas "
                 "(apertura, cierre) del local, con su categoría, frecuencia (diaria, semanal, mensual…), momento del "
                 "día, hora límite, si toca hoy, sus pasos y los registros firmados recientes (quién, cuándo, si se "
                 "completó).",
                 {"local": _LOCAL, "nombre": {"type": "string", "description": "parte del nombre del protocolo"},
                  "dias_registros": {"type": "integer", "description": "registros de los últimos N días (14)"}}),
    _herramienta("ver_rumbo", "Encargos de Rumbo (órdenes, objetivos y proyectos) de cada persona: qué tiene "
                 "pendiente, para cuándo, quién lo encargó, avance de sus casillas y, si ya está archivado, su "
                 "valoración. Solo lo que puede ver quien pregunta.",
                 {"persona": {"type": "string", "description": "parte del nombre de la persona; vacío = todas"},
                  "estado": {"type": "string", "enum": ["abierto", "hecho", "archivado", "todos"],
                             "description": "por defecto, abierto (lo pendiente)"}}),
    _herramienta("ver_catalogo", "Catálogo de productos que se etiquetan: categoría APPCC, conservación, "
                 "caducidad en días, alérgenos y si es vegano."),
    _herramienta("ver_etiquetas_impresas", "Registro APPCC de etiquetas impresas: qué producto, cuándo se preparó, "
                 "cuándo caduca y quién lo hizo.",
                 {"dias": {"type": "integer", "description": "últimos N días (por defecto 7)"},
                  "producto": {"type": "string", "description": "parte del nombre del producto"}}),
    _herramienta("buscar_documentacion", "Busca en la documentación interna de LilOS (visión, módulos, decisiones, "
                 "historial de versiones).", {"consulta": {"type": "string"}}, ["consulta"]),
    _herramienta("buscar_en_internet", "Busca en internet información que no está en la intranet: normativa, "
                 "manuales de equipos, proveedores, precios…", {"consulta": {"type": "string"}}, ["consulta"]),
]

FUNCIONES = {
    "ver_locales_y_personal": intranet.locales_y_personal,
    "ver_equipos": intranet.equipos,
    "ver_tareas": intranet.tareas,
    "ver_bitacora": intranet.bitacora,
    "ver_servicios": intranet.servicios,
    "ver_proveedores": intranet.proveedores,
    "ver_productos_limpieza": intranet.productos_limpieza,
    "ver_protocolos": intranet.protocolos,
    "ver_rumbo": intranet.rumbo,
    "ver_catalogo": intranet.catalogo,
    "ver_etiquetas_impresas": intranet.etiquetas,
    "buscar_documentacion": intranet.documentacion,
    "buscar_en_internet": lambda consulta: buscar_en_internet(consulta),
}

NOMBRES_PASO = {
    "ver_locales_y_personal": "Consultando locales y personal", "ver_equipos": "Consultando equipos",
    "ver_tareas": "Consultando el plan de mantenimiento", "ver_bitacora": "Consultando la bitácora",
    "ver_servicios": "Consultando los servicios de mantenimiento",
    "ver_proveedores": "Consultando los proveedores", "ver_productos_limpieza": "Consultando los productos de limpieza",
    "ver_protocolos": "Consultando los protocolos", "ver_rumbo": "Consultando los encargos de Rumbo",
    "ver_catalogo": "Consultando el catálogo", "ver_etiquetas_impresas": "Consultando las etiquetas impresas",
    "buscar_documentacion": "Buscando en la documentación", "buscar_en_internet": "Buscando en internet",
}


def asistente(historial: list[dict], local_id: str, al_consultar=None) -> str:
    """Responde al último mensaje del historial [{role, content}], consultando la intranet cuando lo necesita.
    al_consultar(texto) se llama en cada consulta, para enseñar el progreso."""
    local = next((l["nombre"] for l in db.locales() if l["id"] == local_id), local_id)
    mensajes = [{"role": "system", "content": (
        f"{SISTEMA}\n\nHoy es {plan.fecha_es(date.today())}. El gerente está trabajando con el local {local} "
        f"(id «{local_id}»): si no dice otro, pregunta por ese local. Usa las herramientas para mirar los datos "
        "reales antes de responder; puedes usar varias. Busca en internet solo lo que no esté en la intranet y di de "
        "dónde sale. Responde en markdown breve, con lo más importante primero."
    )}] + historial
    for _ in range(8):
        mensaje = _completar(mensajes, HERRAMIENTAS)
        llamadas = mensaje.tool_calls or []
        if not llamadas:
            return (mensaje.content or "").strip() or "No he sabido responder a eso."
        # El mensaje se devuelve tal cual: algunos modelos (Gemini) añaden datos propios que hay que reenviar
        mensajes.append(mensaje.model_dump(exclude_none=True))
        for llamada in llamadas:
            nombre = llamada.function.name
            if al_consultar:
                al_consultar(NOMBRES_PASO.get(nombre, nombre))
            try:
                argumentos = json.loads(llamada.function.arguments or "{}")
                resultado = FUNCIONES[nombre](**{k: v for k, v in argumentos.items() if v not in (None, "")})
            except Exception as e:  # el modelo se equivoca de herramienta o de datos: se lo decimos y sigue
                registro.aviso("IA · herramienta", f"{nombre}: {e}")
                resultado = {"error": f"No se pudo consultar: {e}"}
            mensajes.append({"role": "tool", "tool_call_id": llamada.id,
                             "content": json.dumps(resultado, ensure_ascii=False, default=str)[:30000]})
    return "He hecho demasiadas consultas sin llegar a una respuesta. Prueba a preguntarlo de forma más concreta."


def buscar_en_internet(consulta: str) -> dict:
    """Tavily (plan gratuito, hecho para asistentes de IA) si hay clave; si no, la Wikipedia en español."""
    try:
        if clave := db.config("TAVILY_API_KEY"):
            r = httpx.post("https://api.tavily.com/search", timeout=30,
                           headers={"Authorization": f"Bearer {clave}"},
                           json={"query": consulta, "max_results": 5, "include_answer": True})
            r.raise_for_status()
            datos = r.json()
            return {"fuente": "internet (Tavily)", "resumen": datos.get("answer"),
                    "resultados": [{"titulo": x.get("title"), "url": x.get("url"), "texto": x.get("content")}
                                   for x in datos.get("results", [])]}
        r = httpx.get("https://es.wikipedia.org/w/rest.php/v1/search/page", timeout=30,
                      params={"q": consulta, "limit": 5}, headers={"User-Agent": "LilOS-gerencia/1.0"})
        r.raise_for_status()
        return {"fuente": "Wikipedia en español (para buscar en todo internet falta TAVILY_API_KEY)",
                "resultados": [{"titulo": p["title"], "url": f"https://es.wikipedia.org/wiki/{p['key']}",
                                "texto": (p.get("excerpt") or "").replace('<span class="searchmatch">', "")
                                .replace("</span>", "")} for p in r.json().get("pages", [])]}
    except httpx.HTTPError as e:
        registro.aviso("IA · búsqueda en internet", str(e))
        return {"error": f"No se pudo buscar en internet: {e}"}


# ─────────────────────────────────── Ayudas puntuales ───────────────────────────────────

def _ficha_texto(equipo: dict) -> str:
    campos = {
        "Nombre": equipo.get("nombre"), "Tipo": equipo.get("tipo"), "Zona": equipo.get("zona"),
        "Marca": equipo.get("marca"), "Modelo": equipo.get("modelo"),
        "Fecha de compra": plan.fecha_es(equipo.get("fecha_compra")) if equipo.get("fecha_compra") else None,
        "Rango de temperatura": (f"{equipo['temp_min']} a {equipo['temp_max']} °C"
                                 if equipo.get("temp_min") is not None and equipo.get("temp_max") is not None
                                 else None),
        "Notas": equipo.get("notas"),
    }
    return "\n".join(f"- {k}: {v}" for k, v in campos.items() if v)


def _preparar_foto(imagen: bytes) -> str:
    """Las fotos del móvil pesan mucho: se reducen a 1568 px de lado en JPEG."""
    try:
        foto = ImageOps.exif_transpose(Image.open(io.BytesIO(imagen))).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise ErrorIA("No se ha podido abrir la foto. Prueba con otra en JPG o PNG.")
    foto.thumbnail((1568, 1568))
    salida = io.BytesIO()
    foto.save(salida, format="JPEG", quality=88)
    return base64.standard_b64encode(salida.getvalue()).decode("utf-8")


def leer_placa(imagen: bytes) -> dict:
    datos = _json([
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_preparar_foto(imagen)}"}},
        {"type": "text", "text": (
            "Es la foto de la placa de características (o del propio equipo) de una máquina de cocina. Rellena la "
            "ficha con lo que se lea: tipo de equipo, marca, modelo y número de serie tal cual aparecen. temp_min y "
            "temp_max (°C) solo para equipos de frío o calor: las de la placa o, si no salen, las habituales de "
            "trabajo para ese tipo de equipo en hostelería. En notas, lo útil para mantenimiento (potencia, "
            "voltaje, gas refrigerante…) en una o dos líneas. Lo que no se lea, null."
        )},
    ], '{"tipo": uno de ' + json.dumps(plan.TIPOS_EQUIPO, ensure_ascii=False) + ', "marca": texto o null, '
       '"modelo": texto o null, "numero_serie": texto o null, "temp_min": número o null, "temp_max": número o null, '
       '"notas": texto o null}')
    if datos.get("tipo") not in plan.TIPOS_EQUIPO:
        datos["tipo"] = "Otro"
    for campo in ("temp_min", "temp_max"):
        if not isinstance(datos.get(campo), (int, float)):
            datos[campo] = None
    campos = ("tipo", "marca", "modelo", "numero_serie", "temp_min", "temp_max", "notas")
    return {k: datos.get(k) for k in campos}


def sugerir_plan(equipo: dict, tareas_actuales: list[dict]) -> list[dict]:
    actuales = "\n".join(f"- {t['tarea']} ({t['frecuencia']})" for t in tareas_actuales) or "(ninguna)"
    datos = _json(
        f"Equipo de un restaurante:\n{_ficha_texto(equipo)}\n\nTareas que ya tiene en el plan:\n{actuales}\n\n"
        "Propón el plan de mantenimiento preventivo que le falta: entre 3 y 6 tareas concretas que pueda hacer el "
        "personal o el técnico, sin repetir las que ya tiene, cada una con su frecuencia y el motivo en una frase "
        "(qué evita). Tareas cortas, en imperativo, como «Limpiar el condensador».",
        '{"tareas": [{"tarea": texto, "frecuencia": uno de ' + json.dumps(list(plan.FRECUENCIAS)) +
        ', "motivo": texto}]}')
    return [t for t in datos.get("tareas", [])
            if isinstance(t, dict) and t.get("tarea") and t.get("frecuencia") in plan.FRECUENCIAS]


def ayuda_averia(equipo: dict, sintoma: str, historial: list[dict]) -> str:
    previo = "\n".join(
        f"- {plan.fecha_es(h['fecha'])} · {plan.TIPOS_EVENTO.get(h['tipo'], h['tipo'])}: {h['descripcion']}"
        for h in historial[:15]
    ) or "(sin historial)"
    return _texto(
        f"Equipo:\n{_ficha_texto(equipo)}\n\nÚltimos apuntes de su bitácora:\n{previo}\n\n"
        f"Qué le pasa ahora, contado por el personal: «{sintoma}»\n\n"
        "Ayuda al gerente a decidir qué hacer. Responde en markdown breve con estos apartados: **Qué hacer ya** "
        "(sobre todo con el género si es un equipo de frío), **Comprobaciones sencillas** que pueda hacer el "
        "personal sin herramientas ni riesgo, **Posibles causas** y **¿Llamar al técnico?** (sí o no y por qué). "
        "Si el historial muestra que se repite, dilo. Nada de manipular gas, electricidad ni piezas internas."
    )


def resumen_gerente(local: str, horizonte: str, pendientes: list[dict], atrasadas: list[dict],
                    escaladas: list[dict], averiados: list[dict], equipos: dict) -> str:
    def linea(t):
        e = equipos[t["equipo_id"]]
        return f"- {t['tarea']} · {e['nombre']} ({e['tipo']}) · toca el {plan.fecha_es(t['proxima_fecha'])}"

    ids_atrasadas = {t["id"] for t in atrasadas}
    return _texto(
        f"Situación del mantenimiento en {local}, {horizonte.lower()}:\n\n"
        f"Atrasadas ({len(atrasadas)}, de ellas {len(escaladas)} escaladas a dirección por llevar más de "
        f"{plan.DIAS_ESCALADO} días):\n" + ("\n".join(linea(t) for t in atrasadas) or "- ninguna") +
        "\n\nPróximas:\n" + ("\n".join(linea(t) for t in pendientes if t["id"] not in ids_atrasadas) or "- ninguna") +
        "\n\nEquipos averiados o en reparación:\n" +
        ("\n".join(f"- {e['nombre']} ({e['tipo']}) · {plan.ESTADOS_EQUIPO[e['estado']]}" for e in averiados)
         or "- ninguno") +
        "\n\nEscribe al gerente un resumen de 3 a 5 frases: cómo está el local, qué es lo primero que tiene que "
        "hacer hoy y por qué (prioriza lo que afecta a la seguridad alimentaria y lo escalado), y qué puede "
        "esperar. Sin listas ni títulos, directo."
    )


def redactar_rumbo(objetivo: str, tipo: str = "orden", para: str | None = None) -> str:
    """Convierte un encargo de una línea en una nota de Rumbo: una frase de contexto y casillas «- [ ]»."""
    mensaje = _completar([
        {"role": "system", "content": (
            "Eres el jefe de operaciones de Lilo Brunch (restaurantes de brunch en España). Conviertes un encargo de "
            "una línea en instrucciones claras para una persona del equipo. Escribe en español de España, en "
            "markdown: una frase de contexto (qué se busca y por qué) y después entre 3 y 8 casillas «- [ ] …», "
            "cada una una acción concreta y comprobable, en imperativo y corta. Si ayuda, una línea final «**Listo "
            "cuando:** …». Nada de títulos ni de texto fuera de eso.")},
        {"role": "user", "content": f"Tipo: {tipo}. Para: {para or 'una persona del equipo'}. Encargo: {objetivo}"},
    ])
    texto = (mensaje.content or "").strip()
    for valla in ("```markdown", "```md", "```"):
        texto = texto.removeprefix(valla)
    return texto.removesuffix("```").strip()
