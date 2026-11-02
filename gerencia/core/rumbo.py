"""Rumbo (pilar 2, «la brújula»): órdenes, objetivos y proyectos dirigidos a cada persona.

Cada nota es texto en markdown, como en Obsidian o Notion: viñetas, listas y casillas «- [ ]» / «- [x]». Lleva a
quién va dirigida (para), quién está a cargo, cuándo vence y propiedades libres. Al abrir Hoy, cada persona ve su
rumbo sin que nadie tenga que recordárselo; al terminar, quien lo encargó lo valora y lo archiva en la carpeta de
la persona, donde queda para revisar el trabajo.
"""
import io
import json
import re
import unicodedata
import uuid
import zipfile
from datetime import date, datetime, timezone, timedelta

import streamlit as st

from core import db, sesion

TIPOS = {"orden": "📌 Orden", "objetivo": "🎯 Objetivo", "proyecto": "🗂️ Proyecto"}
PRIORIDADES = {"normal": "Normal", "alta": "🔴 Alta"}
ESTADOS = {"abierto": "Abierto", "hecho": "✅ Hecho", "archivado": "🗄️ Archivado"}
DIAS_CORTOS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
FALTA_TABLA = "Falta ejecutar supabase/rumbo.sql en Supabase."

_CASILLA = re.compile(r"^(?P<sangria>\s*)(?P<vineta>[-*+]|\d+[.)])\s+\[(?P<marca>[ xX])\]\s?(?P<texto>.*)$")


# ─────────────────────────── Casillas del markdown ───────────────────────────

def casillas(contenido: str | None) -> list[dict]:
    """Casillas «- [ ]» / «- [x]» del texto, en orden: {indice, linea, nivel, hecho, texto}."""
    salida = []
    for n, linea in enumerate((contenido or "").splitlines()):
        m = _CASILLA.match(linea)
        if m:
            salida.append({"indice": len(salida), "linea": n, "nivel": len(m["sangria"].expandtabs(4)) // 2,
                           "hecho": m["marca"] != " ", "texto": m["texto"].strip()})
    return salida


def marcar(contenido: str | None, indice: int, hecho: bool | None = None) -> str:
    """Devuelve el texto con la casilla nº «indice» marcada (o desmarcada). Sin «hecho», la alterna."""
    lineas = (contenido or "").split("\n")
    casilla = next((c for c in casillas(contenido) if c["indice"] == indice), None)
    if casilla is None:
        return contenido or ""
    valor = (not casilla["hecho"]) if hecho is None else hecho
    lineas[casilla["linea"]] = re.sub(r"\[[ xX]\]", "[x]" if valor else "[ ]", lineas[casilla["linea"]], count=1)
    return "\n".join(lineas)


def progreso(contenido: str | None) -> tuple[int, int]:
    """(hechas, total) de las casillas del texto."""
    todas = casillas(contenido)
    return sum(c["hecho"] for c in todas), len(todas)


def pendientes(contenido: str | None) -> list[dict]:
    return [c for c in casillas(contenido) if not c["hecho"]]


# ─────────────────────────── Fechas y etiquetas ───────────────────────────

def _fecha(valor) -> date | None:
    if not valor:
        return None
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


_DIAS = {"lunes": 1, "lun": 1, "martes": 2, "mar": 2, "miercoles": 3, "miércoles": 3, "mie": 3, "mié": 3,
         "jueves": 4, "jue": 4, "viernes": 5, "vie": 5, "sabado": 6, "sábado": 6, "sab": 6, "sáb": 6,
         "domingo": 7, "dom": 7}


def entrada_rapida(texto: str, hoy: date | None = None) -> tuple[str, date | None]:
    """Título y fecha de una entrada rápida, como en Notion: «Pedir hielo mañana», «Inventario vie», «Pintar 24/10».
    La fecha va al final (hoy, mañana, un día de la semana —el próximo— o dd/mm); si no hay, sin fecha."""
    hoy = hoy or date.today()
    texto = " ".join(texto.split())
    partes = texto.rsplit(" ", 1)
    if len(partes) < 2:
        return texto, None
    titulo, ultima = partes[0], partes[1].lower().rstrip(".")
    if ultima == "hoy":
        return titulo, hoy
    if ultima in ("mañana", "manana"):
        return titulo, hoy + timedelta(days=1)
    if ultima in _DIAS:
        return titulo, hoy + timedelta(days=(_DIAS[ultima] - hoy.isoweekday() - 1) % 7 + 1)
    if "/" in ultima:
        try:
            dia, mes = (int(x) for x in ultima.split("/")[:2])
            fecha = date(hoy.year, mes, dia)
            return titulo, fecha if fecha >= hoy else date(hoy.year + 1, mes, dia)
        except ValueError:
            pass
    return texto, None


