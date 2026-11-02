"""Editar procedimientos (POE del APPCC) y rutinas: datos, cuándo toca (frecuencia como en iAuditor) y pasos.
Página oculta (no sale en el menú): se abre con «✏️ Editar» en Procedimientos e inspecciones y vuelve con «← Volver».
Solo los POE son oficiales: cada cambio exige un motivo y crea una versión nueva en el historial (core/versiones.py).
Las rutinas se editan sin motivo y sin versiones."""
import streamlit as st

from core import db, plan, sesion, tabla, versiones
from core.procedimientos import NUEVO, PAGINA, etiqueta

local_id = st.session_state.local_id

# Viene de «✏️ Editar» en Procedimientos e inspecciones: deja elegido el procedimiento (y su categoría)
_desde = st.session_state.pop("editar_protocolo", None)
if _desde:
    _p = next((p for p in db.protocolos(local_id, solo_activos=False) if p["id"] == _desde), None)
    if _p:
        st.session_state["editar-categoria"] = plan.categoria(_p)
        st.session_state[f"editar-elegido-{plan.categoria(_p)}"] = _desde
st.session_state.setdefault("editar-categoria", "appcc")

def _volver() -> None:   # callback: los widgets de más abajo aún no existen al pulsar, pero su valor sí está en el estado
    cat = st.session_state.get("editar-categoria")
    sel = st.session_state.get(f"editar-elegido-{cat}")
    if sel and sel != NUEVO:
        st.session_state.protocolo_elegido = sel   # vuelve con este mismo procedimiento elegido
    st.session_state.pi_ir_a = "Procedimientos"
    st.session_state.editar_volver = True


st.button("← Volver", key="editar-volver", on_click=_volver)
if st.session_state.pop("editar_volver", False):
    st.switch_page(PAGINA)

st.title("✏️ Editar procedimientos")
st.caption("Crea y cambia los procedimientos (POE del APPCC) y las rutinas del local: datos, cuándo toca y pasos. "
           "Hacerlos y firmarlos se hace en Procedimientos e inspecciones. Solo los POE guardan versiones.")
st.session_state.setdefault("ver_nonce", 0)   # al guardar sube, y el «motivo del cambio» se vacía


