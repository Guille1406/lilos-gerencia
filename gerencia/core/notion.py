"""Rumbo ↔ Notion (solo admin): tu bandeja de Notion («segundo cerebro») alimenta los encargos de LilOS.

En tu base de Notion solo hace falta UNA propiedad nueva: la casilla «LilOS». Lo que marques con ella aparece en
LilOS (Rumbo → Notion) y allí eliges para quién es y cuándo vence, y lo envías. El título y el cuerpo de la página
(casillas, viñetas, listas) pasan al encargo. Si la página tiene una fecha (Vence, Fecha, Due…), se propone como
vencimiento.

De vuelta, LilOS no toca tus propiedades: deja un **comentario** en la página de Notion cuando se envía, cuando se
termina y cuando se valora. No es automático: se lee y se actualiza al abrir la pestaña o pulsar «Traer de Notion».
Configuración: NOTION_TOKEN (integración interna con permiso de leer contenido y de insertar comentarios) y
NOTION_RUMBO_DB (enlace de la base). La base tiene que estar compartida con la integración (··· → Conexiones).
"""
import httpx

from core import db, rumbo

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
CASILLA = "LilOS"
PERSONAS = ("interviene", "para", "responsable", "asignado", "quien", "quién")
FECHAS = ("vence", "fecha", "fecha limite", "fecha límite", "due", "due date", "date", "deadline", "cuando")


def configurado() -> bool:
    return bool(db.config("NOTION_TOKEN") and db.config("NOTION_RUMBO_DB")) and not db.solo_lectura()


def _cliente() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=30, headers={
        "Authorization": f"Bearer {db.config('NOTION_TOKEN')}", "Notion-Version": VERSION,
        "Content-Type": "application/json"})


def _base() -> str:
    """El ID de la base: vale pegar el enlace entero de Notion."""
    valor = db.config("NOTION_RUMBO_DB").split("?")[0].rstrip("/").split("/")[-1]
    return valor.split("-")[-1] if len(valor) > 32 else valor


# ── Lectura de páginas de Notion ──
def _texto_rico(partes: list[dict]) -> str:
    return "".join(p.get("plain_text", "") for p in partes or [])


def titulo(pagina: dict) -> str:
    """El título de la página, se llame como se llame la columna de título."""
    for p in pagina.get("properties", {}).values():
        if p.get("type") == "title":
            return _texto_rico(p["title"]).strip() or "Sin título"
    return "Sin título"


def fecha(pagina: dict) -> str | None:
    """Primera fecha de la página con un nombre de fecha conocido (Vence, Fecha, Due…)."""
    for nombre, p in pagina.get("properties", {}).items():
        if p.get("type") == "date" and p["date"] and nombre.strip().lower() in FECHAS:
            return (p["date"].get("start") or "")[:10] or None
    return None


def personas(pagina: dict) -> list[str]:
    """Nombres de columnas tipo «Interviene/Para/Responsable» (selección o personas): sirven para proponer «Para»."""
    nombres = []
    for nombre, p in pagina.get("properties", {}).items():
        if nombre.strip().lower() not in PERSONAS:
            continue
        if p.get("type") in ("select", "multi_select"):
            valor = p[p["type"]]
            nombres += [o["name"] for o in (valor if isinstance(valor, list) else [valor] if valor else [])]
        elif p.get("type") == "people":
            nombres += [u.get("name", "") for u in p["people"]]
    return [n for n in nombres if n]


def _texto_md(partes: list[dict]) -> str:
    """Texto rico de Notion con sus enlaces en markdown ([texto](url))."""
    trozos = []
    for p in partes or []:
        texto, enlace = p.get("plain_text", ""), p.get("href")
        trozos.append(f"[{texto}]({enlace})" if enlace and texto.strip() and texto != enlace else texto)
    return "".join(trozos)


