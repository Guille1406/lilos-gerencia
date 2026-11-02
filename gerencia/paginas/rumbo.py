"""Rumbo: órdenes, objetivos y proyectos para cada persona. Lo que hay que hacer, para quién, para cuándo y, al
terminar, la valoración en su carpeta. Lo diario (marcar casillas) se hace desde Hoy; aquí, el detalle."""
from datetime import date

import pandas as pd
import streamlit as st

from core import db, ia, plan, registro, rumbo, sesion

persona = sesion.actual()
yo = persona["id"]
st.title("🧭 Rumbo")
st.caption("Encargos con dirección: qué hay que hacer, para quién y para cuándo. Cada persona los ve en **Hoy** y "
           "marca las casillas con un toque; al terminar, quien lo encargó lo valora y queda en su carpeta.")

try:
    notas = rumbo.todas()
except Exception:  # la tabla aún no existe en Supabase
    st.error(rumbo.FALTA_TABLA)
    st.caption("Pégalo entero en Supabase → SQL Editor → Run. Se puede ejecutar varias veces sin romper nada.")
    st.stop()

personal = db.trabajadores()
nombres = {t["id"]: t["name"] for t in personal}
locales = {l["id"]: l["nombre"] for l in db.locales()}
vistas = rumbo.visibles(persona, notas)
gerente, direccion = sesion.puede("gerente"), sesion.puede("directivo")
hoy = date.today()


def _quien(tid: str | None) -> str:
    return nombres.get(tid, "—") if tid else "—"


def _etiqueta(nota: dict) -> str:
    """Texto plano para el título de un desplegable."""
    hechas, total = rumbo.progreso(nota.get("contenido"))
    partes = [f"{'🔴 ' if nota.get('prioridad') == 'alta' else ''}{rumbo.TIPOS[nota['tipo']].split()[0]} {nota['titulo']}"]
    if nota["estado"] == "abierto" and (cuando := rumbo.vence_texto(nota.get("vence"), hoy)):
        partes.append(("⚠️ " if cuando == "vencido" else "📅 ") + cuando)
    if total:
        partes.append(f"{hechas}/{total}")
    return " · ".join(partes)


def _estrellas(n: int | None) -> str:
    return "⭐" * n if n else "sin valorar"


def _valorar(notas_a_valorar: list[dict], clave: str, texto_boton: str = "Valorar y archivar") -> None:
    """Valoración 1–5 con comentario; al guardar, la nota pasa a la carpeta de la persona."""
    with st.form(clave, border=False):
        a, b = st.columns([1, 2])
        estrellas = a.select_slider("Valoración", [1, 2, 3, 4, 5], value=4, format_func=lambda n: "⭐" * n)
        comentario = b.text_input("Comentario (opcional)", placeholder="Qué ha ido bien, qué mejorar…")
        if st.form_submit_button(texto_boton, type="primary"):
            for n in notas_a_valorar:
                rumbo.archivar(n["id"], estrellas, comentario)
            st.toast("Valorado y archivado en su carpeta")
            st.rerun()


def _editar(nota: dict, prefijo: str) -> None:
    with st.form(f"{prefijo}-editar-{nota['id']}", border=False):
        titulo = st.text_input("Título", nota["titulo"])
        contenido = st.text_area("Contenido", nota.get("contenido") or "", height=200)
        a, b = st.columns(2)
        vence = a.date_input("Vence", rumbo._fecha(nota.get("vence")), format="DD/MM/YYYY")
        prioridad = b.selectbox("Prioridad", list(rumbo.PRIORIDADES), format_func=rumbo.PRIORIDADES.get,
                                index=list(rumbo.PRIORIDADES).index(nota.get("prioridad") or "normal"))
        if st.form_submit_button("Guardar cambios", type="primary"):
            if not titulo.strip():
                st.error("Pon un título.")
            else:
                rumbo.actualizar(nota["id"], {"titulo": titulo.strip(), "contenido": contenido,
                                              "vence": vence.isoformat() if vence else None, "prioridad": prioridad})
                st.toast("Guardado")
                st.rerun()