def _editar(elegido: str, protocolo: dict, categoria: str, hay_columnas: bool) -> None:
    k = f"ed-{elegido}-"   # claves de los widgets de este procedimiento
    nuevo = elegido == NUEVO
    actual = plan.categoria(protocolo) if protocolo else categoria
    # Los POE son oficiales: también al pasar una rutina a POE, o un POE a rutina
    oficial_ahora = actual == "appcc"

    # ── Versión vigente y motivo del cambio ──
    vigente = None if nuevo else versiones.ultima(elegido)
    if not nuevo and oficial_ahora:
        if vigente:
            st.success(f"Versión vigente: **v{vigente['version']}** · {plan.fecha_es(vigente.get('created_at'))} · "
                       f"{vigente.get('cambiado_por') or '—'}  \nMotivo: {vigente.get('motivo') or '—'}")
        elif versiones.disponible():
            st.warning("Este procedimiento todavía no tiene versión. La primera vez que guardes un cambio (o con el "
                       "botón de abajo) se crea la v1.")
        else:
            st.warning(versiones.FALTA_TABLA)
    motivo = ""
    if not nuevo and oficial_ahora:   # solo los POE guardan versiones; las rutinas se editan sin más
        motivo = st.text_input(
            "Motivo del cambio *",
            key=f"{k}motivo-{st.session_state.ver_nonce}", placeholder="Por qué se cambia: normativa, error, mejora…",
            help="Es obligatorio para guardar cualquier cambio: queda en el historial de versiones con tu nombre y "
                 "la fecha.")
        motivo = motivo.strip()
        if oficial_ahora and not vigente and versiones.disponible() \
                and st.button("Crear versión inicial v1", key=k + "v1"):
            versiones.guardar_version(elegido, motivo or "Versión inicial", sesion.nombre() or None)
            st.session_state.ver_nonce += 1
            st.toast("Versión inicial v1 creada")
            st.rerun()

    def _registrar_version(es_poe: bool) -> str | None:
        """Crea la versión nueva (solo de los POE) si el contenido ha cambiado. Devuelve un texto para el aviso."""
        if not es_poe:
            return None
        creada = versiones.guardar_version(elegido, motivo or "Sin motivo indicado", sesion.nombre() or None)
        st.session_state.ver_nonce += 1
        return f" · versión v{creada['version']}" if creada else None

    c1, c2 = st.columns([3, 2])
    nombre = c1.text_input("Nombre *", protocolo.get("nombre", ""), placeholder="Apertura", key=k + "nombre")
    tipos = list(plan.TIPOS_PROTOCOLO)
    tipo = c2.selectbox("Tipo", tipos, format_func=plan.TIPOS_PROTOCOLO.get,
                        index=tipos.index(protocolo.get("tipo", "otro")), key=k + "tipo")
    categoria_nueva = st.segmented_control(
        "Categoría", list(plan.CATEGORIAS), format_func=plan.CATEGORIAS.get, required=True, key=k + "categoria",
        default=actual,
        help="Los procedimientos (POE) son los oficiales del APPCC; las rutinas, las del día a día. "
             "Al cambiarla, pasa a la otra página.")
    oficial = oficial_ahora or categoria_nueva == "appcc"

    st.markdown("**Cuándo toca**")
    frecuencia = st.segmented_control(
        "Frecuencia", list(plan.FRECUENCIAS_POE), format_func=plan.FRECUENCIAS_POE.get, required=True,
        default=protocolo.get("frecuencia") or "diaria", key=k + "frecuencia")
    dias_semana = semana_mes = mes_periodo = None
    if frecuencia == "semanal":
        dias_semana = st.segmented_control(
            "Días", list(plan.DIAS_CORTOS), selection_mode="multi", format_func=plan.DIAS_CORTOS.get,
            default=protocolo.get("dias_semana") or [1], key=k + "dias") or None
    elif frecuencia == "trimestral":
        mes_periodo = st.segmented_control(
            "Mes del trimestre", list(plan.MESES_TRIMESTRE), format_func=plan.MESES_TRIMESTRE.get, required=True,
            default=protocolo.get("mes_periodo") if protocolo.get("mes_periodo") in plan.MESES_TRIMESTRE else 1,
            key=k + "mes_trimestre")
    elif frecuencia == "anual":
        mes_periodo = st.segmented_control(
            "Mes", list(plan.MESES), format_func=plan.MESES.get, required=True,
            default=protocolo.get("mes_periodo") or 1, key=k + "mes")
    dia_mes = None
    veces_dia = 1
    if frecuencia in ("mensual", "trimestral", "anual"):
        modo = st.segmented_control(
            "Dentro del mes", ["semana", "dia"], format_func={"semana": "Semana del mes", "dia": "Día del mes"}.get,
            required=True, default="dia" if protocolo.get("dia_mes") else "semana", key=k + "modo_mes")
        if modo == "dia":
            dia_mes = st.number_input(
                "Día del mes", 1, 31, int(protocolo.get("dia_mes") or 1), step=1, key=k + "dia_mes",
                help="Sale en Hoy desde ese día hasta que alguien lo registre. Si el mes es más corto "
                     "(31 en febrero), toca el último día.")
        else:
            semana_mes = st.segmented_control(
                "Semana del mes", list(plan.SEMANAS_MES), format_func=plan.SEMANAS_MES.get,
                default=protocolo.get("semana_mes"), key=k + "semana",
                help="Sale en Hoy toda esa semana hasta que alguien lo registre. Sin elegir: todo el mes.")
    else:
        veces_dia = st.number_input(
            "Veces al día", 1, 6, plan.veces_dia(protocolo), step=1, key=k + "veces_dia",
            help="Si se hace más de una vez al día (aseos, por ejemplo), en Hoy sigue pendiente hasta registrarlo "
                 "todas las veces.")
    c1, c2 = st.columns([3, 1])
    franja = c1.segmented_control("Momento", list(plan.FRANJAS), format_func=plan.FRANJAS.get,
                                  default=plan.franja(protocolo), key=k + "franja")
    hora_limite = c2.time_input("Hora límite (opcional)", plan.hora_limite(protocolo), step=900, key=k + "hora",
                                help="Si a esa hora no está registrado, sale en «Necesita atención» de Hoy.")
    if frecuencia == "semanal" and not dias_semana:
        st.caption("Sin días elegidos sale todos los días.")
    if protocolo.get("momento"):
        st.caption(f"Antes se indicaba: «{protocolo['momento']}»")

    descripcion = st.text_area("Descripción / instrucciones generales", protocolo.get("descripcion") or "",
                               key=k + "descripcion")
    c1, c2 = st.columns(2)
    if oficial:   # en los POE la versión la lleva el historial, no se escribe a mano
        version = protocolo.get("version") or ""
        c1.caption("La versión la lleva el historial de versiones.")
    else:
        version = c1.text_input("Versión", protocolo.get("version") or "", key=k + "version")
    activo = c2.checkbox("Activo", value=protocolo.get("activo", True), key=k + "activo")
    if not hay_columnas:
        st.warning("Falta ejecutar `supabase/procedimientos.sql` en Supabase: hasta entonces la categoría, la "
                   "frecuencia, el momento y la hora límite no se guardan.")
    if st.button("Guardar", type="primary", key=k + "guardar"):
        if not nombre.strip():
            st.error("El nombre es obligatorio.")
            return
        if not nuevo and oficial and not motivo:
            if oficial_ahora:
                st.error("Indica el motivo del cambio: los procedimientos oficiales (POE) lo exigen para guardar.")
                return
            motivo = "Pasa a ser procedimiento oficial (POE)"   # una rutina que se convierte en POE
        datos = {"local_id": local_id, "nombre": nombre.strip(), "tipo": tipo,
                 "descripcion": descripcion.strip() or None, "version": version.strip() or None, "activo": activo}
        if hay_columnas:
            datos |= {"categoria": categoria_nueva, "frecuencia": frecuencia,
                      "dias_semana": sorted(dias_semana) if dias_semana else None, "semana_mes": semana_mes,
                      "mes_periodo": mes_periodo, "franja": franja, "dia_mes": dia_mes, "veces_dia": int(veces_dia),
                      "hora_limite": hora_limite.strftime("%H:%M") if hora_limite else None}
        if nuevo:
            db.table("protocolos").insert(datos).execute()
            st.toast("Creado: ahora elígelo arriba y añade sus pasos"
                     + (" (la versión v1 se crea al guardar los pasos)" if oficial else ""))
        else:
            db.table("protocolos").update(datos).eq("id", elegido).execute()
            aviso = _registrar_version(oficial)
            st.toast("Guardado" + (aviso or "")
                     + ("" if categoria_nueva == actual or not hay_columnas else
                        f" · ahora es {'un procedimiento (POE)' if categoria_nueva == 'appcc' else 'una rutina'}"))
        st.cache_data.clear()
        st.rerun()

    if not nuevo:
        st.markdown("**Pasos** · se muestran en orden los días que toca; los que tienen día de la semana o semana del "
                    "mes solo salen ese día. Añade filas al final; para borrar, selecciona la fila y pulsa la papelera."
                    + (" Cada cambio de pasos pide el motivo de arriba y crea una versión nueva." if oficial_ahora else ""))

        def _motivo_pasos() -> str | None:
            if oficial_ahora and not motivo:
                return "Indica el motivo del cambio (arriba): los procedimientos oficiales (POE) lo exigen para guardar."
            return None

        def _version_pasos() -> None:
            _registrar_version(oficial_ahora)

        tabla.editar("protocolo_pasos", db.pasos(elegido), {
            "orden": st.column_config.NumberColumn("Orden", min_value=1, step=1, required=True, width="small"),
            "seccion": st.column_config.TextColumn("Sección", help="Agrupa los pasos: Cocina, Barra, Sala…"),
            "texto": st.column_config.TextColumn("Tarea", required=True, width="large"),
            "producto": st.column_config.TextColumn("Producto", help="Códigos de productos de limpieza: P1 + P3"),
            "dia_semana": st.column_config.SelectboxColumn("Solo el día", options=list(plan.DIAS_SEMANA),
                                                           format_func=plan.DIAS_SEMANA.get),
            "semana_mes": st.column_config.SelectboxColumn("Solo la semana", options=[1, 2, 3, 4, 5],
                                                           format_func=lambda n: f"{n}ª del mes"),
        }, fijos={"protocolo_id": elegido}, clave=f"pasos-{elegido}", obligatorias=("orden", "texto"),
            validar=_motivo_pasos, al_guardar=_version_pasos, archivar=True)


