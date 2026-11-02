-- ════════════════════════════════════════════════════════════════════
-- LilOS · Impresión por cola: dispositivos principales y cola de etiquetas
-- Ejecutar una vez en Supabase → SQL Editor. Se puede repetir sin romper nada.
-- Necesita antes supabase/schema.sql y supabase/mantenimiento.sql (tabla locales).
--
-- Cada ordenador que ejecuta la etiquetadora (Etiquetas.bat) se registra solo en «dispositivos» y manda un
-- latido cada 30 s. En gerencia → 🖨️ Dispositivos el admin le asigna el local y lo marca como PRINCIPAL:
-- los principales son los que tienen la DYMO conectada e imprimen la cola de su local.
-- Desde una tablet, un móvil o la app de gerencia se añade una fila a «cola_impresion»; el principal del local
-- la toma, la imprime y la marca como impresa (o error). Cada etiqueta impresa queda en registro_appcc con su
-- local. Las apps escriben con la clave de servicio, por eso basta con activar RLS (sin políticas).
-- ════════════════════════════════════════════════════════════════════

-- ── Dispositivos (un ordenador = una fila; el id lo guarda cada PC en dispositivo.local.json) ──
create table if not exists dispositivos (
    id              uuid primary key default gen_random_uuid(),
    nombre          text not null,                               -- p. ej. «PC cocina Enric Granados»
    local_id        text references locales(id) on delete set null,
    principal       boolean not null default false,              -- imprime la cola de su local
    impresora       text,                                         -- DYMO que detecta (o el motivo si no hay)
    version         text,                                         -- versión de LilOS que ejecuta
    ultimo_latido   timestamptz,                                  -- en línea si es de hace menos de 2 min
    activo          boolean not null default true,
    created_at      timestamptz not null default now()
);
create index if not exists dispositivos_local on dispositivos (local_id) where principal;

-- ── Cola de impresión ──
create table if not exists cola_impresion (
    id               uuid primary key default gen_random_uuid(),
    local_id         text not null references locales(id),
    dispositivo_id   uuid references dispositivos(id) on delete set null,   -- null = cualquier principal del local
    solicitado_por   text,                                                   -- quién la pidió
    origen           text not null default 'etiquetadora'
                     check (origen in ('tablet', 'movil', 'gerencia', 'etiquetadora')),
    -- Todo lo necesario para la etiqueta: producto, producto_id, categoria, conservacion, alergenos,
    -- preparacion y caducidad (ISO con zona), horas_caducidad, responsable, lote, copias
    datos            jsonb not null,
    estado           text not null default 'pendiente'
                     check (estado in ('pendiente', 'imprimiendo', 'impresa', 'error', 'cancelada')),
    intentos         integer not null default 0,
    copias_impresas  integer not null default 0,                -- si falla a mitad, se sigue por la siguiente
    error            text,
    created_at       timestamptz not null default now(),
    tomada_en        timestamptz,
    impresa_en       timestamptz
);
create index if not exists cola_impresion_local_estado on cola_impresion (local_id, estado, created_at);
-- Por si la tabla se creó con una versión anterior de este archivo
alter table cola_impresion add column if not exists copias_impresas integer not null default 0;

-- ── Cada etiqueta sabe en qué local se imprimió ──
alter table registro_appcc add column if not exists local_id text references locales(id) on delete set null;
create index if not exists registro_appcc_local on registro_appcc (local_id, fecha_impresion desc);

-- ── Seguridad: solo las apps (clave de servicio) leen y escriben ──
alter table dispositivos   enable row level security;
alter table cola_impresion enable row level security;

-- ── Realtime: el principal se entera al instante de cada trabajo nuevo (si no, mira la cola cada 3 s) ──
do $$
begin
    if exists (select 1 from pg_publication where pubname = 'supabase_realtime')
       and not exists (select 1 from pg_publication_tables
                       where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'cola_impresion') then
        alter publication supabase_realtime add table cola_impresion;
    end if;
end $$;