def vence_texto(valor, hoy: date | None = None) -> str:
    """«vencido», «hoy», «mañana» o «vie 23/10»; vacío si no tiene fecha."""
    fecha, hoy = _fecha(valor), hoy or date.today()
    if not fecha:
        return ""
    if fecha < hoy:
        return "vencido"
    if fecha == hoy:
        return "hoy"
    if (fecha - hoy).days == 1:
        return "mañana"
    return f"{DIAS_CORTOS[fecha.weekday()]} {fecha.strftime('%d/%m')}"


def vence_badge(nota: dict, hoy: date | None = None) -> str:
    """Etiqueta de color para el vencimiento (markdown de Streamlit)."""
    texto = vence_texto(nota.get("vence"), hoy)
    if not texto:
        return ""
    if nota.get("estado") != "abierto":   # ya terminada: solo la fecha, sin alarmas
        return f"📅 {_fecha(nota['vence']).strftime('%d/%m/%Y')}"
    color = "red" if texto == "vencido" else "orange" if texto in ("hoy", "mañana") else "gray"
    return f":{color}-badge[{texto}]"


def orden(nota: dict, hoy: date | None = None):
    """Lo urgente primero: vencido u hoy, luego prioridad alta, luego por fecha; sin fecha, al final."""
    fecha, hoy = _fecha(nota.get("vence")), hoy or date.today()
    urgente = fecha is not None and fecha <= hoy
    return (not urgente, nota.get("prioridad") != "alta", fecha or date.max, nota.get("created_at") or "")


# ─────────────────────────── Quién ve y quién encarga ───────────────────────────

def visibles(persona: dict | None, notas: list[dict]) -> list[dict]:
    """Staff: lo suyo (para o a cargo). Gerente: además todo su local y lo que ha encargado. Dirección y admin: todo."""
    if not persona:
        return []
    yo, nv = persona.get("id"), sesion.NIVEL.get(persona.get("rol"), -1)
    if nv >= sesion.NIVEL["directivo"]:
        return list(notas)

    def ve(n):
        if yo in (n.get("para_id"), n.get("a_cargo_id"), n.get("creado_por_id")):
            return True
        return nv >= sesion.NIVEL["gerente"] and sesion.pertenece(persona, n.get("local_id"))
    return [n for n in notas if ve(n)]


def puede_encargar(persona: dict | None, destino: dict | None) -> bool:
    """Cualquiera se apunta notas a sí mismo; gerencia y más encargan a quien está por debajo (el gerente, solo en
    su local)."""
    if not persona or not destino:
        return False
    if destino.get("id") == persona.get("id"):
        return True
    nv = sesion.NIVEL.get(persona.get("rol"), -1)
    if nv < sesion.NIVEL["gerente"] or sesion.NIVEL.get(destino.get("rol"), 0) >= nv:
        return False
    if nv == sesion.NIVEL["gerente"]:
        return any(sesion.pertenece(destino, l) for l in sesion.sedes(persona))
    return True


def destinatarios(persona: dict | None, personal: list[dict]) -> list[dict]:
    """A quién puede dirigir una nota: primero a sí mismo, luego el resto por nombre."""
    activos = [t for t in personal if t.get("activo", True) and puede_encargar(persona, t)]
    return sorted(activos, key=lambda t: (t["id"] != (persona or {}).get("id"), t["name"].lower()))


def personas_visibles(persona: dict | None, personal: list[dict]) -> list[dict]:
    """De quién puede abrir la carpeta: staff solo la suya; gerente, la gente de su local; dirección y admin, todos."""
    if not persona:
        return []
    nv = sesion.NIVEL.get(persona.get("rol"), -1)
    if nv >= sesion.NIVEL["directivo"]:
        gente = personal
    elif nv >= sesion.NIVEL["gerente"]:
        gente = [t for t in personal if t["id"] == persona["id"]
                 or any(sesion.pertenece(t, l) for l in sesion.sedes(persona))]
    else:
        gente = [t for t in personal if t["id"] == persona["id"]]
    return sorted(gente, key=lambda t: (t["id"] != persona["id"], t["name"].lower()))