def _ficha(nota: dict, prefijo: str) -> None:
    """Detalle de una nota: propiedades, texto con casillas vivas y lo que se puede hacer con ella."""
    datos = [rumbo.TIPOS[nota["tipo"]], f"para **{_quien(nota.get('para_id'))}**"]
    if nota.get("a_cargo_id") and nota["a_cargo_id"] != nota.get("para_id"):
        datos.append(f"a cargo de **{_quien(nota['a_cargo_id'])}**")
    if nota.get("creado_por_id") and nota["creado_por_id"] != nota.get("para_id"):
        datos.append(f"de {_quien(nota['creado_por_id'])}")
    if nota.get("vence"):
        datos.append(f"vence {plan.fecha_es(nota['vence'])} {rumbo.vence_badge(nota, hoy)}")
    if nota.get("prioridad") == "alta":
        datos.append(rumbo.PRIORIDADES["alta"])
    if nota["estado"] != "abierto":
        datos.append(rumbo.ESTADOS[nota["estado"]])
    st.markdown(" · ".join(datos))
    if visibles_ := rumbo.propiedades_visibles(nota):
        st.caption(" · ".join(f"**{k}:** {v}" for k, v in visibles_.items()))

    rumbo.casillas_vivas(nota, persona, prefijo=prefijo)

    if nota["estado"] == "archivado":
        st.markdown(f"**Valoración:** {_estrellas(nota.get('valoracion'))}"
                    + (f" — {nota['comentario_valoracion']}" if nota.get("comentario_valoracion") else ""))

    botones = st.columns(4)
    with botones[3]:   # encargo de un procedimiento o una inspección: lleva directo a hacerlo
        rumbo.boton_hacerlo(nota, persona, f"{prefijo}-hacerlo-{nota['id']}")
    if nota["estado"] == "abierto" and rumbo.puede_marcar(persona, nota):
        hechas, total = rumbo.progreso(nota.get("contenido"))
        if botones[0].button("✅ Marcar como hecho", key=f"{prefijo}-hecho-{nota['id']}", width="stretch",
                             type="primary" if hechas == total else "secondary"):
            rumbo.marcar_hecho(nota["id"])
            st.toast("¡Hecho! Queda pendiente de valoración")
            st.rerun()
    if nota["estado"] == "hecho" and rumbo.puede_marcar(persona, nota):
        if botones[0].button("↩️ Reabrir", key=f"{prefijo}-reabrir-{nota['id']}", width="stretch"):
            rumbo.reabrir(nota["id"])
            st.rerun()
    botones[1].download_button("⬇️ .md", rumbo.a_markdown(nota, nombres), rumbo.nombre_archivo(nota),
                               "text/markdown", key=f"{prefijo}-md-{nota['id']}", width="stretch")
    if nota["estado"] == "abierto" and nota.get("creado_por_id") == yo:
        if botones[2].toggle("✏️ Editar", key=f"{prefijo}-edit-{nota['id']}"):
            _editar(nota, prefijo)
    if nota["estado"] == "hecho" and rumbo.puede_valorar(persona, nota):
        if nota.get("para_id") == yo and nota.get("creado_por_id") == yo:   # nota personal: se archiva sin nota
            if botones[2].button("🗄️ Archivar", key=f"{prefijo}-arch-{nota['id']}", width="stretch"):
                rumbo.archivar(nota["id"], None, None)
                st.rerun()
        else:
            _valorar([nota], f"{prefijo}-valorar-{nota['id']}")


