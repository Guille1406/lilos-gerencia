-- HORECA OS · Tablas de la base de datos en Supabase
-- Pegar entero en Supabase → SQL Editor → New query → Run.
-- Se puede ejecutar varias veces sin romper nada (if not exists).

create table if not exists productos (
    id          text primary key,
    name        text not null,
    category    text not null default 'General',
    storage     text not null default 'refrigerado',
    exp_hours   integer not null default 48,
    allergens   text not null default 'Ninguno',
    vegan       boolean not null default false,
    created_at  timestamptz not null default now()
);

-- Para proyectos creados antes de añadir la casilla de vegano
alter table productos add column if not exists vegan boolean not null default false;

create table if not exists trabajadores (
    id          text primary key,
    name        text not null,
    created_at  timestamptz not null default now()
);

-- Registro sanitario de cada etiqueta impresa. Solo se añade, nunca se modifica.
create table if not exists registro_appcc (
    id               bigint generated always as identity primary key,
    fecha_impresion  timestamptz not null default now(),
    producto         text,
    preparacion      text,   -- tal cual se imprimió en la etiqueta (dd/mm/aa hh:mm)
    caducidad        text,   -- tal cual se imprimió en la etiqueta (dd/mm/aa hh:mm)
    responsable      text
);

create index if not exists registro_appcc_fecha_idx on registro_appcc (fecha_impresion desc);

-- Seguridad: activamos RLS sin políticas. Así nadie puede leer ni escribir con la clave pública
-- (anon); solo el servidor de la app, que usa la clave service_role guardada en .env.
alter table productos      enable row level security;
alter table trabajadores   enable row level security;
alter table registro_appcc enable row level security;
