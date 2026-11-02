"""Hoy: como la lista de «encender un avión». Una fila por rutina y un toque para decir que todo está bien;
solo se marca lo que falla. El detalle está en las otras páginas."""
from datetime import date, datetime
from html import escape

import streamlit as st

from core import acciones, avisos, db, ia, plan, procedimientos, sesion

local_id = st.session_state.local_id
hoy = date.today()
yo = sesion.nombre()
obligados = acciones.obligados_paso_a_paso(sesion.actual()["id"])   # protocolos que debo revisar tarea por tarea
MAX_ATENCION = 5   # líneas de «Necesita atención» antes de resumir

# Filas finas en vez de tarjetas: una línea por cosa, con una raya suave entre filas
st.markdown("""<style>
[class*='st-key-fila-'] {border-bottom: 1px solid rgba(120,113,108,.18); padding: .1rem 0 .3rem}
[class*='st-key-fila-'] p {margin: 0}
.pista {color: #78716C; font-size: .85rem}
.hecha, .hecha strong {color: #A8A29E}
</style>""", unsafe_allow_html=True)

st.title(f"Hoy · {plan.DIAS_SEMANA[hoy.isoweekday()]} {plan.fecha_es(hoy)}")


def _hora(registro: dict) -> str:
    return datetime.fromisoformat(registro["created_at"]).astimezone().strftime("%H:%M")


def _ir_a_protocolos(protocolo: dict) -> None:
    st.session_state.protocolo_elegido = protocolo["id"]
    st.switch_page(procedimientos.PAGINA)   # Procedimientos e inspecciones, con este elegido


def _algo_falla(protocolo: dict, pasos: list[dict], etiqueta: str, rapido: bool = False, marcado: bool = True,
                tipo: str = "tertiary") -> None:
    """Desplegable con la lista del día. Normalmente ya marcada: se desmarca solo lo que ha fallado y se registra.
    En revisión paso a paso (marcado=False) sale sin marcar y hay que comprobar cada tarea."""
    with st.popover(etiqueta, type=tipo):
        if rapido and acciones.registro_rapido(protocolo, pasos, clave=f"otra-{protocolo['id']}", tipo="primary"):
            st.toast(f"{protocolo['nombre']} registrado")
            st.rerun()
        st.caption("Desmarca lo que no se ha podido hacer y registra." if marcado else
                   "Comprueba cada tarea y márcala al terminarla. Si algo no se ha hecho, explica por qué.")
        with st.form(f"falla-{protocolo['id']}", border=False):
            marcados, seccion = {}, None
            for paso in pasos:
                if paso.get("seccion") and paso["seccion"] != seccion:
                    seccion = paso["seccion"]
                    st.caption(f"**{seccion}**")
                texto = paso["texto"] + (f" · _{paso['producto']}_" if paso.get("producto") else "")
                marcados[paso["id"]] = st.checkbox(texto, value=marcado, key=f"paso-{protocolo['id']}-{paso['id']}")
            incidencia = st.text_input("¿Qué ha pasado? (opcional)", placeholder="Ej: falta desengrasante",
                                       key=f"incidencia-{protocolo['id']}")
            if st.form_submit_button("Registrar", type="primary", width="stretch"):
                if not marcado and not all(marcados.values()) and not incidencia.strip():
                    st.error("Faltan tareas por marcar: explica qué ha pasado.")
                else:
                    acciones.registrar_protocolo(protocolo["id"], yo, hoy, marcados, incidencias=incidencia)
                    fallos = sum(not v for v in marcados.values())
                    # la próxima vez la lista vuelve a salir como al principio
                    for clave in [k for k in st.session_state if str(k).startswith(f"paso-{protocolo['id']}-")]:
                        del st.session_state[clave]
                    st.session_state.pop(f"incidencia-{protocolo['id']}", None)
                    st.toast(f"{protocolo['nombre']} registrado" + (f" · {fallos} sin hacer" if fallos else ""))
                    st.rerun()
        if sesion.puede("gerente") and st.button("Ver tareas", key=f"ver-{protocolo['id']}", type="tertiary", icon="📋"):
            _ir_a_protocolos(protocolo)