def _grupo(copias: list[dict], prefijo: str) -> None:
    """Un encargo de grupo en una línea: «Trabajadores · Enric Granados — 3/6 hecho», y quién lo ha hecho."""
    base = copias[0]
    terminadas = [c for c in copias if c["estado"] != "abierto"]
    etiqueta = (f"👥 {rumbo.nombre_grupo(base, locales)} — {base['titulo']} — "
                f"{len(terminadas)}/{len(copias)} hecho")
    with st.expander(etiqueta):
        st.markdown(f"{rumbo.TIPOS[base['tipo']]}" + (f" · vence {plan.fecha_es(base['vence'])}" if base.get("vence") else ""))
        st.markdown(base.get("contenido") or "")
        st.dataframe(
            [{"Persona": _quien(c["para_id"]), "Estado": rumbo.ESTADOS[c["estado"]],
              "Avance": "{}/{}".format(*rumbo.progreso(c.get("contenido"))),
              "Valoración": _estrellas(c.get("valoracion")) if c["estado"] == "archivado" else ""}
             for c in sorted(copias, key=lambda c: _quien(c["para_id"]))],
            hide_index=True, width="stretch")
        por_valorar = [c for c in copias if c["estado"] == "hecho" and rumbo.puede_valorar(persona, c)]
        if por_valorar:
            st.markdown("**Por valorar**")
            for c in por_valorar:
                with st.container(border=True):
                    st.markdown(f"**{_quien(c['para_id'])}** · {'{}/{}'.format(*rumbo.progreso(c.get('contenido')))}")
                    _valorar([c], f"{prefijo}-valorar-{c['id']}")
            if len(por_valorar) > 1:
                st.markdown(f"**Valorar a todos igual** ({len(por_valorar)})")
                _valorar(por_valorar, f"{prefijo}-valorar-todos-{base['grupo_id']}", "Valorar a todos y archivar")


# ── Pestañas según el rol ──
nombres_pestanas = ["Mis encargos", *(["Encargados por mí"] if gerente else []), "Carpetas", "➕ Nuevo",
                    *(["Todas"] if direccion else []), *(["Notion"] if sesion.puede("admin") else [])]
pestanas = dict(zip(nombres_pestanas, st.tabs(nombres_pestanas)))

def _apuntar_rapido() -> None:
    """Entrada rápida tipo Notion: solo el título (y, si quieres, la fecha al final). Se apunta para uno mismo."""
    texto = st.session_state.get("rumbo-rapido", "").strip()
    if not texto:
        return
    titulo, vence = rumbo.entrada_rapida(texto)
    rumbo.crear({"titulo": titulo, "tipo": "orden", "para_id": yo, "a_cargo_id": yo, "creado_por_id": yo,
                 "local_id": st.session_state.get("local_id") or sesion.sede_principal(persona), "vence": vence.isoformat() if vence else None})
    st.session_state["rumbo-rapido"] = ""
    st.toast(f"Apuntado: {titulo}" + (f" · {rumbo.vence_texto(vence)}" if vence else ""))


# ── Mis encargos: lo que tengo que hacer ──
with pestanas["Mis encargos"]:
    st.text_input("Apuntar", key="rumbo-rapido", on_change=_apuntar_rapido, label_visibility="collapsed",
                  placeholder="➕ Apunta algo y pulsa Enter · «Pedir hielo mañana», «Inventario vie»")
    mias = [n for n in notas if yo in (n.get("para_id"), n.get("a_cargo_id"))]
    abiertas = sorted([n for n in mias if n["estado"] == "abierto"], key=lambda n: rumbo.orden(n, hoy))
    if not abiertas:
        st.info("No tienes nada abierto. Cuando alguien te encargue algo, aparecerá aquí y en **Hoy**.")
    for nota in abiertas:
        with st.expander(_etiqueta(nota), expanded=len(abiertas) == 1):
            _ficha(nota, "mis")
    hechas = [n for n in mias if n["estado"] == "hecho"]
    if hechas:
        st.markdown("**Hechas, pendientes de valoración**")
        for nota in hechas:
            with st.expander(_etiqueta(nota)):
                _ficha(nota, "mis")

