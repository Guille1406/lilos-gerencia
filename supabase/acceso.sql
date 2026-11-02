-- ════════════════════════════════════════════════════════════════════
-- LilOS · Acceso con PIN y perfiles (v0.14)
-- Ejecutar una vez en Supabase → SQL Editor. Se puede repetir sin romper nada.
--
-- Cada persona entra con su PIN personal (como en el TPV de Square). Dirección y admin entran con
-- usuario + PIN/contraseña. Jerarquía: admin > directivo (dirección) > gerente > staff (trabajador).
-- El PIN nunca se guarda tal cual: solo su huella (pbkdf2 con sal), calculada en la app.
-- ════════════════════════════════════════════════════════════════════

-- Roles: se añade «admin» (la cuenta maestra) a los que ya había
alter table trabajadores drop constraint if exists trabajadores_rol_check;
alter table trabajadores add constraint trabajadores_rol_check
    check (rol in ('staff', 'gerente', 'directivo', 'admin'));

alter table trabajadores add column if not exists pin_hash text;          -- huella del PIN (o de la contraseña del admin)
alter table trabajadores add column if not exists usuario  text unique;   -- solo dirección y admin
alter table trabajadores add column if not exists activo   boolean not null default true;

-- Registro de entradas (correctas y fallidas): sirve para frenar a quien pruebe PINs al azar
-- y para que el admin vea quién entra y cuándo.
create table if not exists accesos (
    id             bigint generated always as identity primary key,
    trabajador_id  text references trabajadores(id) on delete set null,
    nombre         text,
    exito          boolean not null,
    motivo         text,                           -- «pin», «usuario», «pin incorrecto»…
    created_at     timestamptz not null default now()
);
create index if not exists accesos_fecha on accesos (created_at desc);

-- Ajustes generales de la app (p. ej. minutos sin uso antes de pedir el PIN de nuevo)
create table if not exists ajustes (
    clave  text primary key,
    valor  text not null
);
insert into ajustes (clave, valor) values ('bloqueo_minutos', '5') on conflict (clave) do nothing;

alter table accesos enable row level security;
alter table ajustes enable row level security;