# ── Qué se edita: POE o rutinas, y el procedimiento concreto ──
categoria = st.segmented_control("Qué editar", list(plan.CATEGORIAS), format_func=plan.CATEGORIAS.get, required=True,
                                 key="editar-categoria")
todos = db.protocolos(local_id, solo_activos=False)
# Antes de ejecutar supabase/procedimientos.sql no existen las columnas nuevas: se ve todo, pero no se guardan
hay_columnas = not todos or all(c in todos[0] for c in ("frecuencia", "veces_dia", "dia_mes"))
protocolos = [p for p in todos if plan.categoria(p) == categoria]
por_id = {p["id"]: p for p in protocolos}
opciones = [p["id"] for p in protocolos if p["activo"]] + [p["id"] for p in protocolos if not p["activo"]] + [NUEVO]
clave = f"editar-elegido-{categoria}"
if st.session_state.get(clave) not in opciones:
    st.session_state.pop(clave, None)
elegido = st.selectbox(
    "Procedimiento" if categoria == "appcc" else "Rutina", opciones, key=clave,
    format_func=lambda i: ("➕ Crear procedimiento nuevo" if categoria == "appcc" else "➕ Crear rutina nueva")
    if i == NUEVO else etiqueta(por_id[i]))
_editar(elegido, por_id.get(elegido, {}), categoria, hay_columnas)