def _hijos(c: httpx.Client, bloque_id: str) -> list[dict]:
    """Todos los bloques hijos (Notion los da de 100 en 100)."""
    bloques, cursor = [], None
    while True:
        params = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
        r = c.get(f"/blocks/{bloque_id}/children", params=params)
        r.raise_for_status()
        datos = r.json()
        bloques += datos.get("results", [])
        if not datos.get("has_more"):
            return bloques
        cursor = datos.get("next_cursor")


def leer_contenido(c: httpx.Client, pagina_id: str, max_bloques: int = 400) -> str:
    """Cuerpo completo de la página, entrando en desplegables y bloques anidados (hasta 4 niveles)."""
    contador = [0]

    def arbol(bloque_id: str, nivel: int) -> list[dict]:
        bloques = []
        for b in _hijos(c, bloque_id):
            contador[0] += 1
            if contador[0] > max_bloques:
                break
            if b.get("has_children") and nivel < 4 and b["type"] not in ("child_page", "child_database"):
                b["_hijos"] = arbol(b["id"], nivel + 1)
            bloques.append(b)
        return bloques

    return bloques_a_markdown(arbol(pagina_id, 0))


def bloques_a_markdown(bloques: list[dict], nivel: int = 0) -> str:
    """Cuerpo de la página de Notion → markdown de Rumbo. Casillas, viñetas, listas, títulos, desplegables (con su
    contenido sangrado debajo), avisos, citas, código, enlaces; imágenes y bases se indican con un aviso."""
    lineas, numero, sangria = [], 0, "  " * nivel
    for b in bloques:
        tipo = b.get("type")
        datos = b.get(tipo) or {}
        texto = _texto_md(datos.get("rich_text"))
        numero = numero + 1 if tipo == "numbered_list_item" else 0
        if tipo == "to_do":
            lineas.append(f"{sangria}- [{'x' if datos.get('checked') else ' '}] {texto}")
        elif tipo in ("bulleted_list_item", "toggle"):
            lineas.append(f"{sangria}- {texto}")
        elif tipo == "numbered_list_item":
            lineas.append(f"{sangria}{numero}. {texto}")
        elif tipo in ("heading_1", "heading_2", "heading_3"):
            lineas.append(f"{sangria}- **{texto}**" if nivel else f"\n{'#' * (int(tipo[-1]) + 1)} {texto}")
        elif tipo == "callout":
            icono = (datos.get("icon") or {}).get("emoji", "💡")
            lineas.append(f"{sangria}> {icono} {texto}")
        elif tipo == "quote":
            lineas.append(f"{sangria}> {texto}")
        elif tipo == "code":
            lineas.append(f"{sangria}`{texto}`")
        elif tipo == "paragraph":
            if texto.strip():
                lineas.append(f"{sangria}{texto}" if not nivel else f"{sangria}  {texto}")
        elif tipo in ("image", "video", "file", "pdf"):
            lineas.append(f"{sangria}  _({ {'image': 'imagen', 'video': 'vídeo'}.get(tipo, 'archivo')} en Notion)_")
        elif tipo in ("bookmark", "embed", "link_preview"):
            lineas.append(f"{sangria}  {datos.get('url', '')}")
        elif tipo == "child_database":
            lineas.append(f"{sangria}  _(tabla «{datos.get('title', '')}» en Notion)_")
        elif tipo == "child_page":
            lineas.append(f"{sangria}  _(página «{datos.get('title', '')}» en Notion)_")
        elif tipo == "divider":
            lineas.append("---")
        if b.get("_hijos"):   # contenido de un desplegable o de una viñeta con subelementos
            sub = bloques_a_markdown(b["_hijos"], nivel + 1)
            if sub:
                lineas.append(sub)
    return "\n".join(lineas).strip("\n") if nivel else "\n".join(lineas).strip()


def puntos_a_casillas(contenido: str) -> str:
    """Convierte los puntos de primer nivel («- algo») en casillas («- [ ] algo») para poder marcarlos en LilOS."""
    return "\n".join(f"- [ ] {l[2:]}" if l.startswith("- ") and not l.startswith("- [") else l
                     for l in contenido.splitlines())


