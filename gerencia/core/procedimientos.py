"""Procedimientos (POE del APPCC) y Rutinas (apertura, cierre…) en una sola pantalla: hacerlos, firmarlos y ver sus
registros (y el historial de versiones de los POE). Es la pestaña Procedimientos de
paginas/procedimientos_inspecciones.py; crearlos y editarlos está en paginas/editar_procedimientos.py (página oculta,
a la que lleva «✏️ Editar»)."""
from datetime import date

import streamlit as st

from core import acciones, db, plan, rumbo, sesion, versiones

PAGINA = "paginas/procedimientos_inspecciones.py"   # a donde llevan «Ver tareas» (Hoy) y «Hacerlo» (Rumbo)
PAGINA_EDITAR = "paginas/editar_procedimientos.py"   # página oculta: se abre con «✏️ Editar»
NUEVO = "__nuevo__"   # opción «crear uno nuevo» de Editar procedimientos
FILTROS = {"todos": "Todos", "appcc": "📋 POE", "rutina": "🔁 Rutinas"}


def pagina() -> None:
    local_id = st.session_state.local_id
    st.caption("POE del APPCC (limpieza, aseos, temperaturas…) y rutinas del local (apertura, cierre…): quien lo hace "
               "marca cada tarea y firma; el encargado/a verifica. Cada registro queda guardado con fecha, hora y "
               "nombre, como la firma en papel.")

    todos = db.protocolos(local_id, solo_activos=False)
    por_id = {p["id"]: p for p in todos}
    puede_encargar = sesion.puede("gerente")   # hacer y consultar; encargar y editar son de gerencia
    # Viene de «Ver tareas» en Hoy, de «Hacerlo» en Rumbo o de «← Volver» en el editor
    desde = st.session_state.pop("protocolo_elegido", None)
    if desde in por_id:
        st.session_state["proc-filtro"] = "todos"
        st.session_state["proc-elegido"] = desde
    st.session_state.setdefault("proc-filtro", "todos")
    filtro = st.segmented_control("Mostrar", list(FILTROS), format_func=FILTROS.get, required=True, key="proc-filtro")
    visibles = [p for p in todos if filtro == "todos" or plan.categoria(p) == filtro]
    opciones = [p["id"] for p in visibles if p["activo"]] + \
        ([p["id"] for p in visibles if not p["activo"]] if puede_encargar else [])
    if not opciones:
        st.info("Todavía no hay nada aquí.")
        return
    if st.session_state.get("proc-elegido") not in opciones:
        st.session_state.pop("proc-elegido", None)
    c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
    elegido = c1.selectbox("Procedimiento o rutina", opciones, key="proc-elegido",
                           format_func=lambda i: etiqueta(por_id[i]))
    protocolo = por_id[elegido]
    if puede_encargar and c2.button("✏️ Editar", key="proc-editar", width="stretch"):
        st.session_state.editar_protocolo = elegido   # el editor lo preselecciona
        st.switch_page(PAGINA_EDITAR)
    nombres = [t["name"] for t in db.trabajadores()]
    yo = nombres.index(sesion.nombre()) if sesion.nombre() in nombres else 0

    if protocolo.get("descripcion"):
        st.info(protocolo["descripcion"])
    if protocolo.get("tipo") == "averia":
        st.caption("🚩 Se activa al avisar de una avería desde Hoy: no es una rutina que toque cada día.")
    tab_hacer, tab_registros = st.tabs(["✅ Hacer", "📒 Registros"])
    with tab_hacer:
        if puede_encargar and protocolo.get("activo", True):
            _encargar(protocolo)
        _hacer(protocolo, nombres, yo)
    with tab_registros:
        _registros(elegido, nombres, yo, plan.categoria(protocolo) == "appcc")


def etiqueta(p: dict) -> str:
    icono = plan.TIPOS_PROTOCOLO.get(p["tipo"], "").split(" ")[0]
    return " · ".join(x for x in (f"{icono} {p['nombre']}", plan.describir_frecuencia(p), plan.texto_franja(p),
                                  None if p["activo"] else "(inactivo)") if x)


# ── Encargar a alguien que lo haga (nota en Rumbo; se da por hecha al registrarlo) ──
def _encargar(protocolo: dict) -> None:
    def elegir():
        return (f"Hacer: {protocolo['nombre']}", rumbo.props_procedimiento(protocolo),
                f"Se da por hecho al registrar «{protocolo['nombre']}» (botón ▶️ Hacerlo).")
    rumbo.popover_encargar(f"encargar-{protocolo['id']}", elegir)