# ── Avería: un aviso (flag) que deja el equipo averiado, abre su procedimiento y genera un informe ──
equipos_local = db.equipos(local_id)
with st.popover("🚩 Avisar de una avería", type="secondary"):
    if not equipos_local:
        st.caption("Este local aún no tiene equipos.")
    else:
        with st.form("avisar-averia", border=False, clear_on_submit=True):
            equipo_id = st.selectbox("Equipo", [e["id"] for e in equipos_local], index=None,
                                     placeholder="Elige el equipo…",
                                     format_func=lambda i: next(e["nombre"] for e in equipos_local if e["id"] == i))
            que_pasa = st.text_input("¿Qué pasa?", placeholder="Ej: no enfría, hace ruido, gotea…")
            afecta = st.toggle("¿Afecta a alimentos?")
            if st.form_submit_button("🚩 Avisar", type="primary", width="stretch"):
                if not equipo_id or not que_pasa.strip():
                    st.error("Elige el equipo y cuenta qué pasa.")
                else:
                    equipo = next(e for e in equipos_local if e["id"] == equipo_id)
                    texto = acciones.avisar_averia(equipo, que_pasa, afecta, yo)
                    st.session_state.averia_activa = {"equipo_id": equipo_id, "que_pasa": texto, "registrado": False}
                    st.session_state.pop("averia_ia", None)
                    st.rerun()

activa = st.session_state.get("averia_activa")
if activa:
    equipo = next((e for e in db.equipos(local_id) if e["id"] == activa["equipo_id"]), None)
    if equipo is None:
        st.session_state.pop("averia_activa")
    else:
        with st.container(border=True, key="fila-averia"):
            st.markdown(f"🚩 **Avería avisada · {escape(equipo['nombre'])}** <span class='pista'>{escape(activa['que_pasa'])}"
                        f" · equipo marcado como averiado</span>", unsafe_allow_html=True)
            if not activa["registrado"]:
                procs = acciones.procedimientos_averia(local_id, equipo)
                if not procs:
                    st.caption("No hay un procedimiento de avería definido para este local.")
                else:
                    proc = procs[0] if len(procs) == 1 else st.selectbox(
                        "Procedimiento", procs, format_func=lambda p: p["nombre"], key="averia-proc")
                    st.caption(f"**{proc['nombre']}**: marca lo que ya has hecho.")
                    with st.form("averia-pasos", border=False):
                        marcados = {}
                        for paso in db.pasos(proc["id"]):
                            marcados[paso["id"]] = st.checkbox(paso["texto"], value=False, key=f"averia-paso-{paso['id']}")
                        nota = st.text_input("Algo más (opcional)", key="averia-nota")
                        if st.form_submit_button("Registrar lo hecho", type="primary", width="stretch"):
                            incidencia = acciones.incidencia_averia(equipo, activa["que_pasa"]) + \
                                (f" · {nota.strip()}" if nota.strip() else "")
                            acciones.registrar_protocolo(proc["id"], yo, hoy, marcados, incidencias=incidencia)
                            activa["registrado"] = True
                            st.toast(f"{proc['nombre']} registrado")
                            st.rerun()
            else:
                st.caption("✅ Procedimiento registrado.")
            with st.container(horizontal=True, gap="small", vertical_alignment="center"):
                if ia.disponible() and st.button("✨ Pedir ayuda", key="averia-ia-boton"):
                    with st.spinner("Pensando…"):
                        try:
                            st.session_state.averia_ia = ia.ayuda_averia(
                                equipo, activa["que_pasa"], db.bitacora([equipo["id"]], 15))
                        except ia.ErrorIA as e:
                            st.session_state.averia_ia = f"⚠️ {e}"
                evento = acciones.ultima_averia(equipo["id"])
                if evento:
                    acciones.boton_informe_averia(equipo, evento, clave="averia-informe-hoy")
                if st.button("Cerrar", key="averia-cerrar", type="tertiary"):
                    st.session_state.pop("averia_activa", None)
                    st.session_state.pop("averia_ia", None)
                    st.rerun()
            if st.session_state.get("averia_ia"):
                st.markdown(st.session_state.averia_ia)

# ── Rutinas de hoy: pendientes arriba con «Todo bien»; hechas abajo, en gris ──
# Toca hoy si el procedimiento toca por su frecuencia y alguno de sus pasos toca hoy. Lo mensual, trimestral o anual
# sigue pendiente toda su semana (o su mes) hasta que alguien lo registra.
protocolos = [p for p in db.protocolos(local_id) if p["tipo"] != "averia" and plan.procedimiento_toca(p, hoy)]
ventanas = {p["id"]: plan.ventana(p, hoy) for p in protocolos}
desde = min((v[0] for v in ventanas.values()), default=hoy)
registros = db.registros_protocolo([p["id"] for p in protocolos], 1000, desde=desde.isoformat())
rutinas = []
for protocolo in protocolos:
    pasos_hoy = [p for p in db.pasos(protocolo["id"]) if plan.paso_toca(p, hoy)]
    if pasos_hoy:
        inicio = ventanas[protocolo["id"]][0].isoformat()
        hechos = sorted((r for r in registros if r["protocolo_id"] == protocolo["id"] and r["fecha"] >= inicio),
                        key=lambda r: (r["fecha"], r["created_at"]))
        rutinas.append((protocolo, pasos_hoy, hechos))


