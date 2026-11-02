-- ════════════════════════════════════════════════════════════════════
-- LilOS · Registro de errores y avisos de las dos apps (gerencia y etiquetas)
-- Ejecutar una vez en Supabase → SQL Editor. Se puede repetir sin romper nada.
--
-- Aquí se acumula todo lo que falla o avisa en la app (errores no controlados, fallos de la IA, de Notion,
-- del email, de la impresora DYMO…). Solo lo ve el admin, en «🧾 Registro de errores». Cada apunte se puede
-- marcar como resuelto. Las apps escriben con la clave de servicio, por eso basta con activar RLS.
-- ════════════════════════════════════════════════════════════════════

create table if not exists registro_errores (
    id            bigint generated always as identity primary key,
    created_at    timestamptz not null default now(),
    app           text not null default 'gerencia' check (app in ('gerencia', 'etiquetas')),
    nivel         text not null default 'error' check (nivel in ('error', 'aviso', 'info')),
    origen        text,                          -- página, módulo o función donde ocurrió
    mensaje       text not null,
    detalle       text,                          -- traceback o datos extra (JSON)
    persona       text,                          -- quién estaba usando la app
    local_id      text,
    resuelto      boolean not null default false,
    resuelto_por  text,
    resuelto_en   timestamptz
);

create index if not exists registro_errores_fecha      on registro_errores (created_at desc);
create index if not exists registro_errores_pendientes on registro_errores (created_at desc) where not resuelto;

alter table registro_errores enable row level security;