# ── Encargos a un grupo: «Trabajadores · <local>» ──
# Cada persona del grupo recibe su propia copia (la hace y se valora por separado); las copias comparten grupo_id.
# Quien entra después en el local no recibe las copias ya creadas.
GRUPOS = {"staff": "Trabajadores"}


def locales_para_grupo(persona: dict | None, locales: list[str]) -> list[str]:
    """Locales a cuyo equipo puede encargar algo a la vez: el gerente, solo el suyo; dirección y admin, todos."""
    nv = sesion.NIVEL.get((persona or {}).get("rol"), -1)
    if nv >= sesion.NIVEL["directivo"]:
        return list(locales)
    if nv == sesion.NIVEL["gerente"]:
        return [l for l in sesion.sedes(persona) if l in locales]
    return []


def miembros_grupo(personal: list[dict], local_id: str, grupo: str = "staff") -> list[dict]:
    return [t for t in personal if t.get("activo", True) and (t.get("rol") or "staff") == grupo
            and sesion.pertenece(t, local_id)]


def copias_grupo(datos: dict, miembros: list[dict], grupo: str = "staff", a_cargo_id: str | None = None,
                 grupo_id: str | None = None) -> list[dict]:
    """Una fila por persona del grupo, todas con el mismo grupo_id. Sin «a cargo», cada uno de la suya."""
    grupo_id = grupo_id or str(uuid.uuid4())
    return [{**datos, "para_id": m["id"], "a_cargo_id": a_cargo_id or m["id"], "grupo_id": grupo_id,
             "para_grupo": grupo} for m in miembros]


def agrupar(notas: list[dict]) -> list[list[dict]]:
    """Junta las copias de un mismo encargo de grupo; las notas sueltas van solas. Mantiene el orden."""
    salida, por_grupo = [], {}
    for n in notas:
        if n.get("grupo_id"):
            if n["grupo_id"] not in por_grupo:
                por_grupo[n["grupo_id"]] = []
                salida.append(por_grupo[n["grupo_id"]])
            por_grupo[n["grupo_id"]].append(n)
        else:
            salida.append([n])
    return salida


def nombre_grupo(nota: dict, locales: dict[str, str]) -> str:
    local = locales.get(nota.get("local_id"), "").removeprefix("Lilo ")
    return f"{GRUPOS.get(nota.get('para_grupo'), 'Grupo')} · {local}".strip(" ·")


def puede_valorar(persona: dict | None, nota: dict) -> bool:
    """Valora y archiva quien la encargó; dirección y admin, cualquiera. Nadie valora su propio trabajo, salvo
    archivar sus notas personales."""
    if not persona:
        return False
    if nota.get("creado_por_id") == persona.get("id"):
        return True
    return sesion.NIVEL.get(persona.get("rol"), -1) >= sesion.NIVEL["directivo"] \
        and persona.get("id") not in (nota.get("para_id"), nota.get("a_cargo_id"))


def puede_marcar(persona: dict | None, nota: dict) -> bool:
    """Marcan casillas y dan por hecha la nota: a quien va dirigida, quien está a cargo y quien la encargó."""
    return bool(persona) and persona.get("id") in (nota.get("para_id"), nota.get("a_cargo_id"), nota.get("creado_por_id"))


# ─────────────────────────── Base de datos ───────────────────────────

def _tabla():
    return db.table("rumbo")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def todas(estados: list[str] | None = None) -> list[dict]:
    """Todas las notas (lanza excepción si falta la tabla: la página lo avisa)."""
    query = _tabla().select("*").order("created_at", desc=True)
    if estados:
        query = query.in_("estado", estados)
    return query.execute().data


def mias(persona: dict, estados: tuple[str, ...] = ("abierto",)) -> list[dict]:
    """Notas dirigidas a la persona o a su cargo."""
    filas = _tabla().select("*").in_("estado", list(estados)) \
        .or_(f"para_id.eq.{persona['id']},a_cargo_id.eq.{persona['id']}").execute().data
    return sorted(filas, key=orden)


def una(nota_id: str) -> dict | None:
    filas = _tabla().select("*").eq("id", nota_id).execute().data
    return filas[0] if filas else None