def _de_hoy(hechos: list[dict]) -> list[dict]:
    return [r for r in hechos if r["fecha"] == hoy.isoformat()]


def _completa(protocolo: dict, hechos: list[dict]) -> bool:
    """Hecha: con una sola vez al día basta un registro en su ventana; con varias, todas las de hoy."""
    veces = plan.veces_dia(protocolo)
    return len(_de_hoy(hechos)) >= veces if veces > 1 else bool(hechos)


# Las de varias veces al día siguen pendientes hasta registrarlas todas
pendientes = sorted((r for r in rutinas if not _completa(r[0], r[2])), key=lambda r: plan.orden_franja(r[0]))   # apertura → cierre
hechas = sorted((r for r in rutinas if _completa(r[0], r[2])), key=lambda r: (r[2][-1]["fecha"], r[2][-1]["created_at"]))
ahora = datetime.now().time()
# Pasada la hora límite sin registrar (el último día de su ventana): sale en «Necesita atención»
atrasadas = [p for p, _, _ in pendientes
             if plan.hora_limite(p) and ventanas[p["id"]][1] == hoy and ahora > plan.hora_limite(p)]


def _pista_rutina(protocolo: dict) -> list[str]:
    """Cuándo se hace: franja del día, frecuencia si no es diaria y hora límite."""
    limite = plan.hora_limite(protocolo)
    return [plan.texto_franja(protocolo),
            plan.describir_frecuencia(protocolo) if (protocolo.get("frecuencia") or "diaria") != "diaria" else None,
            f"antes de las {limite:%H:%M}" if limite else None]

if enc := st.session_state.pop("hoy_encargo", None):   # el equipo llega desde «▶️ Hacerlo» de un encargo de Rumbo
    nombre_enc = next((p["nombre"] for p, _, _ in pendientes if p["id"] == enc), None)
    if nombre_enc:
        st.info(f"👉 Tu encargo: **{nombre_enc}**. Está en la lista de abajo: «Todo bien» o «Algo falla» para registrarla.")
    else:
        st.info("Ese encargo no está pendiente hoy en tu lista de rutinas. Si ya está hecho, se da por cumplido al "
                "registrarlo; si no, díselo a quien te lo encargó.")
if rutinas:
    st.markdown(f"**Rutinas de hoy** · {len(hechas)} de {len(rutinas)}"
                + (" · todo hecho ✅" if not pendientes else ""))
for protocolo, pasos_hoy, hechos in pendientes:
    with st.container(horizontal=True, vertical_alignment="center", gap="small", key=f"fila-{protocolo['id']}"):
        paso_a_paso = acciones.va_paso_a_paso(protocolo["id"], obligados)
        veces, de_hoy = plan.veces_dia(protocolo), _de_hoy(hechos)
        avance = None
        if veces > 1:   # «2 veces al día» o, si ya se ha hecho alguna, «1 de 2 hoy»
            avance = f"✅ {len(de_hoy)} de {veces} · {_hora(de_hoy[-1])} {de_hoy[-1].get('realizado_por') or ''}".strip() \
                if de_hoy else f"🔁 {veces} veces al día"
        pista = " · ".join(x for x in (f"{len(pasos_hoy)} tareas", avance, *_pista_rutina(protocolo),
                                       "tarea por tarea" if paso_a_paso else None) if x)
        icono = "⏰" if protocolo in atrasadas else "⏳"
        st.markdown(f"{icono} **{escape(protocolo['nombre'])}** <span class='pista'>{escape(pista)}</span>",
                    unsafe_allow_html=True, width="stretch")
        if paso_a_paso:   # sin «Todo bien»: hay que marcar cada tarea
            _algo_falla(protocolo, pasos_hoy, "📋 Revisar tareas", marcado=False, tipo="primary")
            continue
        if acciones.registro_rapido(protocolo, pasos_hoy, clave=f"rapido-{protocolo['id']}", width="content",
                                    tipo="primary"):
            st.toast(f"{protocolo['nombre']} registrado")
            st.rerun()
        _algo_falla(protocolo, pasos_hoy, "Algo falla")
for protocolo, pasos_hoy, hechos in hechas:
    with st.container(horizontal=True, vertical_alignment="center", gap="small", key=f"fila-{protocolo['id']}"):
        ultimo = hechos[-1]
        icono = "✅" if all(r["completado"] for r in hechos) else "⚠️"
        cuando = _hora(ultimo) if ultimo["fecha"] == hoy.isoformat() else f"el {plan.fecha_es(ultimo['fecha'])[:5]}"
        veces = plan.veces_dia(protocolo)
        if veces > 1:   # las de varias veces al día: todas las horas
            pista = f"hecho {len(_de_hoy(hechos))} de {veces} veces · " + \
                ", ".join(f"{_hora(r)} {r.get('realizado_por') or '—'}" for r in _de_hoy(hechos))
        else:
            pista = f"hecho {cuando} · {ultimo.get('realizado_por') or '—'}" + (f" · {len(hechos)} veces" if len(hechos) > 1 else "")
        if not ultimo["completado"]:
            pista += " · con fallos"
        st.markdown(f"<span class='hecha'>{icono} <strong>{escape(protocolo['nombre'])}</strong></span> "
                    f"<span class='pista'>{escape(pista)}</span>", unsafe_allow_html=True, width="stretch")
        paso_a_paso = acciones.va_paso_a_paso(protocolo["id"], obligados)
        _algo_falla(protocolo, pasos_hoy, "Otra vez", rapido=not paso_a_paso, marcado=not paso_a_paso)