# ── Hacer el procedimiento y firmarlo ──
def _hacer(protocolo: dict, nombres: list[str], yo: int) -> None:
    elegido = protocolo["id"]
    pasos = db.pasos(elegido)
    c1, c2 = st.columns(2)
    dia = c1.date_input("Fecha", date.today(), format="DD/MM/YYYY", key=f"dia-{elegido}")
    turno = c2.text_input("Turno", placeholder="Mañana, tarde, cierre…", key=f"turno-{elegido}")
    if not plan.procedimiento_toca(protocolo, dia):
        st.caption(f"Este día no le toca ({plan.describir_frecuencia(protocolo)}), pero se puede registrar igual.")
    toca = [p for p in pasos if plan.paso_toca(p, dia)]
    hoy = [r for r in db.registros_protocolo([elegido], 20) if r["fecha"] == dia.isoformat()]
    if hoy:
        st.success(f"Ya registrado {len(hoy)} vez/veces este día: "
                   + ", ".join(f"{r.get('turno') or 'sin turno'} ({r.get('realizado_por') or '—'})" for r in hoy))
    if not toca:
        st.caption("No tiene pasos para este día. Añádelos con «✏️ Editar».")
        return
    with st.form(f"hacer-{elegido}-{dia}", clear_on_submit=True):
        marcados, seccion = {}, None
        for paso in toca:
            if paso.get("seccion") != seccion:
                seccion = paso.get("seccion")
                if seccion:
                    st.markdown(f"**{seccion}**")
            extra = []
            if paso.get("producto"):
                extra.append(f"🧴 {paso['producto']}")
            if paso.get("dia_semana"):
                extra.append(f"📅 {plan.DIAS_SEMANA[paso['dia_semana']]}")
            if paso.get("semana_mes"):
                extra.append(f"📅 {paso['semana_mes']}ª semana del mes")
            marcados[paso["id"]] = st.checkbox(paso["texto"] + (f"  ·  {' · '.join(extra)}" if extra else ""),
                                               key=f"paso-{paso['id']}-{dia}")
        st.divider()
        c1, c2 = st.columns(2)
        quien = c1.selectbox("Hecho por (firma)", nombres, index=yo) if nombres else c1.text_input("Hecho por (firma)")
        incidencias = c2.text_area("Incidencias", placeholder="Qué no se pudo hacer y por qué, acción tomada…")
        if st.form_submit_button("✍️ Firmar y guardar", type="primary"):
            hechos = sum(marcados.values())
            if hechos < len(marcados) and not incidencias.strip():
                st.error(f"Faltan {len(marcados) - hechos} tareas: anota en incidencias por qué no se hicieron.")
            elif not quien:
                st.error("Indica quién lo ha hecho.")
            else:
                acciones.registrar_protocolo(elegido, quien, dia, marcados, turno, incidencias)
                st.toast(f"Registrado: {hechos}/{len(marcados)} tareas · firmado por {quien}")
                st.rerun()


# ── Registros firmados y verificación del encargado/a ──
def _registros(elegido: str, nombres: list[str], yo: int, oficial: bool = False) -> None:
    if oficial:
        _versiones(elegido)
    registros = db.registros_protocolo([elegido], 200)
    if not registros:
        st.caption("Todavía no hay registros.")
        return
    marcas = db.table("protocolo_registro_pasos").select("registro_id, hecho") \
        .in_("registro_id", [r["id"] for r in registros]).execute().data
    cuenta = {}
    for m in marcas:
        total, hechos = cuenta.get(m["registro_id"], (0, 0))
        cuenta[m["registro_id"]] = (total + 1, hechos + bool(m["hecho"]))
    st.dataframe([{
        "Fecha": plan.fecha_es(r["fecha"]), "Turno": r.get("turno") or "—",
        **({"Versión": f"v{r['version']}" if r.get("version") else "—"} if oficial else {}),
        "Tareas": "{1}/{0}".format(*cuenta.get(r["id"], (0, 0))),
        "Completo": "✅" if r["completado"] else "⚠️", "Hecho por": r.get("realizado_por") or "—",
        "Verificado": r.get("verificado_por") or "pendiente", "Incidencias": r.get("incidencias") or "",
    } for r in registros], hide_index=True, width="stretch")

    pendientes = [r for r in registros if not r.get("verificado_por")]
    if pendientes:
        with st.form(f"verificar-{elegido}"):
            st.markdown("**Verificar (encargado/a)**")
            elegidos = st.multiselect(
                "Registros", [r["id"] for r in pendientes],
                default=[r["id"] for r in pendientes],
                format_func=lambda i: next(f"{plan.fecha_es(r['fecha'])} · {r.get('turno') or 'sin turno'} · "
                                           f"{r.get('realizado_por') or '—'}" for r in pendientes if r["id"] == i))
            verificador = st.selectbox("Verificado por", nombres, index=yo) if nombres else st.text_input("Verificado por")
            if st.form_submit_button("Verificar") and elegidos and verificador:
                db.table("protocolo_registros").update({"verificado_por": verificador}) \
                    .in_("id", elegidos).execute()
                st.toast(f"{len(elegidos)} registros verificados")
                st.rerun()


