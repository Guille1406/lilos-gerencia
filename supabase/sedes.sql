-- ════════════════════════════════════════════════════════════════════
-- LilOS · Sedes: una persona puede pertenecer a más de un local
-- Ejecutar en Supabase → SQL Editor. Se puede repetir sin romper nada.
--
-- `locales` es la lista de sedes de la persona (vacía o nula = todas, como antes el local_id nulo).
-- `local_id` se queda como «sede principal»: la que se elige por defecto al entrar.
-- ════════════════════════════════════════════════════════════════════

alter table trabajadores add column if not exists locales text[];

-- Quien ya tenía un local pasa a tener esa sede (solo si aún no se ha rellenado `locales`)
update trabajadores set locales = array[local_id] where local_id is not null and locales is null;