# ── Encargados por mí: seguimiento y valoración ──
if "Encargados por mí" in pestanas:
    with pestanas["Encargados por mí"]:
        encargadas = [n for n in notas if n.get("creado_por_id") == yo and n.get("para_id") != yo
                      and n["estado"] != "archivado"]
        if not encargadas:
            st.info("Aún no has encargado nada. Créalo en **➕ Nuevo**.")
        grupos = rumbo.agrupar(sorted(encargadas, key=lambda n: rumbo.orden(n, hoy)))
        por_valorar = [g for g in grupos if any(n["estado"] == "hecho" for n in g)]
        en_marcha = [g for g in grupos if not any(n["estado"] == "hecho" for n in g)]
        for apartado, lista in (("Hechas: valóralas y archívalas", por_valorar), ("En marcha", en_marcha)):
            if not lista:
                continue
            st.markdown(f"**{apartado}**")
            for g in lista:
                if g[0].get("grupo_id"):
                    _grupo(g, "enc")
                else:
                    with st.expander(f"{_etiqueta(g[0])} · {_quien(g[0].get('para_id'))}"):
                        _ficha(g[0], "enc")

# ── Carpetas: lo terminado de cada persona, con su valoración ──
with pestanas["Carpetas"]:
    gente = rumbo.personas_visibles(persona, personal)
    elegida = st.selectbox("Carpeta de", gente, format_func=lambda t: t["name"], key="carpeta-persona") \
        if len(gente) > 1 else (gente[0] if gente else None)
    if elegida:
        carpeta = sorted([n for n in vistas if elegida["id"] in (n.get("para_id"), n.get("a_cargo_id"))
                          and n["estado"] in ("hecho", "archivado")],
                         key=lambda n: n.get("archivado_en") or n.get("hecho_en") or "", reverse=True)
        valoradas = [n["valoracion"] for n in carpeta if n.get("valoracion")]
        a, b, c = st.columns(3)
        a.metric("Terminadas", len(carpeta))
        b.metric("Valoración media", f"{sum(valoradas) / len(valoradas):.1f} ⭐" if valoradas else "—")
        c.metric("Abiertas ahora", sum(1 for n in vistas if n.get("para_id") == elegida["id"] and n["estado"] == "abierto"))
        if carpeta:
            st.download_button("⬇️ Exportar carpeta (.md)", rumbo.carpeta_zip(carpeta, nombres, elegida["name"]),
                               f"rumbo-{rumbo._slug(elegida['name'])}.zip", "application/zip")
            for nota in carpeta:
                with st.expander(f"{_etiqueta(nota)} · {_estrellas(nota.get('valoracion'))}"):
                    _ficha(nota, "carpeta")
        else:
            st.info("Todavía no hay nada terminado en esta carpeta.")

