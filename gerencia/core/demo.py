"""Modo demostración: la app funciona sin Supabase, con datos inventados que viven en la sesión de cada visitante.

Se activa solo cuando no hay claves de Supabase (db.modo_demo). Imita la parte del cliente de Supabase que usa la app
(select, filtros, order, limit, insert, update, delete…). Lo que se cambia se pierde al cerrar la pestaña, así que cada
visita empieza de cero y un visitante nunca ve lo que ha hecho otro. Todos los nombres, teléfonos y registros son
inventados.
"""
import copy
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import streamlit as st

PINES = {"Gerente": "1111", "Trabajador": "2222"}
USUARIO_DIRECCION = ("direccion", "3333")

# Valores por defecto de las columnas, como en supabase/*.sql
_DEFECTOS = {
    "equipos": {"estado": "operativo"},
    "tareas_mantenimiento": {"activa": True},
    "servicios": {"activo": True, "categoria": "otro"},
    "productos_limpieza": {"activo": True, "ficha_tecnica": False, "ficha_seguridad": False},
    "protocolos": {"activo": True, "tipo": "otro"},
    "protocolo_pasos": {"activo": True},
    "protocolo_registros": {"completado": False},
    "comunicados": {"activo": True},
    "trabajadores": {"rol": "staff", "activo": True},
}
_HOY_POR_DEFECTO = {"bitacora_equipos": "fecha", "protocolo_registros": "fecha"}
_BORRADO_EN_CASCADA = {
    "equipos": [("tareas_mantenimiento", "equipo_id"), ("bitacora_equipos", "equipo_id")],
    "protocolos": [("protocolo_pasos", "protocolo_id"), ("protocolo_registros", "protocolo_id")],
    "protocolo_registros": [("protocolo_registro_pasos", "registro_id")],
    "comunicados": [("comunicado_lecturas", "comunicado_id")],
}
# select("hecho, protocolo_pasos(texto, orden)"): tabla relacionada -> columna que la enlaza
_RELACIONES = {"protocolo_pasos": "paso_id"}
_ANIDADA = re.compile(r"(\w+)\(")


def _almacen() -> dict[str, list[dict]]:
    if "_demo_datos" not in st.session_state:
        st.session_state["_demo_datos"] = datos_iniciales()
    return st.session_state["_demo_datos"]


class _Respuesta:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