def crear(datos: dict | list[dict]) -> list[dict]:
    """Inserta una nota (o varias de una vez, las copias de un encargo de grupo)."""
    return _tabla().insert(datos).execute().data


def actualizar(nota_id: str, cambios: dict) -> None:
    _tabla().update({**cambios, "updated_at": _ahora()}).eq("id", nota_id).execute()


def guardar_casilla(nota_id: str, indice: int, hecho: bool) -> None:
    """Marca una casilla sobre el texto recién leído (por si otra persona lo ha cambiado entretanto)."""
    nota = una(nota_id)
    if nota:
        actualizar(nota_id, {"contenido": marcar(nota.get("contenido"), indice, hecho)})


def marcar_hecho(nota_id: str) -> None:
    actualizar(nota_id, {"estado": "hecho", "hecho_en": _ahora()})


def reabrir(nota_id: str) -> None:
    actualizar(nota_id, {"estado": "abierto", "hecho_en": None})


def archivar(nota_id: str, valoracion: int | None, comentario: str | None) -> None:
    actualizar(nota_id, {"estado": "archivado", "archivado_en": _ahora(), "valoracion": valoracion,
                         "comentario_valoracion": (comentario or "").strip() or None})


# ─────────────────────────── Encargar un procedimiento o una inspección ───────────────────────────
# El encargo es una nota de Rumbo normal (sin casillas: el procedimiento o la inspección ya es la lista) con
# propiedades que dicen qué hay que hacer. Al registrar el procedimiento o guardar la inspección, la nota se da por
# hecha sola; el botón «Hacerlo» lleva directo a la pantalla.
PROPIEDADES_INTERNAS = ("procedimiento_id", "procedimiento", "categoria", "inspeccion_plantilla_id",
                        "inspeccion_protocolo_id", "plantilla")
PAGINA_INSPECCIONES = "paginas/procedimientos_inspecciones.py"   # el equipo solo la ve con una inspección encargada
PAGINA_HOY = "paginas/hoy.py"


def propiedades_visibles(nota: dict) -> dict:
    """Propiedades de la nota sin las que usa LilOS por dentro (qué procedimiento o inspección se encarga)."""
    return {k: v for k, v in (nota.get("propiedades") or {}).items() if k not in PROPIEDADES_INTERNAS}


def props_procedimiento(protocolo: dict) -> dict:
    from core import plan
    return {"procedimiento_id": protocolo["id"], "procedimiento": protocolo["nombre"],
            "categoria": plan.categoria(protocolo)}


def props_inspeccion(clave: str, nombre: str) -> dict:
    """Propiedades de un encargo de inspección. «clave»: «p:<plantilla>» o «r:<protocolo>» (inspección de rutina)."""
    tipo, _, ident = clave.partition(":")
    return {"inspeccion_plantilla_id": ident if tipo == "p" else None,
            "inspeccion_protocolo_id": ident if tipo == "r" else None, "plantilla": nombre}


def clave_inspeccion(nota: dict) -> str | None:
    """«p:<plantilla>» / «r:<protocolo>» si la nota encarga una inspección; si no, None."""
    p = nota.get("propiedades") or {}
    if p.get("inspeccion_plantilla_id"):
        return f"p:{p['inspeccion_plantilla_id']}"
    if p.get("inspeccion_protocolo_id"):
        return f"r:{p['inspeccion_protocolo_id']}"
    return None


def encargo_ejecutable(nota: dict) -> dict | None:
    """Qué se hace con «Hacerlo»: {'tipo': 'procedimiento', 'id', 'pagina'} o {'tipo': 'inspeccion', 'clave', 'pagina'}."""
    if nota.get("estado") != "abierto":
        return None
    p = nota.get("propiedades") or {}
    if p.get("procedimiento_id"):
        from core import procedimientos, sesion
        # Gerencia lo hace en Procedimientos e inspecciones; el equipo no tiene esa página: lo hace en Hoy
        return {"tipo": "procedimiento", "id": p["procedimiento_id"],
                "pagina": procedimientos.PAGINA if sesion.puede("gerente") else PAGINA_HOY}
    if clave := clave_inspeccion(nota):
        return {"tipo": "inspeccion", "clave": clave, "pagina": PAGINA_INSPECCIONES}
    return None