# ── Nuevo encargo ──
with pestanas["➕ Nuevo"]:
    n = st.session_state.setdefault("rumbo_nuevo", 0)   # cambia al crear: deja el formulario vacío
    destinos = rumbo.destinatarios(persona, personal)
    opciones = [t["id"] for t in destinos] + \
        [f"grupo:staff:{l}" for l in rumbo.locales_para_grupo(persona, list(locales))]

    def _nombre_destino(op: str) -> str:
        if op.startswith("grupo:"):
            _, grupo, local = op.split(":", 2)
            miembros = rumbo.miembros_grupo(personal, local, grupo)
            return f"👥 {rumbo.GRUPOS[grupo]} · {locales[local].removeprefix('Lilo ')} ({len(miembros)})"
        return f"{nombres[op]} (yo)" if op == yo else nombres[op]

    if not gerente:
        st.caption("Apúntate tus propias tareas. Los encargos a otras personas los crea gerencia.")
    titulo = st.text_input("Título *", key=f"nuevo-titulo-{n}", placeholder="Revisar el inventario de la cámara")
    a, b = st.columns(2)
    tipo = a.selectbox("Tipo", list(rumbo.TIPOS), format_func=rumbo.TIPOS.get, key=f"nuevo-tipo-{n}")
    para = b.selectbox("Para *", opciones, format_func=_nombre_destino, key=f"nuevo-para-{n}")
    a, b, c = st.columns(3)
    a_cargo = a.selectbox("A cargo de", [None, *[t["id"] for t in destinos]], key=f"nuevo-cargo-{n}",
                          format_func=lambda i: ("Cada uno la suya" if str(para).startswith("grupo:")
                                                 else "La misma persona") if i is None else nombres[i])
    vence = b.date_input("Vence", None, min_value=hoy, format="DD/MM/YYYY", key=f"nuevo-vence-{n}")
    prioridad = c.segmented_control("Prioridad", list(rumbo.PRIORIDADES), format_func=rumbo.PRIORIDADES.get,
                                    default="normal", key=f"nuevo-prioridad-{n}")

    clave_contenido = f"nuevo-contenido-{n}"
    if ia.disponible():
        with st.expander("✨ Redactar con IA"):
            objetivo = st.text_input("¿Qué quieres conseguir?", key=f"nuevo-objetivo-{n}",
                                     placeholder="Que la barra esté lista para abrir a las 8:30 sin prisas")
            if st.button("Redactar", key=f"nuevo-redactar-{n}", disabled=not objetivo.strip()):
                with st.spinner("Redactando…"):
                    try:
                        st.session_state[clave_contenido] = ia.redactar_rumbo(
                            objetivo.strip(), tipo, None if str(para).startswith("grupo:") else nombres.get(para))
                        st.rerun()
                    except ia.ErrorIA as e:
                        st.error(str(e))

    escribir, vista = st.tabs(["✍️ Escribir", "👁️ Vista previa"])
    contenido = escribir.text_area(
        "Contenido", key=clave_contenido, height=220,
        placeholder="Una frase de contexto y las tareas:\n- [ ] Contar el género de la cámara\n- [ ] Apuntar lo que falta",
        help="Markdown: «- » viñeta · «1. » lista · «- [ ] » casilla · «**negrita**». Las casillas se marcan "
             "con un toque desde Hoy.")
    with vista:
        st.markdown(contenido or "_Nada que mostrar todavía._")

    with st.expander("Propiedades extra (opcional)"):
        st.caption("Lo que quieras añadir: zona, presupuesto, enlace… Una fila por propiedad.")
        propiedades = st.data_editor(pd.DataFrame({"clave": pd.Series(dtype="str"), "valor": pd.Series(dtype="str")}),
                                     num_rows="dynamic", hide_index=True, width="stretch", key=f"nuevo-props-{n}")

    if st.button("Crear encargo", type="primary", key=f"nuevo-crear-{n}"):
        extra = {str(f["clave"]).strip(): str(f["valor"]).strip() for f in propiedades.to_dict("records")
                 if pd.notna(f["clave"]) and str(f["clave"]).strip()}
        datos = {"titulo": titulo.strip(), "tipo": tipo, "contenido": contenido or None, "creado_por_id": yo,
                 "vence": vence.isoformat() if vence else None, "prioridad": prioridad or "normal",
                 "propiedades": extra}
        if not titulo.strip():
            st.error("Pon un título.")
        elif para.startswith("grupo:"):
            _, grupo, local = para.split(":", 2)
            miembros = rumbo.miembros_grupo(personal, local, grupo)
            if not miembros:
                st.error("En ese local no hay nadie del equipo activo.")
            else:
                rumbo.crear(rumbo.copias_grupo({**datos, "local_id": local}, miembros, grupo, a_cargo))
                st.session_state.rumbo_nuevo = n + 1
                st.toast(f"Encargo creado para {len(miembros)} personas: lo verán en Hoy")
                st.rerun()
        else:
            destino = next(t for t in destinos if t["id"] == para)
            rumbo.crear({**datos, "para_id": para, "a_cargo_id": a_cargo or para,
                         "local_id": sesion.sede_principal(destino) or sesion.sede_principal(persona)})
            st.session_state.rumbo_nuevo = n + 1
            st.toast("Encargo creado: lo verá en Hoy" if para != yo else "Apuntado en tu rumbo")
            st.rerun()

