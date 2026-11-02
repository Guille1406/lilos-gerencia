-- LilOS · Comunicados al equipo con confirmación de lectura («leído»).
-- Ejecutar en Supabase › SQL Editor (después de appcc.sql). Se puede ejecutar varias veces.

create table if not exists comunicados (
    id          uuid primary key default gen_random_uuid(),
    local_id    text references locales(id),          -- vacío = para todos los locales
    titulo      text not null,
    texto       text,
    enlace      text,                                  -- documento, vídeo o foto (opcional)
    creado_por  text,
    activo      boolean not null default true,
    created_at  timestamptz not null default now()
);

create table if not exists comunicado_lecturas (
    comunicado_id  uuid not null references comunicados(id) on delete cascade,
    trabajador     text not null,                      -- nombre, equivale a la firma del acuse de recibo
    leido_en       timestamptz not null default now(),
    primary key (comunicado_id, trabajador)
);

alter table comunicados          enable row level security;
alter table comunicado_lecturas  enable row level security;