class _Consulta:
    def __init__(self, tabla: str):
        self.tabla, self._accion, self._valores = tabla, "select", None
        self._filtros, self._orden, self._limite, self._anidadas, self._contar = [], [], None, [], False

    def select(self, columnas: str = "*", count=None, **_):
        self._anidadas = _ANIDADA.findall(columnas)
        self._contar = bool(count)
        return self

    def insert(self, filas, **_):
        self._accion, self._valores = "insert", filas
        return self

    def upsert(self, filas, **_):
        self._accion, self._valores = "upsert", filas
        return self

    def update(self, valores, **_):
        self._accion, self._valores = "update", valores
        return self

    def delete(self, **_):
        self._accion = "delete"
        return self

    def _filtro(self, condicion):
        self._filtros.append(condicion)
        return self

    def eq(self, col, valor):
        return self._filtro(lambda f: f.get(col) == valor)

    def neq(self, col, valor):
        return self._filtro(lambda f: f.get(col) != valor)

    def gt(self, col, valor):
        return self._filtro(lambda f: f.get(col) is not None and str(f[col]) > str(valor))

    def gte(self, col, valor):
        return self._filtro(lambda f: f.get(col) is not None and str(f[col]) >= str(valor))

    def lt(self, col, valor):
        return self._filtro(lambda f: f.get(col) is not None and str(f[col]) < str(valor))

    def lte(self, col, valor):
        return self._filtro(lambda f: f.get(col) is not None and str(f[col]) <= str(valor))

    def in_(self, col, valores):
        valores = list(valores)
        return self._filtro(lambda f: f.get(col) in valores)

    def is_(self, col, valor):
        return self._filtro(lambda f: f.get(col) is None if valor in (None, "null") else f.get(col) == valor)

    def match(self, condiciones: dict):
        return self._filtro(lambda f: all(f.get(c) == v for c, v in condiciones.items()))

    def ilike(self, col, patron: str):
        texto = re.escape(patron.lower()).replace("%", ".*").replace("_", ".")
        return self._filtro(lambda f: re.fullmatch(texto, str(f.get(col) or "").lower()) is not None)

    def or_(self, condiciones: str):
        """Solo lo que usa la app: «col.eq.valor,col.is.null»."""
        partes = [c.split(".", 2) for c in condiciones.split(",")]

        def cumple(f):
            return any(f.get(col) is None if op == "is" else str(f.get(col)) == valor for col, op, valor in partes)
        return self._filtro(cumple)

    def order(self, col, desc=False, **_):
        self._orden.append((col, desc))
        return self

    def limit(self, n):
        self._limite = n
        return self

    def _coinciden(self, filas):
        return [f for f in filas if all(c(f) for c in self._filtros)]

    def _nueva(self, fila: dict) -> dict:
        ahora = datetime.now(timezone.utc).isoformat()
        nueva = {"id": str(uuid.uuid4()), "created_at": ahora, **_DEFECTOS.get(self.tabla, {}), **fila}
        if self.tabla in _HOY_POR_DEFECTO:
            nueva.setdefault(_HOY_POR_DEFECTO[self.tabla], date.today().isoformat())
        return nueva

    def _borrar_relacionadas(self, tabla: str, fila: dict, datos: dict) -> None:
        for hija, columna in _BORRADO_EN_CASCADA.get(tabla, []):
            for resto in [h for h in datos.get(hija, []) if h.get(columna) == fila.get("id")]:
                datos[hija].remove(resto)
                self._borrar_relacionadas(hija, resto, datos)

    def execute(self):
        datos = _almacen()
        filas = datos.setdefault(self.tabla, [])
        if self._accion in ("insert", "upsert"):
            nuevas = [self._nueva(f) for f in (self._valores if isinstance(self._valores, list) else [self._valores])]
            if self._accion == "upsert":
                claves = {f.get("id") for f in nuevas} | {f.get("clave") for f in nuevas if "clave" in f}
                filas[:] = [f for f in filas if f.get("id") not in claves and f.get("clave") not in claves]
            filas.extend(nuevas)
            return _Respuesta(copy.deepcopy(nuevas))
        elegidas = self._coinciden(filas)
        if self._accion == "update":
            for fila in elegidas:
                fila.update(self._valores)
            return _Respuesta(copy.deepcopy(elegidas))
        if self._accion == "delete":
            for fila in elegidas:
                filas.remove(fila)
                self._borrar_relacionadas(self.tabla, fila, datos)
            return _Respuesta(copy.deepcopy(elegidas))
        resultado = copy.deepcopy(elegidas)
        for col, desc in reversed(self._orden):   # el primer order() es el que manda
            resultado.sort(key=lambda f: (f.get(col) is None, str(f.get(col) if f.get(col) is not None else "")),
                           reverse=desc)
        total = len(resultado)
        if self._limite is not None:
            resultado = resultado[:self._limite]
        for anidada in self._anidadas:
            enlace = _RELACIONES.get(anidada)
            for fila in resultado:
                fila[anidada] = next((copy.deepcopy(o) for o in datos.get(anidada, []) if o.get("id") == fila.get(enlace)),
                                     None)
        return _Respuesta(resultado, total if self._contar else None)


class Cliente:
    def table(self, nombre: str) -> _Consulta:
        return _Consulta(nombre)