# ── Todas (dirección y admin): todo, en todos los locales ──
if "Todas" in pestanas:
    with pestanas["Todas"]:
        a, b, c = st.columns(3)
        filtro_local = a.selectbox("Local", [None, *locales], format_func=lambda i: locales.get(i, "Todos los locales"),
                                   key="todas-local")
        filtro_persona = b.selectbox("Persona", [None, *sorted(nombres, key=lambda i: nombres[i].lower())],
                                     format_func=lambda i: nombres.get(i, "Todas"), key="todas-persona")
        filtro_estado = c.multiselect("Estado", list(rumbo.ESTADOS), default=["abierto", "hecho"],
                                      format_func=rumbo.ESTADOS.get, key="todas-estado")
        filtradas = [nt for nt in vistas
                     if (not filtro_local or nt.get("local_id") == filtro_local)
                     and (not filtro_persona or filtro_persona in (nt.get("para_id"), nt.get("a_cargo_id"),
                                                                    nt.get("creado_por_id")))
                     and (not filtro_estado or nt["estado"] in filtro_estado)]
        filtradas.sort(key=lambda nt: rumbo.orden(nt, hoy))
        st.caption(f"{len(filtradas)} notas")
        st.dataframe(
            [{"Título": nt["titulo"], "Tipo": rumbo.TIPOS[nt["tipo"]], "Para": _quien(nt.get("para_id")),
              "Grupo": rumbo.nombre_grupo(nt, locales) if nt.get("grupo_id") else "",
              "Local": locales.get(nt.get("local_id"), ""), "De": _quien(nt.get("creado_por_id")),
              "Vence": plan.fecha_es(nt["vence"]) if nt.get("vence") else "",
              "Avance": "{}/{}".format(*rumbo.progreso(nt.get("contenido"))), "Estado": rumbo.ESTADOS[nt["estado"]],
              "Valoración": nt.get("valoracion")} for nt in filtradas],
            hide_index=True, width="stretch")
        abrir = st.selectbox("Abrir una nota", filtradas, index=None, key="todas-abrir", placeholder="Elige una nota",
                             format_func=lambda nt: f"{nt['titulo']} · {_quien(nt.get('para_id'))}")
        if abrir:
            with st.container(border=True):
                st.markdown(f"### {abrir['titulo']}")
                _ficha(abrir, "todas")

