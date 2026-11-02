-- ════════════════════════════════════════════════════════════════════
-- LilOS · Rumbo: órdenes, objetivos y proyectos para cada persona (pilar 2, «la brújula»)
-- Ejecutar en Supabase → SQL Editor (después de acceso.sql). Se puede repetir sin romper nada.
--
-- Cada nota es un encargo en texto (markdown: viñetas, listas y casillas «- [ ]» / «- [x]») dirigido a una
-- persona (para), con alguien a cargo (puede ser la misma), fecha de vencimiento y propiedades libres.
-- Al terminarla queda «hecho»; quien la encargó la valora (1–5) y la archiva en la carpeta de la persona.
-- ════════════════════════════════════════════════════════════════════

create table if not exists rumbo (
    id                     uuid primary key default gen_random_uuid(),
    titulo                 text not null,
    tipo                   text not null default 'orden' check (tipo in ('orden', 'objetivo', 'proyecto')),
    contenido              text,                                         -- markdown con casillas «- [ ]»
    para_id                text references trabajadores(id) on delete set null,   -- a quién va dirigida
    a_cargo_id             text references trabajadores(id) on delete set null,   -- responsable (puede ser la misma)
    creado_por_id          text references trabajadores(id) on delete set null,
    local_id               text references locales(id),                   -- local de la persona (vacío = sin local)
    vence                  date,
    prioridad              text not null default 'normal' check (prioridad in ('normal', 'alta')),
    propiedades            jsonb not null default '{}'::jsonb,            -- propiedades extra libres (clave: valor)
    estado                 text not null default 'abierto' check (estado in ('abierto', 'hecho', 'archivado')),
    hecho_en               timestamptz,
    valoracion             smallint check (valoracion between 1 and 5),
    comentario_valoracion  text,
    archivado_en           timestamptz,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now()
);

-- Encargos a un grupo («Trabajadores · Enric Granados»): se crea una copia por persona (cada una lo hace y se
-- valora por separado) y todas comparten grupo_id. para_grupo dice a qué grupo iba (p. ej. 'staff').
-- Quien entra después en el local no recibe las copias ya creadas.
alter table rumbo add column if not exists grupo_id   uuid;
alter table rumbo add column if not exists para_grupo text;

create index if not exists rumbo_para     on rumbo (para_id);
create index if not exists rumbo_grupo    on rumbo (grupo_id);
create index if not exists rumbo_a_cargo  on rumbo (a_cargo_id);
create index if not exists rumbo_estado   on rumbo (estado);

-- Igual que el resto de tablas: RLS sin políticas; solo la app (clave de servicio) lee y escribe.
alter table rumbo enable row level security;
