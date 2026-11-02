"""Inspecciones (como SafetyCulture / iAuditor): sanidad, PRL, emergencias, calidad, rutinas del local y plantillas
propias. Se responde pregunta a pregunta, la nota sale en directo y lo que falla puede ir a Rumbo como encargo.
Es el contenido de la pestaña Inspecciones de paginas/procedimientos_inspecciones.py."""
from datetime import date

import streamlit as st

from core import db, registro, rumbo, sesion
from core import inspecciones as insp


PAGINA_PLANTILLAS = "paginas/plantillas_inspeccion.py"   # página oculta: se abre con «✏️ Editar plantillas»


def mostrar() -> None:
    es_gerente = sesion.puede("gerente")
    local_id = st.session_state.local_id
    persona = sesion.actual() or {}

    # El equipo solo entra a hacer las inspecciones que le han encargado por Rumbo
    encargos = []
    if not es_gerente:
        try:
            encargos = rumbo.inspecciones_encargadas(persona)
        except Exception:
            encargos = []
        if not encargos:
            st.warning("Las inspecciones son cosa de gerencia. Aquí solo salen las que te encargan por Rumbo.")
            return

    if es_gerente:
        c1, c2 = st.columns([5, 1], vertical_alignment="center")
        c1.caption("Audita el local como lo haría un inspector de sanidad, un técnico de prevención o un cliente "
                   "misterioso, o revisa a fondo una rutina del local. Cada «No» puede llevar observación y acción "
                   "correctiva.")
        if c2.button("✏️ Editar plantillas", key="insp-editar-plantillas", width="stretch"):
            st.switch_page(PAGINA_PLANTILLAS)   # página oculta; allí hay un «← Volver»
    else:
        st.title("🔍 Mis inspecciones encargadas")
        st.caption("Inspecciones que te han encargado por Rumbo: contesta pregunta a pregunta y guarda; al terminar "
                   "quedan hechas.")

    try:
        plantillas = insp.plantillas(local_id, solo_activas=False)
    except Exception:
        st.error(insp.FALTA_TABLA)
        return

    # La primera vez se cargan solas las plantillas oficiales (sanidad, PRL, emergencias, calidad)
    if es_gerente and not any(p.get("predefinida") for p in plantillas):
        try:
            if insp.cargar_oficiales(plantillas):
                plantillas = insp.plantillas(local_id, solo_activas=False)
        except Exception as e:
            registro.excepcion("Inspecciones · plantillas oficiales", e)
            st.warning(f"No se pudieron cargar las plantillas oficiales: {e}")

    por_id = {p["id"]: p for p in plantillas}
    locales = {l["id"]: l["nombre"] for l in db.locales()}
    st.session_state.setdefault("insp_nonce", 0)


    def _icono(tipo: str | None) -> str:
        return insp.TIPOS_PLANTILLA.get(tipo or "", "✏️ ").split()[0]


    def _pct(valor) -> str:
        return f"{float(valor):g} %" if valor is not None else "—"


    if aviso := st.session_state.pop("insp_aviso", None):
        st.success(aviso)


    # ─────────────────────────── Nueva inspección ───────────────────────────

    def _encargo(plantilla: dict, fecha: date, nota: dict, malas: list[dict], para: str) -> bool:
        """Crea en Rumbo un encargo con una casilla por cada cosa que falla. Devuelve si se pudo."""
        try:
            titulo, contenido = insp.texto_encargo(plantilla["nombre"], fecha, nota, malas)
            rumbo.crear({"titulo": titulo, "tipo": "orden", "contenido": contenido, "para_id": para, "a_cargo_id": para,
                         "creado_por_id": persona.get("id"), "local_id": local_id,
                         "prioridad": "alta" if nota["criticas"] else "normal"})
            return True
        except Exception as e:
            registro.excepcion("Inspecciones · crear encargo en Rumbo", e)
            return False


    def _formulario(clave: str, plantilla: dict, filas: list[dict]) -> None:
        k = f"insp-{st.session_state.insp_nonce}-{clave}"
        c1, c2 = st.columns([1, 2], vertical_alignment="bottom")
        fecha = c1.date_input("Fecha", date.today(), format="DD/MM/YYYY", key=f"{k}-fecha")
        c2.markdown(f"Inspector/a: **{sesion.nombre() or '—'}**"
                    + (f"  \n<small>{plantilla['descripcion']}</small>" if plantilla.get("descripcion") else ""),
                    unsafe_allow_html=True)
        marcador = st.container()   # la nota se rellena al final, con lo ya respondido

        respuestas, extras, seccion = {}, {}, object()
        for p in filas:
            if p.get("seccion") != seccion:
                seccion = p.get("seccion")
                if seccion:
                    st.markdown(f"##### {seccion}")
            pk = f"{k}-{p['id']}"
            enunciado = p["enunciado"] + (" 🔴" if p.get("critica") else "")
            if p["tipo"] == "texto":
                st.markdown(f"ℹ️ *{p['enunciado']}*", help=p.get("ayuda"))
            elif p["tipo"] == "casilla":
                respuestas[p["id"]] = st.checkbox(enunciado, key=pk, help=p.get("ayuda"))
            elif p["tipo"] == "respuesta":
                respuestas[p["id"]] = st.text_input(enunciado + ("" if p.get("obligatoria", True) else " (opcional)"),
                                                    key=pk, help=p.get("ayuda"))
            else:
                a, b = st.columns([3, 2], vertical_alignment="center")
                a.markdown(enunciado, help=p.get("ayuda"))
                respuestas[p["id"]] = b.segmented_control("Respuesta", ["si", "no", "na"], format_func=insp.VALORES.get,
                                                          key=pk, label_visibility="collapsed")
                if respuestas[p["id"]] == "no":
                    c, d = st.columns(2)
                    extras[p["id"]] = {
                        "comentario": c.text_input("Qué se ha visto", key=f"{pk}-c", placeholder="Observación"),
                        "accion_correctiva": d.text_input("Acción correctiva", key=f"{pk}-a",
                                                          placeholder="Qué se hace y quién"),
                    }

        nota = insp.puntuar(filas, respuestas)
        res = insp.resultado(nota["porcentaje"], nota["criticas"])
        with marcador:
            a, b, c = st.columns(3)
            a.metric("Resultado", f"{insp.ICONO_RESULTADO[res]} {res}", border=True)
            b.metric("Puntuación", _pct(nota["porcentaje"]), f"{nota['puntos']}/{nota['maximo']} puntos",
                     delta_color="off", border=True)
            c.metric("Críticas", nota["criticas"], f"{nota['respondidas']}/{nota['total']} respondidas",
                     delta_color="off", border=True)

        st.divider()
        notas = st.text_area("Notas generales", key=f"{k}-notas", placeholder="Lo que quieras dejar anotado de la visita")
        malas = insp.fallos(filas, respuestas, extras)
        para = None
        if malas:
            c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
            if c1.checkbox(f"📌 Crear encargo en Rumbo con lo que falla ({len(malas)})", value=True, key=f"{k}-encargo"):
                try:
                    destinos = rumbo.destinatarios(persona, db.trabajadores())
                except Exception:
                    destinos = []
                if not destinos and persona.get("id"):
                    destinos = [persona]   # como mínimo, para quien inspecciona
                if destinos:
                    gerente = next((t["id"] for t in destinos if t.get("rol") == "gerente"
                                    and sesion.pertenece(t, local_id)), destinos[0]["id"])
                    ids = [t["id"] for t in destinos]
                    nombres = {t["id"]: t["name"] for t in destinos}
                    para = c2.selectbox("Para", ids, index=ids.index(gerente), format_func=nombres.get, key=f"{k}-para")

        if st.button("✅ Guardar y cerrar", type="primary", key=f"{k}-guardar"):
            if faltan := insp.pendientes(filas, respuestas):
                st.error(f"Faltan {len(faltan)} preguntas obligatorias: "
                         + "; ".join(p["enunciado"] for p in faltan[:3]) + ("…" if len(faltan) > 3 else ""))
                return
            try:
                insp.guardar_inspeccion(plantilla, filas, respuestas, extras, local_id, sesion.nombre(), fecha, notas)
            except Exception as e:
                registro.excepcion("Inspecciones · guardar", e)
                st.error(f"No se pudo guardar la inspección: {e}")
                return
            aviso = f"Inspección guardada: {res} · {_pct(nota['porcentaje'])} · {nota['criticas']} crítica(s)."
            try:   # si alguien se la había encargado por Rumbo, queda hecha sola
                if rumbo.completar_inspeccion(persona, plantilla.get("id"), plantilla.get("protocolo_id")):
                    aviso += " Encargo de Rumbo hecho."
            except Exception:
                pass
            if para:
                aviso += (" Encargo creado en Rumbo." if _encargo(plantilla, fecha, nota, malas, para)
                          else " No se pudo crear el encargo en Rumbo (¿falta supabase/rumbo.sql?).")
            if es_gerente:
                st.session_state.insp_aviso = aviso
            else:
                st.toast(aviso)   # al quedarse sin encargos, el equipo sale de esta página: el aviso va como toast
            st.session_state.insp_nonce += 1
            st.rerun()


    try:
        protocolos = db.protocolos(local_id)
    except Exception:
        protocolos = []
    elegir_desde_rumbo = st.session_state.pop("insp_elegir", None)   # viene de «▶️ Hacerlo» en Rumbo u Hoy


    def _opciones() -> dict[str, str]:
        """Qué se puede inspeccionar: plantillas (p:…) y rutinas del local (r:…)."""
        activas = sorted([p for p in plantillas if p["activo"] and p["tipo"] != "rutina"],
                         key=lambda p: (not p.get("predefinida"), p["nombre"].lower()))
        opciones = {f"p:{p['id']}": f"{_icono(p['tipo'])} {p['nombre']}" for p in activas}
        return opciones | {f"r:{p['id']}": f"📋 Inspeccionar la rutina · {p['nombre']}" for p in protocolos}


    def _nombre_clave(clave: str) -> str:
        """Nombre con el que quedará la inspección en el historial."""
        if clave.startswith("r:"):
            return insp.desde_protocolo(next(p for p in protocolos if p["id"] == clave[2:]), [])["nombre"]
        return por_id[clave[2:]]["nombre"]


    def _mostrar(elegido: str) -> None:
        """Formulario de la plantilla (p:…) o de la rutina (r:…) elegida."""
        if elegido.startswith("r:"):
            protocolo = next((p for p in protocolos if p["id"] == elegido[2:]), None)
            if not protocolo:
                st.caption("Esa rutina ya no existe.")
                return
            plantilla = insp.desde_protocolo(protocolo)
            if not plantilla["preguntas"]:
                st.caption("Esta rutina no tiene pasos. Añádelos en Procedimientos (✏️ Editar).")
            else:
                _formulario(elegido, plantilla, plantilla["preguntas"])
        elif elegido[2:] in por_id:
            plantilla = por_id[elegido[2:]]
            filas = insp.preguntas(plantilla["id"])
            if not filas:
                st.caption("Esta plantilla no tiene preguntas. Añádelas con «✏️ Editar plantillas».")
            else:
                _formulario(elegido, plantilla, filas)
        else:
            st.caption("Esa plantilla ya no existe.")


    # ── Equipo: solo las inspecciones que le han encargado ──
    if not es_gerente:
        asignadas = {}
        for e in encargos:
            if (clave := rumbo.clave_inspeccion(e)) and clave not in asignadas:
                cuando = rumbo.vence_texto(e.get("vence"))
                asignadas[clave] = e["titulo"] + (f" · {cuando}" if cuando else "")
        if not asignadas:
            st.info("No te queda ninguna inspección encargada.")
            return
        clave_mia = f"insp-mia-{st.session_state.insp_nonce}"
        if elegir_desde_rumbo in asignadas:
            st.session_state[clave_mia] = elegir_desde_rumbo
        elif st.session_state.get(clave_mia) not in asignadas:
            st.session_state.pop(clave_mia, None)
        if len(asignadas) > 1:
            mia = st.selectbox("Inspección encargada", list(asignadas), format_func=asignadas.get, key=clave_mia)
        else:
            mia = next(iter(asignadas))
            st.markdown(f"**{asignadas[mia]}**")
        _mostrar(mia)
        return

    tab_nueva, tab_historial = st.tabs(["📝 Nueva", "📒 Historial"])

    with tab_nueva:
        opciones = _opciones()
        clave_sel = f"insp-elegido-{st.session_state.insp_nonce}"
        if elegir_desde_rumbo in opciones:
            st.session_state[clave_sel] = elegir_desde_rumbo
        c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
        elegido = c1.selectbox("Qué vas a inspeccionar", list(opciones), format_func=opciones.get, index=None,
                               placeholder="Elige una plantilla o una rutina del local", key=clave_sel)

        def _elegir_encargo():
            que = st.selectbox("Qué inspeccionar", list(opciones), format_func=opciones.get, index=None,
                               placeholder="Elige una plantilla o una rutina", key="insp-encargar-que")
            if not que:
                return None
            nombre = _nombre_clave(que)
            return (f"Inspeccionar: {nombre}", rumbo.props_inspeccion(que, nombre),
                    f"Se da por hecho al guardar la inspección «{nombre}» (botón ▶️ Hacerlo).")

        with c2:
            rumbo.popover_encargar("encargar-insp", _elegir_encargo, "📌 Encargar")
        if elegido:
            _mostrar(elegido)


    # ─────────────────────────── Historial ───────────────────────────

    with tab_historial:
        todos = sesion.puede("directivo") and st.toggle("Todos los locales", key="insp-todos")
        lista = insp.inspecciones(None if todos else local_id)
        if not lista:
            st.caption("Todavía no hay inspecciones guardadas.")
        else:
            def _res(i):
                return insp.resultado(float(i["porcentaje"]) if i.get("porcentaje") is not None else None,
                                      i.get("criticas") or 0)

            st.dataframe([{
                "Fecha": insp._fecha_es(i["fecha"]), "Plantilla": i.get("plantilla") or "—",
                "Local": locales.get(i.get("local_id"), "—"), "Inspector/a": i.get("inspector") or "—",
                "%": float(i["porcentaje"]) if i.get("porcentaje") is not None else None,
                "Críticas": i.get("criticas") or 0, "Resultado": f"{insp.ICONO_RESULTADO[_res(i)]} {_res(i)}",
            } for i in lista], hide_index=True, width="stretch", column_config={
                "%": st.column_config.ProgressColumn("%", min_value=0, max_value=100, format="%.0f %%")})

            ver = st.selectbox("Ver una inspección", [i["id"] for i in lista], index=None, placeholder="Elige una",
                               format_func=lambda x: next(f"{insp._fecha_es(i['fecha'])} · {i.get('plantilla') or '—'} · "
                                                          f"{locales.get(i.get('local_id'), '')}" for i in lista if i["id"] == x),
                               key="insp-ver")
            if ver:
                inspeccion = next(i for i in lista if i["id"] == ver)
                filas = insp.respuestas(ver)
                res = _res(inspeccion)
                a, b, c = st.columns(3)
                a.metric("Resultado", f"{insp.ICONO_RESULTADO[res]} {res}", border=True)
                b.metric("Puntuación", _pct(inspeccion.get("porcentaje")), border=True)
                c.metric("Críticas", inspeccion.get("criticas") or 0, border=True)
                preguntas_, valores, extras = insp.respuestas_como_preguntas(filas)
                malas = insp.fallos(preguntas_, valores, extras)
                if malas:
                    st.markdown("**Lo que falla**")
                    for m in malas:
                        st.markdown(f"- {'🔴 **Crítica** · ' if m.get('critica') else ''}{m['enunciado']}"
                                    + (f"  \n  _{m['comentario']}_" if m.get("comentario") else "")
                                    + (f"  \n  ➜ {m['accion_correctiva']}" if m.get("accion_correctiva") else ""))
                else:
                    st.caption("Sin no conformidades.")
                if inspeccion.get("notas"):
                    st.info(inspeccion["notas"])
                with st.expander("Todas las respuestas"):
                    st.dataframe([{"Sección": p.get("seccion") or "", "Pregunta": p["enunciado"],
                                   "Respuesta": (insp.VALORES.get(valores[p["id"]], valores[p["id"]])
                                                 if p["tipo"] in insp.PUNTUABLES else valores[p["id"]]) or "—"}
                                  for p in preguntas_], hide_index=True, width="stretch")
                st.download_button("⬇️ Descargar informe (.md)",
                                   insp.informe_md(inspeccion, filas, locales.get(inspeccion.get("local_id"), "")),
                                   file_name=f"inspeccion-{inspeccion['fecha']}.md", mime="text/markdown")
