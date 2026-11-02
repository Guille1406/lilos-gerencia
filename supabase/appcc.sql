-- LilOS · APPCC: proveedores, revisiones de equipos, servicios de mantenimiento, productos de limpieza y protocolos.
-- Ejecutar en Supabase › SQL Editor DESPUÉS de schema.sql y mantenimiento.sql. Se puede ejecutar varias veces.

-- ── Proveedores y empresas técnicas (comunes a todos los locales) ──
create table if not exists proveedores (
    id             uuid primary key default gen_random_uuid(),
    nombre         text not null,                -- "Servicio técnico de frío"
    servicio       text,                         -- qué hace: maquinaria general, frío, plagas, extintores…
    contacto       text,                         -- persona de contacto
    telefono       text,
    email          text,
    documentacion  text,                         -- CIF, nº ROESB, contrato…
    notas          text,
    created_at     timestamptz not null default now()
);

-- ── Frecuencias: se añaden cuatrimestral (filtros BWT) y quinquenal (retimbrado de extintores) ──
alter table tareas_mantenimiento drop constraint if exists tareas_mantenimiento_frecuencia_check;
alter table tareas_mantenimiento add constraint tareas_mantenimiento_frecuencia_check
    check (frecuencia in ('semanal', 'quincenal', 'mensual', 'trimestral', 'cuatrimestral', 'semestral', 'anual',
                          'quinquenal'));

-- ── Revisión periódica de cada equipo (última y próxima) y su empresa técnica ──
alter table equipos add column if not exists capacidad           text;   -- "500 L", "20 L · 1,1 kW"
alter table equipos add column if not exists proveedor_id        uuid references proveedores(id) on delete set null;
alter table equipos add column if not exists revision_frecuencia text;   -- semanal…quinquenal, o segun_fabricante,
                                                                          -- segun_contrato, a_demanda
alter table equipos add column if not exists revision_detalle    text;   -- "Anual (mayo) + revisión trimestral"
alter table equipos add column if not exists ultima_revision     date;
alter table equipos add column if not exists proxima_revision    date;

-- ── Servicios de mantenimiento del local: frío, plagas (DDD), extintores, climatización, electricidad… ──
create table if not exists servicios (
    id                uuid primary key default gen_random_uuid(),
    local_id          text not null references locales(id),
    nombre            text not null,             -- "Control de plagas (DDD)"
    categoria         text not null default 'otro'
                      check (categoria in ('frio', 'maquinaria', 'cafetera', 'agua', 'plagas', 'extintores',
                                           'climatizacion', 'electricidad', 'fontaneria', 'campana', 'otro')),
    proveedor_id      uuid references proveedores(id) on delete set null,
    frecuencia        text,                      -- como revision_frecuencia de equipos
    detalle           text,                      -- "Trimestral + a demanda"
    ultima_revision   date,
    proxima_revision  date,
    documentacion     text,                      -- contrato, certificados, nº ROESB…
    notas             text,
    activo            boolean not null default true,
    created_at        timestamptz not null default now()
);

-- La bitácora (registro de intervenciones) sirve para equipos y para servicios
alter table bitacora_equipos alter column equipo_id drop not null;
alter table bitacora_equipos add column if not exists servicio_id   uuid references servicios(id) on delete cascade;
alter table bitacora_equipos add column if not exists numero_factura text;   -- nº de factura o parte del técnico
alter table bitacora_equipos drop constraint if exists bitacora_equipo_o_servicio;
alter table bitacora_equipos add constraint bitacora_equipo_o_servicio
    check (equipo_id is not null or servicio_id is not null);

-- ── Productos de limpieza y desinfección (Anexo 1) ──
create table if not exists productos_limpieza (
    id               uuid primary key default gen_random_uuid(),
    local_id         text not null references locales(id),
    codigo           text not null,              -- P1, P2, P2-B…
    nombre           text not null,
    marca            text,
    uso              text,                        -- uso principal
    dosis            text,                        -- dosis / dilución
    tiempo_contacto  text,
    registro         text,                        -- nº de registro (HA, ES/, EU-), UFI o lote
    ficha_tecnica    boolean not null default false,
    ficha_seguridad  boolean not null default false,
    peligros         text,                        -- frases H, EPIs…
    proveedor_id     uuid references proveedores(id) on delete set null,
    activo           boolean not null default true,
    created_at       timestamptz not null default now(),
    unique (local_id, codigo)
);

-- ── Protocolos: apertura, cierre, limpieza, averías… con sus pasos y los registros firmados ──
create table if not exists protocolos (
    id           uuid primary key default gen_random_uuid(),
    local_id     text not null references locales(id),
    nombre       text not null,                  -- "Cierre"
    tipo         text not null default 'otro'
                 check (tipo in ('apertura', 'cierre', 'limpieza', 'averia', 'maquinaria', 'otro')),
    momento      text,                           -- "Al cierre", "Mañana y tarde", "Ante una avería"
    descripcion  text,
    version      text,
    activo       boolean not null default true,
    created_at   timestamptz not null default now()
);

create table if not exists protocolo_pasos (
    id            uuid primary key default gen_random_uuid(),
    protocolo_id  uuid not null references protocolos(id) on delete cascade,
    orden         integer not null,
    seccion       text,                          -- "Cocina (material verde)"
    texto         text not null,
    producto      text,                          -- códigos de producto: "P1 + P3"
    dia_semana    integer check (dia_semana between 1 and 7),   -- 1 = lunes; vacío = todos los días
    semana_mes    integer check (semana_mes between 1 and 5),   -- 1ª…5ª semana; vacío = todas
    activo        boolean not null default true
);

create table if not exists protocolo_registros (
    id              uuid primary key default gen_random_uuid(),
    protocolo_id    uuid not null references protocolos(id) on delete cascade,
    fecha           date not null default current_date,
    turno           text,
    realizado_por   text,                        -- equivale a la firma
    verificado_por  text,                        -- encargado/a
    completado      boolean not null default false,
    incidencias     text,
    created_at      timestamptz not null default now()
);

create table if not exists protocolo_registro_pasos (
    registro_id  uuid not null references protocolo_registros(id) on delete cascade,
    paso_id      uuid not null references protocolo_pasos(id) on delete cascade,
    hecho        boolean not null default false,
    primary key (registro_id, paso_id)
);

-- Seguridad: igual que el resto de tablas, solo el servidor (clave service_role) puede leer y escribir
alter table proveedores               enable row level security;
alter table servicios                 enable row level security;
alter table productos_limpieza        enable row level security;
alter table protocolos                enable row level security;
alter table protocolo_pasos           enable row level security;
alter table protocolo_registros       enable row level security;
alter table protocolo_registro_pasos  enable row level security;