def hacerlo(nota: dict) -> None:
    """Lleva a la pantalla donde se hace el encargo (procedimiento o inspección) con eso ya elegido."""
    e = encargo_ejecutable(nota)
    if not e:
        return
    if e["tipo"] == "procedimiento":
        if e["pagina"] == PAGINA_HOY:   # el equipo: la rutina está en Hoy; allí se le avisa de cuál es
            st.session_state.hoy_encargo = e["id"]
        else:
            st.session_state.protocolo_elegido = e["id"]
    else:
        st.session_state.insp_elegir = e["clave"]
    st.switch_page(e["pagina"])


def boton_hacerlo(nota: dict, persona: dict | None, clave: str, width="stretch") -> None:
    """«▶️ Hacerlo» para quien tiene el encargo (para o a cargo) si la nota encarga un procedimiento o inspección."""
    if persona and persona.get("id") in (nota.get("para_id"), nota.get("a_cargo_id")) and encargo_ejecutable(nota):
        if st.button("▶️ Hacerlo", key=clave, width=width, type="primary"):
            hacerlo(nota)


def _abiertas_que(persona: dict | None, coincide) -> list[dict]:
    if not persona:
        return []
    return [n for n in mias(persona) if coincide(n.get("propiedades") or {})]


def completar_procedimiento(persona: dict | None, protocolo_id: str) -> int:
    """Da por hechas las notas abiertas de esa persona que le encargaban este procedimiento. Devuelve cuántas."""
    notas = _abiertas_que(persona, lambda p: p.get("procedimiento_id") == protocolo_id)
    for n in notas:
        marcar_hecho(n["id"])
    return len(notas)


def inspecciones_encargadas(persona: dict | None) -> list[dict]:
    """Notas abiertas de esa persona que le encargan una inspección."""
    return _abiertas_que(persona, lambda p: bool(p.get("inspeccion_plantilla_id") or p.get("inspeccion_protocolo_id")))


def completar_inspeccion(persona: dict | None, plantilla_id: str | None, protocolo_id: str | None) -> int:
    """Da por hechas las notas abiertas de esa persona que le encargaban esta inspección (plantilla o rutina)."""
    def coincide(p):
        return bool((plantilla_id and p.get("inspeccion_plantilla_id") == plantilla_id)
                    or (protocolo_id and p.get("inspeccion_protocolo_id") == protocolo_id))
    notas = _abiertas_que(persona, coincide)
    for n in notas:
        marcar_hecho(n["id"])
    return len(notas)


def opciones_para(persona: dict | None, personal: list[dict], locales: list[str]) -> list[str]:
    """«Para» de un encargo, como en ➕ Nuevo: ids de personas y «grupo:staff:<local>» para todo el equipo."""
    return [t["id"] for t in destinatarios(persona, personal)] + \
        [f"grupo:staff:{l}" for l in locales_para_grupo(persona, locales)]


def nombre_destino(opcion: str, persona: dict | None, personal: list[dict], locales: dict[str, str]) -> str:
    if opcion.startswith("grupo:"):
        _, grupo, local = opcion.split(":", 2)
        return f"👥 {GRUPOS[grupo]} · {locales.get(local, '').removeprefix('Lilo ')} " \
               f"({len(miembros_grupo(personal, local, grupo))})"
    nombre = next((t["name"] for t in personal if t["id"] == opcion), "—")
    return f"{nombre} (yo)" if opcion == (persona or {}).get("id") else nombre


def crear_encargo(persona: dict, personal: list[dict], para: str, titulo: str, contenido: str, vence: date | None,
                  propiedades: dict) -> int:
    """Crea la nota de Rumbo del encargo (para una persona o para todo el equipo de un local). Devuelve a cuántas
    personas llega; ValueError si el grupo está vacío."""
    datos = {"titulo": titulo, "tipo": "orden", "contenido": contenido or None, "creado_por_id": persona["id"],
             "vence": vence.isoformat() if vence else None, "prioridad": "normal", "propiedades": propiedades}
    if para.startswith("grupo:"):
        _, grupo, local = para.split(":", 2)
        miembros = miembros_grupo(personal, local, grupo)
        if not miembros:
            raise ValueError("En ese local no hay nadie del equipo activo.")
        crear(copias_grupo({**datos, "local_id": local}, miembros, grupo))
        return len(miembros)
    destino = next(t for t in personal if t["id"] == para)
    crear({**datos, "para_id": para, "a_cargo_id": para, "local_id": sesion.sede_principal(destino) or sesion.sede_principal(persona)})
    return 1