# ── Notion (solo admin): lo que marcas con la casilla «LilOS» en tu bandeja de Notion llega aquí ──
if "Notion" in pestanas:
    from core import notion
    with pestanas["Notion"]:
        if not notion.configurado():
            st.info("Conecta tu bandeja de Notion: solo hace falta una casilla «LilOS» en tu base.")
            st.markdown(
                "1. En https://www.notion.so/profile/integrations → **Nueva integración** (interna). En *Capacidades*, "
                "deja **Leer contenido** e **Insertar comentarios**. Copia el *token*.\n"
                "2. En tu base de Notion añade una propiedad **casilla** llamada exactamente **LilOS**.\n"
                "3. Da acceso a la integración: en la página que contiene la base, menú **···** → **Conexiones**, o "
                "en la integración → pestaña **Acceso** → elige esa página.\n"
                "4. En `.streamlit/secrets.toml` pon `NOTION_TOKEN = \"...\"` y `NOTION_RUMBO_DB = \"enlace de la "
                "base\"` y reinicia la app.")
        else:
            st.caption("Lo que marques con **LilOS** en Notion aparece aquí: elige para quién y envíalo. Al terminarlo "
                       "y valorarlo, LilOS lo comenta en la página de Notion.")
            if st.button("🔄 Traer de Notion", type="primary") or "notion_bandeja" not in st.session_state:
                try:
                    with st.spinner("Leyendo tu Notion…"):
                        st.session_state.notion_bandeja = notion.bandeja()
                        avisados = notion.actualizar_notion()
                    if avisados:
                        st.toast(f"Notion: {avisados} páginas actualizadas con un comentario")
                except Exception as e:  # token, permisos, casilla o base mal configurados
                    st.session_state.notion_bandeja = []
                    registro.excepcion("Rumbo · Notion", e, f"Notion no responde: {str(e)[:300]}")
                    st.error(f"Notion no responde como esperaba: {str(e)[:300]}")
            bandeja = st.session_state.get("notion_bandeja", [])
            if not bandeja:
                st.caption("Nada pendiente: marca la casilla **LilOS** en Notion y pulsa «Traer de Notion».")
            for pagina in bandeja:
                with st.container(border=True):
                    st.markdown(f"**{pagina['titulo']}** · [abrir en Notion]({pagina['url']})")
                    casillas_n = False
                    if pagina["contenido"]:
                        with st.expander("Ver contenido"):
                            st.markdown(pagina["contenido"])
                        if rumbo.progreso(pagina["contenido"])[1] == 0 and "\n- " in "\n" + pagina["contenido"]:
                            casillas_n = st.checkbox("Convertir cada punto en una casilla para ir marcándolas",
                                                     key=f"notion-casillas-{pagina['id']}")
                    a, b, c, d = st.columns([3, 2, 2, 2], vertical_alignment="bottom")
                    # si en Notion pone «Interviene: José» y José está en LilOS, ya viene elegido
                    sugerido = next((op for op in opciones if not op.startswith("grupo:") and nombres.get(op, "").lower()
                                     in {x.lower() for x in pagina.get("personas", [])}), None)
                    para_n = a.selectbox("Para", opciones, format_func=_nombre_destino,
                                         index=opciones.index(sugerido) if sugerido else None,
                                         placeholder="¿Para quién?", key=f"notion-para-{pagina['id']}")
                    vence_n = b.date_input("Vence", date.fromisoformat(pagina["vence"]) if pagina["vence"] else None,
                                           format="DD/MM/YYYY", key=f"notion-vence-{pagina['id']}")
                    tipo_n = c.selectbox("Tipo", list(rumbo.TIPOS), format_func=rumbo.TIPOS.get,
                                         key=f"notion-tipo-{pagina['id']}")
                    if d.button("Enviar", key=f"notion-enviar-{pagina['id']}", type="primary", width="stretch",
                                disabled=not para_n):
                        texto_n = notion.puntos_a_casillas(pagina["contenido"]) if casillas_n else pagina["contenido"]
                        datos = {"titulo": pagina["titulo"], "tipo": tipo_n, "contenido": texto_n or None,
                                 "creado_por_id": yo, "vence": vence_n.isoformat() if vence_n else None,
                                 "prioridad": "normal"}
                        if para_n.startswith("grupo:"):
                            _, grupo, local = para_n.split(":", 2)
                            miembros = rumbo.miembros_grupo(personal, local, grupo)
                            filas = rumbo.copias_grupo({**datos, "local_id": local}, miembros, grupo)
                        else:
                            destino = next(t for t in personal if t["id"] == para_n)
                            filas = [{**datos, "para_id": para_n, "a_cargo_id": para_n,
                                      "local_id": sesion.sede_principal(destino) or sesion.sede_principal(persona)}]
                        if not filas:
                            st.error("En ese local no hay nadie del equipo activo.")
                        else:
                            notion.enviar(pagina, filas, _nombre_destino(para_n))
                            st.session_state.notion_bandeja = [p for p in bandeja if p["id"] != pagina["id"]]
                            st.toast(f"«{pagina['titulo']}» enviado: lo verá en Hoy")
                            st.rerun()
