-- ════════════════════════════════════════════════════════════════════
-- LilOS · Revisión paso a paso (v0.16)
-- Ejecutar una vez en Supabase → SQL Editor. Se puede repetir sin romper nada.
--
-- A una persona concreta se le quita el «✅ Todo bien» de un toque: tiene que marcar cada tarea del protocolo
-- (p. ej. tras una amonestación por no limpiar bien los suelos). Puede ser para un protocolo o para todos, con
-- fecha de fin o indefinido, y se quita cuando se quiera. El motivo solo lo ve el admin.
-- ════════════════════════════════════════════════════════════════════

create table if not exists paso_a_paso (
    id             uuid primary key default gen_random_uuid(),
    trabajador_id  text not null references trabajadores(id) on delete cascade,
    protocolo_id   uuid references protocolos(id) on delete cascade,   -- vacío = todos los protocolos
    hasta          date,                                               -- vacío = hasta que se quite
    motivo         text,
    creado_por     text,
    activo         boolean not null default true,
    created_at     timestamptz not null default now()
);
create index if not exists paso_a_paso_trabajador on paso_a_paso (trabajador_id) where activo;

alter table paso_a_paso enable row level security;