def popover_encargar(clave: str, elegir, etiqueta: str = "📌 Encargar") -> None:
    """Desplegable «📌 Encargar» (gerente y más): Para, Vence y nota. «elegir» se llama dentro y devuelve
    (título, propiedades, línea de cómo se da por hecho) o None si aún no hay nada elegido."""
    persona = sesion.actual()
    if not persona or not sesion.puede("gerente"):
        return
    try:
        personal, locales = db.trabajadores(), {l["id"]: l["nombre"] for l in db.locales()}
    except Exception:
        return
    n = st.session_state.setdefault(f"{clave}-n", 0)   # cambia al crear: deja el desplegable limpio
    with st.popover(etiqueta):
        que = elegir()
        if not que:
            return
        titulo, propiedades, linea = que
        opciones = opciones_para(persona, personal, list(locales))
        if not opciones:
            st.caption("No hay a quién encargárselo.")
            return
        para = st.selectbox("Para", opciones, key=f"{clave}-para-{n}",
                            format_func=lambda o: nombre_destino(o, persona, personal, locales))
        vence = st.date_input("Vence", date.today(), min_value=date.today(), format="DD/MM/YYYY",
                              key=f"{clave}-vence-{n}")
        nota = st.text_area("Nota (opcional)", key=f"{clave}-nota-{n}", placeholder="Algo que tenga en cuenta")
        if st.button("📌 Encargar", type="primary", key=f"{clave}-ok-{n}"):
            contenido = (nota.strip() + "\n\n" if nota.strip() else "") + linea
            try:
                cuantos = crear_encargo(persona, personal, para, titulo, contenido, vence, propiedades)
            except ValueError as e:
                st.error(str(e))
                return
            except Exception:  # falta supabase/rumbo.sql
                st.error(FALTA_TABLA)
                return
            st.session_state[f"{clave}-n"] = n + 1
            st.toast(f"Encargado a {cuantos} personas: lo verán en Hoy" if cuantos > 1 else "Encargado: lo verá en Hoy")
            st.rerun()


# ─────────────────────────── Exportar a .md (Obsidian) ───────────────────────────

def _yaml(valor) -> str:
    """Valor YAML seguro: las cadenas JSON son YAML válido."""
    if valor is None or valor == "":
        return "null"
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return str(valor)
    return json.dumps(str(valor), ensure_ascii=False)