# ── Historial de versiones (solo los POE): ver, comparar y descargar para imprimir y firmar ──
def _versiones(protocolo_id: str) -> None:
    lista = versiones.listar(protocolo_id)   # la más reciente primero
    if not lista:
        with st.expander("📜 Historial de versiones"):
            st.caption("Todavía no hay versiones guardadas." if versiones.disponible() else versiones.FALTA_TABLA)
        return
    vigente = lista[0]
    sustituida = {v["version"]: lista[i - 1].get("created_at") for i, v in enumerate(lista) if i > 0}
    with st.expander(f"📜 Historial de versiones · vigente: v{vigente['version']} "
                     f"({plan.fecha_es(vigente.get('created_at'))})"):
        st.dataframe([{
            "Versión": f"v{v['version']}" + (" (vigente)" if v is vigente else ""),
            "Fecha": plan.fecha_es(v.get("created_at")), "Quién": v.get("cambiado_por") or "—",
            "Motivo": v.get("motivo") or "", "Cambios": (v.get("resumen") or "").replace("\n", " · "),
        } for v in lista], hide_index=True, width="stretch")
        numeros = [v["version"] for v in lista]
        por_numero = {v["version"]: v for v in lista}

        st.download_button(f"⬇️ Descargar la versión vigente (v{vigente['version']}, .md)",
                           versiones.como_markdown(vigente), file_name=f"procedimiento-v{vigente['version']}.md",
                           mime="text/markdown", key=f"ver-vigente-{protocolo_id}")
        ver = st.selectbox("Ver una versión", numeros, key=f"ver-{protocolo_id}",
                           format_func=lambda n: f"v{n} · {plan.fecha_es(por_numero[n].get('created_at'))}")
        elegida = por_numero[ver]
        st.markdown(f"**v{ver}** · {plan.fecha_es(elegida.get('created_at'))} · {elegida.get('cambiado_por') or '—'}  \n"
                    f"Motivo: {elegida.get('motivo') or '—'}")
        pasos = (elegida.get("snapshot") or {}).get("pasos") or []
        st.dataframe([{"Sección": p.get("seccion") or "", "Tarea": p["texto"], "Producto": p.get("producto") or "",
                       "Día": plan.DIAS_SEMANA.get(p.get("dia_semana"), ""),
                       "Semana": f"{p['semana_mes']}ª" if p.get("semana_mes") else ""} for p in pasos],
                     hide_index=True, width="stretch")
        st.download_button(f"⬇️ Descargar v{ver} (.md)", versiones.como_markdown(elegida, sustituida.get(ver)),
                           file_name=f"procedimiento-v{ver}.md", mime="text/markdown",
                           key=f"ver-descarga-{protocolo_id}-{ver}")

        if len(numeros) > 1:
            st.markdown("**Comparar dos versiones**")
            c1, c2 = st.columns(2)
            antes = c1.selectbox("De", numeros, index=1, format_func=lambda n: f"v{n}", key=f"cmp-a-{protocolo_id}")
            despues = c2.selectbox("A", numeros, index=0, format_func=lambda n: f"v{n}", key=f"cmp-b-{protocolo_id}")
            if antes == despues:
                st.caption("Elige dos versiones distintas.")
            else:
                a, b = sorted((antes, despues))
                cambios = versiones.diferencias(por_numero[a]["snapshot"], por_numero[b]["snapshot"])
                st.markdown(f"De v{a} a v{b}:")
                st.markdown("\n".join(f"- {x}" for x in cambios) if cambios else "Sin diferencias.")