# ── Tu rumbo (encargos) ──
try:
    from core import rumbo
    rumbo.en_hoy()
except ImportError:   # el módulo de Rumbo aún no existe
    pass

# ── Comunicados que me faltan por leer: una línea cada uno ──
try:
    comunicados = db.comunicados(local_id)
    leidos = {l["comunicado_id"] for l in db.lecturas([c["id"] for c in comunicados]) if l["trabajador"] == yo}
except Exception:  # la tabla aún no existe en Supabase
    comunicados, leidos = [], set()
sin_leer = [c for c in comunicados if c["id"] not in leidos]
if sin_leer:
    st.markdown(f"**Comunicados** · {len(sin_leer)} sin leer")
    for comunicado in sin_leer:
        with st.container(horizontal=True, vertical_alignment="center", gap="small", key=f"fila-com-{comunicado['id']}"):
            st.markdown(f"📣 {escape(comunicado['titulo'])}", unsafe_allow_html=True, width="stretch")
            with st.popover("Leer", type="tertiary"):
                if comunicado.get("texto"):
                    st.markdown(comunicado["texto"])
                if comunicado.get("enlace"):
                    st.link_button("Abrir documento", comunicado["enlace"])
                if st.button("He leído y entendido", key=f"leido-{comunicado['id']}", type="primary"):
                    db.table("comunicado_lecturas").insert({"comunicado_id": comunicado["id"], "trabajador": yo}).execute()
                    st.toast("Lectura confirmada")
                    st.rerun()

# ── Necesita atención: solo lo vencido o averiado, una línea cada cosa ──
vencido = avisos.recopilar(todos=True)
averiados = [e for e in db.equipos(local_id) if e["estado"] in ("averiado", "en_reparacion")]
local_nombre = next((l["nombre"] for l in db.locales() if l["id"] == local_id), "")
lineas = [f"⏰ **{p['nombre']}** sin registrar · límite {plan.hora_limite(p):%H:%M}" for p in atrasadas]
lineas += [f"{plan.ESTADOS_EQUIPO[e['estado']]} · **{e['nombre']}**" for e in averiados]
lineas += [f"{apartado.split()[0]} {linea}" for apartado, ls in vencido.get(local_nombre, {}).items() for linea in ls]
if lineas:
    st.markdown(f"**Necesita atención** · {len(lineas)}")
    resto = len(lineas) - MAX_ATENCION
    st.markdown("  \n".join(lineas[:MAX_ATENCION]) + (f"  \n<span class='pista'>y {resto} más</span>" if resto > 0 else ""),
                unsafe_allow_html=True)
    if sesion.puede("gerente"):   # Alertas es de gerencia; el equipo solo lo ve
        st.page_link("paginas/alertas.py", label="Ir a Alertas para marcarlo como hecho", icon="🔔")
else:
    st.caption("Mantenimiento al día: nada vencido ni averiado ✅")

# ── Asistente: una sola caja abajo; la respuesta sale aquí mismo (solo consulta, no registra nada) ──
if ia.disponible():
    chat = st.session_state.setdefault("chat_asistente", [])   # la misma conversación que la página Asistente
    pregunta = st.chat_input("Pide ayuda o dicta lo que has hecho…")
    if pregunta:
        chat.append({"role": "user", "content": pregunta})
        with st.spinner("Pensando…"):
            try:
                respuesta = ia.asistente(chat[-10:], local_id)
            except ia.ErrorIA as e:
                respuesta = f"⚠️ {e}"
        chat.append({"role": "assistant", "content": respuesta})
    if chat:
        st.markdown("**Asistente**")
        for mensaje in chat[-2:]:   # solo la última pregunta y su respuesta
            with st.chat_message(mensaje["role"]):
                st.markdown(mensaje["content"])
        with st.container(horizontal=True, gap="small"):
            if len(chat) > 2:
                st.page_link("paginas/asistente.py", label="Ver toda la conversación", icon="✨")
            if st.button("Borrar", type="tertiary", key="borrar-chat-hoy"):
                st.session_state.chat_asistente = []
                st.rerun()