def _slug(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", plano).strip("-").lower()[:60] or "nota"


def nombre_archivo(nota: dict) -> str:
    return f"{(nota.get('created_at') or '')[:10] or 'sin-fecha'}-{_slug(nota.get('titulo'))}.md"


def a_markdown(nota: dict, nombres: dict[str, str]) -> str:
    """Una nota como .md con cabecera YAML (frontmatter), lista para abrir en Obsidian."""
    campos = {
        "titulo": nota.get("titulo"), "tipo": nota.get("tipo"),
        "para": nombres.get(nota.get("para_id"), nota.get("para_id")),
        "a_cargo": nombres.get(nota.get("a_cargo_id"), nota.get("a_cargo_id")),
        "creado_por": nombres.get(nota.get("creado_por_id"), nota.get("creado_por_id")),
        "creado": (nota.get("created_at") or "")[:10], "vence": nota.get("vence"),
        "prioridad": nota.get("prioridad"), "estado": nota.get("estado"),
        "hecho_en": (nota.get("hecho_en") or "")[:10], "valoracion": nota.get("valoracion"),
        "comentario_valoracion": nota.get("comentario_valoracion"),
    }
    lineas = ["---", *(f"{k}: {_yaml(v)}" for k, v in campos.items())]
    propiedades = nota.get("propiedades") or {}
    if propiedades:
        lineas.append("propiedades:")
        lineas += [f"  {_yaml(k)}: {_yaml(v)}" for k, v in propiedades.items()]
    else:
        lineas.append("propiedades: {}")
    lineas += ["---", "", f"# {nota.get('titulo') or ''}", "", (nota.get("contenido") or "").strip(), ""]
    return "\n".join(lineas)


def carpeta_zip(notas: list[dict], nombres: dict[str, str], carpeta: str = "rumbo") -> bytes:
    """Las notas de una persona en un .zip de archivos .md (sin repetir nombres)."""
    salida, usados = io.BytesIO(), set()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as zf:
        for nota in notas:
            nombre, n = nombre_archivo(nota), 2
            while nombre in usados:
                nombre = nombre_archivo(nota).removesuffix(".md") + f"-{n}.md"
                n += 1
            usados.add(nombre)
            zf.writestr(f"{_slug(carpeta)}/{nombre}", a_markdown(nota, nombres))
    return salida.getvalue()


# ─────────────────────────── Interfaz compartida ───────────────────────────

def _tocar(nota_id: str, indice: int, clave: str) -> None:
    guardar_casilla(nota_id, indice, bool(st.session_state.get(clave)))


def linea_resumen(nota: dict, hoy: date | None = None) -> str:
    """«**Título** · :red-badge[vencido] · 1/3» en una sola línea."""
    hechas, total = progreso(nota.get("contenido"))
    partes = [f"**{nota['titulo']}**"]
    if nota.get("prioridad") == "alta":
        partes[0] = "🔴 " + partes[0]
    if badge := vence_badge(nota, hoy):
        partes.append(badge)
    if total:
        partes.append(f"{hechas}/{total}")
    return " · ".join(partes)


def casillas_vivas(nota: dict, persona: dict | None, solo_pendientes: int | None = None, prefijo: str = "r") -> None:
    """Pinta el texto con casillas de verdad: un toque y queda guardado.
    Con «solo_pendientes», solo las N próximas casillas sin marcar (para Hoy)."""
    editable = puede_marcar(persona, nota) and nota.get("estado") == "abierto"
    if solo_pendientes is not None:
        faltan = pendientes(nota.get("contenido"))
        for c in faltan[:solo_pendientes]:
            clave = f"{prefijo}-{nota['id']}-{c['indice']}-{int(c['hecho'])}"
            st.checkbox(c["texto"] or "—", value=c["hecho"], key=clave, disabled=not editable,
                        on_change=_tocar, args=(nota["id"], c["indice"], clave))
        if len(faltan) > solo_pendientes:
            st.caption(f"y {len(faltan) - solo_pendientes} más")
        return

    bloque, por_linea = [], {c["linea"]: c for c in casillas(nota.get("contenido"))}

    def soltar():
        if "".join(bloque).strip():
            st.markdown("\n".join(bloque))
        bloque.clear()

    for n, linea in enumerate((nota.get("contenido") or "").split("\n")):
        c = por_linea.get(n)
        if not c:
            bloque.append(linea)
            continue
        soltar()
        clave = f"{prefijo}-{nota['id']}-{c['indice']}-{int(c['hecho'])}"
        sitio = st.columns([min(c["nivel"], 4) + 0.01, 30])[1] if c["nivel"] else st.container()
        sitio.checkbox(c["texto"] or "—", value=c["hecho"], key=clave, disabled=not editable,
                       on_change=_tocar, args=(nota["id"], c["indice"], clave))
    soltar()


def en_hoy() -> None:
    """Sección «Tu rumbo» para la pantalla Hoy: lo abierto de la persona, una línea por nota y las próximas casillas
    para marcarlas con un toque. No pinta nada si no hay notas o si falta la tabla."""
    persona = sesion.actual()
    if not persona:
        return
    try:
        notas = mias(persona)
    except Exception:  # falta supabase/rumbo.sql: Hoy sigue funcionando igual
        return
    if not notas:
        return
    st.subheader("🧭 Tu rumbo")
    hoy = date.today()
    for nota in notas:
        with st.container(border=True):
            hechas, total = progreso(nota.get("contenido"))
            a, b = st.columns([6, 2], vertical_alignment="center")
            a.markdown(linea_resumen(nota, hoy))
            if encargo_ejecutable(nota) and persona.get("id") in (nota.get("para_id"), nota.get("a_cargo_id")):
                with b:   # procedimiento o inspección encargados: se hace y la nota se da por hecha sola
                    boton_hacerlo(nota, persona, f"hoy-hacerlo-{nota['id']}")
            elif hechas == total and puede_marcar(persona, nota):
                b.button("✅ Marcar como hecho", key=f"hoy-hecho-{nota['id']}", width="stretch",
                         on_click=marcar_hecho, args=(nota["id"],))
            casillas_vivas(nota, persona, solo_pendientes=3, prefijo="hoy")
