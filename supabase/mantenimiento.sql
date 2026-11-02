-- LilOS · Módulo de mantenimiento de equipos (APPCC: mantenimiento de instalaciones y equipos)
-- Pegar entero en Supabase → SQL Editor → New query → Run. Se puede ejecutar varias veces sin romper nada.

-- ── Locales ──
create table if not exists locales (
    id      text primary key,
    nombre  text not null
);
insert into locales (id, nombre) values
    ('sagrada-familia', 'Lilo Sagrada Familia'),
    ('enric-granados',  'Lilo Enric Granados'),
    ('madrid',          'Lilo Madrid')
on conflict (id) do nothing;

-- ── Rol y local de cada trabajador ──
-- Todos pueden registrar mantenimientos; las alertas son responsabilidad del gerente del local
-- y, si se retrasan, de los directivos.
alter table trabajadores add column if not exists rol text not null default 'staff'
    check (rol in ('staff', 'gerente', 'directivo'));
alter table trabajadores add column if not exists local_id text references locales(id);

-- ── Equipos (ficha técnica) ──
create table if not exists equipos (
    id                uuid primary key default gen_random_uuid(),
    local_id          text not null references locales(id),
    nombre            text not null,               -- "Nevera 2 barra"
    tipo              text not null,               -- nevera, congelador, cámara, horno, freidora, mesón...
    zona              text,                        -- cocina, barra, almacén...
    marca             text,
    modelo            text,
    numero_serie      text,
    fecha_compra      date,
    garantia_hasta    date,
    servicio_tecnico  text,                        -- empresa
    contacto_tecnico  text,                        -- teléfono / email
    temp_min          numeric(5,1),                -- rango correcto (solo equipos de frío/calor)
    temp_max          numeric(5,1),
    estado            text not null default 'operativo'
                      check (estado in ('operativo', 'averiado', 'en_reparacion', 'baja')),
    notas             text,
    foto_url          text,
    created_at        timestamptz not null default now()
);
create index if not exists equipos_local_idx on equipos (local_id);

-- ── Plan de mantenimiento: tareas que se repiten ──
create table if not exists tareas_mantenimiento (
    id             uuid primary key default gen_random_uuid(),
    equipo_id      uuid not null references equipos(id) on delete cascade,
    tarea          text not null,                  -- "Limpiar condensador"
    frecuencia     text not null
                   check (frecuencia in ('semanal', 'quincenal', 'mensual', 'trimestral', 'semestral', 'anual')),
    proxima_fecha  date not null,
    activa         boolean not null default true,
    created_at     timestamptz not null default now()
);
create index if not exists tareas_proxima_idx on tareas_mantenimiento (proxima_fecha) where activa;

-- ── Bitácora: todo lo que se le hace a un equipo ──
create table if not exists bitacora_equipos (
    id             uuid primary key default gen_random_uuid(),
    equipo_id      uuid not null references equipos(id) on delete cascade,
    fecha          date not null default current_date,
    tipo           text not null
                   check (tipo in ('mantenimiento', 'inspeccion', 'limpieza', 'reparacion', 'averia', 'cambio_pieza', 'otro')),
    descripcion    text not null,
    coste          numeric(10,2),
    realizado_por  text,                           -- trabajador o empresa externa
    tarea_id       uuid references tareas_mantenimiento(id) on delete set null,  -- si cumple una tarea del plan
    created_at     timestamptz not null default now()
);
create index if not exists bitacora_equipo_idx on bitacora_equipos (equipo_id, fecha desc);

-- Seguridad: igual que el resto, solo el servidor (clave service_role) puede leer y escribir.
alter table locales               enable row level security;
alter table equipos               enable row level security;
alter table tareas_mantenimiento  enable row level security;
alter table bitacora_equipos      enable row level security;