# ── Datos inventados ──
def datos_iniciales() -> dict[str, list[dict]]:
    from core import sesion

    hoy = date.today()

    def dia(n: int) -> str:
        return (hoy + timedelta(days=n)).isoformat()

    def momento(n: int, hora: int = 9) -> str:
        return datetime.combine(hoy + timedelta(days=n), datetime.min.time(), timezone.utc).replace(hour=hora).isoformat()

    locales = [{"id": "sagrada-familia", "nombre": "Lilo Sagrada Familia"},
               {"id": "enric-granados", "nombre": "Lilo Enric Granados"},
               {"id": "madrid", "nombre": "Lilo Madrid"}]
    sf = "sagrada-familia"

    def persona(id_, nombre, rol, local, pin=None, usuario=None):
        return {"id": id_, "name": nombre, "rol": rol, "local_id": local, "locales": [local] if local else None,
                "activo": True, "usuario": usuario, "created_at": momento(-60),
                "pin_hash": sesion.huella(pin) if pin else None}

    trabajadores = [
        persona("demo-gerente", "Marta Prueba", "gerente", sf, PINES["Gerente"]),
        persona("demo-staff", "Pablo Ejemplo", "staff", sf, PINES["Trabajador"]),
        persona("demo-direccion", "Sara Ficticia", "directivo", None, USUARIO_DIRECCION[1], USUARIO_DIRECCION[0]),
        persona("demo-staff-2", "Nico Inventado", "staff", sf),
        persona("demo-gerente-2", "Elena Muestra", "gerente", "enric-granados"),
        persona("demo-gerente-3", "Óscar Simulado", "gerente", "madrid"),
    ]

    def proveedor(id_, nombre, servicio, contacto, telefono):
        return {"id": id_, "nombre": nombre, "servicio": servicio, "contacto": contacto, "telefono": telefono,
                "email": f"{id_}@ejemplo.invalid", "documentacion": None, "notas": "Proveedor inventado",
                "created_at": momento(-60)}

    proveedores = [
        proveedor("prov-frio", "Frío Ejemplo S.L.", "Frío y neveras", "Técnico de guardia", "600 000 001"),
        proveedor("prov-maq", "Maquinaria Muestra", "Maquinaria de cocina", "Atención técnica", "600 000 002"),
        proveedor("prov-plagas", "Plagas Ficticias", "Control de plagas", "Oficina", "600 000 003"),
        proveedor("prov-cafe", "Café Técnico Demo", "Cafetera", "Posventa", "600 000 004"),
    ]

    def equipo(id_, nombre, tipo, zona, marca, modelo, proveedor_id=None, temp=(None, None), estado="operativo",
               garantia=None, local=sf, notas=None):
        return {"id": id_, "local_id": local, "nombre": nombre, "tipo": tipo, "zona": zona, "marca": marca,
                "modelo": modelo, "numero_serie": f"DEMO-{id_.upper()}", "fecha_compra": dia(-700),
                "garantia_hasta": garantia, "servicio_tecnico": None, "contacto_tecnico": None,
                "temp_min": temp[0], "temp_max": temp[1], "estado": estado, "notas": notas, "foto_url": None,
                "capacidad": None, "proveedor_id": proveedor_id, "revision_frecuencia": None, "revision_detalle": None,
                "ultima_revision": None, "proxima_revision": None, "created_at": momento(-60)}

    equipos = [
        equipo("nevera-barra", "Nevera barra", "nevera", "Barra", "MarcaFrío", "BF-200", "prov-frio", (0, 5),
               garantia=dia(90)),
        equipo("nevera-cocina", "Nevera cocina 1", "nevera", "Cocina", "MarcaFrío", "CF-500", "prov-frio", (0, 5),
               estado="averiado", notas="No llega a la temperatura desde ayer"),
        equipo("congelador", "Congelador", "congelador", "Almacén", "PoloDemo", "PD-300", "prov-frio", (-22, -18)),
        equipo("horno", "Horno de convección", "horno", "Cocina", "HornoMuestra", "HM-10", "prov-maq"),
        equipo("plancha", "Plancha eléctrica", "plancha", "Cocina", "HornoMuestra", "PL-90", "prov-maq"),
        equipo("cafetera", "Cafetera de dos grupos", "cafetera", "Barra", "CaféDemo", "CD-2", "prov-cafe"),
        equipo("lavavajillas", "Lavavajillas", "lavavajillas", "Office", "LavaEjemplo", "LE-40", "prov-maq"),
        equipo("nevera-eg", "Nevera sala", "nevera", "Sala", "MarcaFrío", "BF-200", "prov-frio", (0, 5),
               local="enric-granados"),
        equipo("horno-mad", "Horno", "horno", "Cocina", "HornoMuestra", "HM-10", "prov-maq", local="madrid"),
    ]

    def tarea(id_, equipo_id, texto, frecuencia, dias):
        return {"id": id_, "equipo_id": equipo_id, "tarea": texto, "frecuencia": frecuencia,
                "proxima_fecha": dia(dias), "activa": True, "created_at": momento(-60)}

    tareas = [
        tarea("t1", "nevera-barra", "Limpiar el condensador", "trimestral", -12),
        tarea("t2", "nevera-cocina", "Revisar la goma de la puerta", "mensual", -3),
        tarea("t3", "horno", "Limpiar los quemadores", "mensual", 2),
        tarea("t4", "cafetera", "Cambiar el filtro de agua", "mensual", 5),
        tarea("t5", "lavavajillas", "Descalcificar", "quincenal", 6),
        tarea("t6", "congelador", "Descongelar y limpiar", "semestral", 20),
        tarea("t7", "plancha", "Revisar los termostatos", "trimestral", 45),
        tarea("t8", "nevera-eg", "Limpiar el condensador", "trimestral", 4),
        tarea("t9", "horno-mad", "Limpiar los quemadores", "mensual", 3),
    ]

    def apunte(id_, equipo_id, n, tipo, texto, coste=None, quien="Pablo Ejemplo"):
        return {"id": id_, "equipo_id": equipo_id, "servicio_id": None, "fecha": dia(n), "tipo": tipo,
                "descripcion": texto, "coste": coste, "realizado_por": quien, "tarea_id": None, "numero_factura": None,
                "created_at": momento(n)}

    bitacora = [
        apunte("b1", "nevera-cocina", -1, "averia", "No baja de 9 °C. Se pasa el género a la nevera de barra."),
        apunte("b2", "nevera-cocina", -40, "reparacion", "Cambio del ventilador", 180, "Frío Ejemplo S.L."),
        apunte("b3", "cafetera", -20, "mantenimiento", "Limpieza de grupos y cambio de juntas", 65, "Café Técnico Demo"),
        apunte("b4", "horno", -30, "limpieza", "Limpieza a fondo"),
        apunte("b5", "lavavajillas", -15, "reparacion", "Bomba de desagüe", 120, "Maquinaria Muestra"),
    ]
    servicios = [
        {"id": "s1", "local_id": sf, "nombre": "Control de plagas (DDD)", "categoria": "plagas", "proveedor_id": "prov-plagas",
         "frecuencia": "trimestral", "detalle": "Trimestral y a demanda", "ultima_revision": dia(-70),
         "proxima_revision": dia(20), "documentacion": None, "notas": None, "activo": True, "created_at": momento(-60)},
        {"id": "s2", "local_id": sf, "nombre": "Revisión de frío", "categoria": "frio", "proveedor_id": "prov-frio",
         "frecuencia": "semestral", "detalle": None, "ultima_revision": dia(-170), "proxima_revision": dia(10),
         "documentacion": None, "notas": None, "activo": True, "created_at": momento(-60)},
    ]
    limpieza = [
        {"id": "l1", "local_id": sf, "codigo": "P1", "nombre": "Desengrasante de ejemplo", "marca": "LimpiaDemo",
         "uso": "Superficies de cocina", "dosis": "50 ml por litro", "tiempo_contacto": "5 min", "registro": None,
         "ficha_tecnica": True, "ficha_seguridad": True, "peligros": None, "proveedor_id": None, "activo": True,
         "created_at": momento(-60)},
        {"id": "l2", "local_id": sf, "codigo": "P2", "nombre": "Desinfectante de ejemplo", "marca": "LimpiaDemo",
         "uso": "Tablas y utensilios", "dosis": "20 ml por litro", "tiempo_contacto": "10 min", "registro": None,
         "ficha_tecnica": True, "ficha_seguridad": False, "peligros": None, "proveedor_id": None, "activo": True,
         "created_at": momento(-60)},
    ]
    protocolos = [
        {"id": "apertura", "local_id": sf, "nombre": "Apertura", "tipo": "apertura", "momento": "Al abrir",
         "descripcion": "Comprobaciones antes de abrir", "version": "1", "activo": True, "created_at": momento(-60)},
        {"id": "cierre", "local_id": sf, "nombre": "Cierre", "tipo": "cierre", "momento": "Al cierre",
         "descripcion": "Limpieza y apagado", "version": "1", "activo": True, "created_at": momento(-60)},
    ]

    def paso(id_, protocolo, orden, texto):
        return {"id": id_, "protocolo_id": protocolo, "orden": orden, "seccion": None, "texto": texto, "producto": None,
                "dia_semana": None, "semana_mes": None, "activo": True}

    pasos = [
        paso("p1", "apertura", 1, "Comprobar la temperatura de las neveras"),
        paso("p2", "apertura", 2, "Encender la plancha y el horno"),
        paso("p3", "apertura", 3, "Revisar las caducidades de la barra"),
        paso("p4", "cierre", 1, "Limpiar y apagar la plancha"),
        paso("p5", "cierre", 2, "Poner el lavavajillas en limpieza"),
        paso("p6", "cierre", 3, "Sacar la basura y cerrar las neveras"),
    ]
    comunicados = [
        {"id": "c1", "local_id": None, "titulo": "Nueva carta de temporada", "texto": "Texto de ejemplo: el lunes cambia la carta.",
         "enlace": None, "creado_por": "Sara Ficticia", "activo": True, "created_at": momento(-2)},
    ]
    productos = [
        {"id": "demo-mayonesa", "name": "Salsa de ejemplo", "category": "Salsas", "storage": "refrigerado", "exp_hours": 72,
         "allergens": "Huevo", "vegan": False, "created_at": momento(-60)},
        {"id": "demo-hummus", "name": "Crema de garbanzos", "category": "Salsas", "storage": "refrigerado", "exp_hours": 96,
         "allergens": "Sésamo", "vegan": True, "created_at": momento(-60)},
    ]
    etiquetas = [
        {"id": 1, "fecha_impresion": momento(-1, 8), "producto": "Salsa de ejemplo", "preparacion": "—", "caducidad": "—",
         "responsable": "Pablo Ejemplo", "local_id": sf},
        {"id": 2, "fecha_impresion": momento(0, 8), "producto": "Crema de garbanzos", "preparacion": "—", "caducidad": "—",
         "responsable": "Nico Inventado", "local_id": sf},
    ]
    return {
        "locales": locales, "trabajadores": trabajadores, "proveedores": proveedores, "equipos": equipos,
        "tareas_mantenimiento": tareas, "bitacora_equipos": bitacora, "servicios": servicios,
        "productos_limpieza": limpieza, "protocolos": protocolos, "protocolo_pasos": pasos, "comunicados": comunicados,
        "productos": productos, "registro_appcc": etiquetas, "ajustes": [{"clave": "bloqueo_minutos", "valor": "30"}],
    }