def _por_notion(notas: list[dict]) -> dict[str, list[dict]]:
    """Encargos de LilOS agrupados por la página de Notion de la que vienen."""
    grupos: dict[str, list[dict]] = {}
    for nota in notas:
        nid = (nota.get("propiedades") or {}).get("notion_id")
        if nid:
            grupos.setdefault(nid, []).append(nota)
    return grupos


# ── Bandeja: lo marcado con «LilOS» que aún no se ha enviado ──
def bandeja() -> list[dict]:
    """Páginas con la casilla LilOS marcada que todavía no son encargos. Con su texto ya en markdown."""
    enviadas = set(_por_notion(rumbo.todas()))
    with _cliente() as c:
        r = c.post(f"/databases/{_base()}/query",
                   json={"filter": {"property": CASILLA, "checkbox": {"equals": True}}, "page_size": 100})
        r.raise_for_status()
        pendientes = []
        for pagina in r.json()["results"]:
            if pagina["id"] in enviadas or pagina.get("archived"):
                continue
            pendientes.append({"id": pagina["id"], "url": pagina.get("url"), "titulo": titulo(pagina),
                               "vence": fecha(pagina), "personas": personas(pagina),
                               "contenido": leer_contenido(c, pagina["id"])})
    return pendientes


def _comentar(c: httpx.Client, pagina_id: str, texto: str) -> bool:
    """Comentario en la página de Notion. Si la integración no tiene permiso de comentar, no pasa nada."""
    r = c.post("/comments", json={"parent": {"page_id": pagina_id}, "rich_text": [{"text": {"content": texto}}]})
    return r.is_success


def enviar(pagina: dict, filas: list[dict], para: str) -> None:
    """Crea el encargo (o las copias del grupo) y lo anota en Notion."""
    propiedades = {"notion_id": pagina["id"], "notion_url": pagina.get("url"), "notion_estado": "enviado"}
    rumbo.crear([{**f, "propiedades": {**(f.get("propiedades") or {}), **propiedades}} for f in filas])
    with _cliente() as c:
        _comentar(c, pagina["id"], f"📤 LilOS: enviado a {para}.")


def estado(copias: list[dict]) -> str:
    if all(n["estado"] == "archivado" for n in copias):
        return "valorado"
    if all(n["estado"] in ("hecho", "archivado") for n in copias):
        return "hecho"
    return "enviado"


def aviso(copias: list[dict], nuevo: str, nombres: dict[str, str]) -> str:
    """Texto del comentario cuando cambia el estado en LilOS."""
    if nuevo == "hecho":
        quien = ", ".join(sorted({nombres.get(n.get("para_id"), "?") for n in copias}))
        return f"✅ LilOS: hecho ({quien})."
    notas = [n["valoracion"] for n in copias if n.get("valoracion")]
    media = f" · valoración {round(sum(notas) / len(notas), 1)}/5" if notas else ""
    comentarios = "; ".join(n["comentario_valoracion"] for n in copias if n.get("comentario_valoracion"))
    return f"⭐ LilOS: valorado y archivado{media}." + (f" «{comentarios}»" if comentarios else "")


def actualizar_notion() -> int:
    """Comenta en Notion lo que ha cambiado (hecho, valorado) desde la última vez. Devuelve cuántas páginas."""
    nombres = {t["id"]: t["name"] for t in db.trabajadores()}
    cambios = 0
    with _cliente() as c:
        for nid, copias in _por_notion(rumbo.todas()).items():
            nuevo = estado(copias)
            anterior = (copias[0].get("propiedades") or {}).get("notion_estado", "enviado")
            if nuevo == anterior or nuevo == "enviado":
                continue
            _comentar(c, nid, aviso(copias, nuevo, nombres))
            for n in copias:   # se recuerda en cada copia para no repetir el comentario
                rumbo.actualizar(n["id"], {"propiedades": {**(n.get("propiedades") or {}), "notion_estado": nuevo}})
            cambios += 1
    return cambios
