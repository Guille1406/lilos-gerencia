-- ════════════════════════════════════════════════════════════════════
-- LilOS · Historial de versiones de los procedimientos oficiales (POE del APPCC)
-- Ejecutar una vez en Supabase → SQL Editor. Se puede repetir sin romper nada.
--
-- Para que un procedimiento oficial (temperaturas, aseos…) tenga validez legal hay que poder demostrar qué
-- decía en cada momento y por qué cambió. Cada vez que se modifica el procedimiento o sus pasos, la app guarda
-- una versión nueva con el motivo del cambio, quién lo hizo y una foto («snapshot») del contenido completo.
-- Los registros firmados guardan además la versión que estaba vigente cuando se firmaron.
-- ════════════════════════════════════════════════════════════════════

create table if not exists procedimiento_versiones (
    id            uuid primary key default gen_random_uuid(),
    protocolo_id  uuid not null references protocolos(id) on delete cascade,
    version       int  not null,                 -- 1, 2, 3… por procedimiento
    motivo        text not null,                 -- por qué se cambia (obligatorio en los POE)
    cambiado_por  text,                          -- nombre de quien lo cambia
    snapshot      jsonb not null,                -- datos del procedimiento + lista ordenada de pasos activos
    resumen       text,                          -- diferencias con la versión anterior, en lenguaje humano
    created_at    timestamptz not null default now(),
    unique (protocolo_id, version)
);
create index if not exists procedimiento_versiones_protocolo on procedimiento_versiones (protocolo_id, version desc);

-- Seguridad: igual que el resto de tablas, solo el servidor (clave service_role) puede leer y escribir
alter table procedimiento_versiones enable row level security;

-- Versión del procedimiento que estaba en vigor cuando se firmó cada registro
alter table protocolo_registros add column if not exists version int;
