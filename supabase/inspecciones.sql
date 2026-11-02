-- ════════════════════════════════════════════════════════════════════
-- LilOS · Inspecciones (auditorías tipo SafetyCulture / iAuditor)
-- Ejecutar una vez en Supabase → SQL Editor (después de appcc.sql). Se puede repetir sin romper nada.
--
-- Una plantilla es una lista de preguntas agrupadas por secciones. Hay plantillas oficiales que trae la app
-- (sanidad/APPCC, PRL, emergencias, calidad), plantillas propias y plantillas hechas a partir de un protocolo
-- (cada paso de la rutina se convierte en «¿Correcto?»). Cada inspección guarda sus respuestas, la nota
-- (porcentaje) y cuántas no conformidades críticas tuvo.
-- ════════════════════════════════════════════════════════════════════

create table if not exists inspeccion_plantillas (
    id            uuid primary key default gen_random_uuid(),
    nombre        text not null,
    tipo          text not null default 'personalizada',     -- personalizada, sanidad, prl, emergencias, calidad, rutina…
    descripcion   text,
    local_id      text references locales(id),               -- vacío = para todos los locales
    protocolo_id  uuid references protocolos(id) on delete set null,   -- solo las que salen de una rutina
    predefinida   boolean not null default false,            -- las oficiales: no se editan, se duplican
    activo        boolean not null default true,
    creado_por    text,
    created_at    timestamptz not null default now()
);

create table if not exists inspeccion_preguntas (
    id           uuid primary key default gen_random_uuid(),
    plantilla_id uuid not null references inspeccion_plantillas(id) on delete cascade,
    orden        integer not null default 1,
    seccion      text,                                       -- "Control de plagas"
    tipo         text not null default 'si_no'
                 check (tipo in ('texto', 'casilla', 'si_no', 'respuesta')),
                 -- texto = instrucción o encabezado (sin respuesta) · casilla = marcar · si_no = Sí/No/N/A
                 -- respuesta = texto corto (p. ej. «Tiempo de espera hasta la comanda (min)»)
    enunciado    text not null,
    ayuda        text,                                       -- qué mirar, normativa de referencia…
    obligatoria  boolean not null default true,
    critica      boolean not null default false,             -- un «No» aquí es una no conformidad crítica
    puntua       boolean not null default true               -- cuenta para el porcentaje
);
create index if not exists inspeccion_preguntas_plantilla on inspeccion_preguntas (plantilla_id, orden);

create table if not exists inspecciones (
    id            uuid primary key default gen_random_uuid(),
    plantilla_id  uuid references inspeccion_plantillas(id) on delete set null,
    plantilla     text,                      -- nombre de la plantilla en ese momento (por si luego cambia)
    local_id      text references locales(id),
    inspector     text,
    fecha         date not null default current_date,
    estado        text not null default 'cerrada' check (estado in ('borrador', 'cerrada')),
    puntos        numeric,
    maximo        numeric,
    porcentaje    numeric,
    criticas      integer not null default 0,
    notas         text,
    created_at    timestamptz not null default now(),
    cerrada_en    timestamptz
);
create index if not exists inspecciones_local_fecha on inspecciones (local_id, fecha desc);

create table if not exists inspeccion_respuestas (
    id                 uuid primary key default gen_random_uuid(),
    inspeccion_id      uuid not null references inspecciones(id) on delete cascade,
    pregunta_id        uuid references inspeccion_preguntas(id) on delete set null,
    valor              text,                 -- 'si', 'no', 'na', 'true', 'false' o el texto escrito
    comentario         text,
    accion_correctiva  text,
    -- copia de la pregunta tal como estaba: el historial no cambia aunque luego se edite la plantilla
    seccion            text,
    tipo               text,
    enunciado          text,
    critica            boolean not null default false
);
create index if not exists inspeccion_respuestas_inspeccion on inspeccion_respuestas (inspeccion_id);

-- Igual que el resto de tablas: RLS sin políticas; solo la app (clave de servicio) lee y escribe.
alter table inspeccion_plantillas  enable row level security;
alter table inspeccion_preguntas   enable row level security;
alter table inspecciones           enable row level security;
alter table inspeccion_respuestas  enable row level security;
