-- ════════════════════════════════════════════════════════════════════
-- LilOS · Procedimientos (POE) y rutinas, con frecuencia como en iAuditor
-- Ejecutar una vez en Supabase → SQL Editor. Se puede repetir sin romper nada.
--
-- Los protocolos se separan en dos categorías:
--   · appcc  → Procedimientos Operativos Estandarizados (POE) del APPCC: limpieza, aseos, temperaturas…
--   · rutina → lo del día a día del local: apertura, cierre…
-- Y el «cuándo» deja de ser texto libre: frecuencia (diaria, semanal, mensual, trimestral, anual), el momento
-- del día (apertura, durante el turno, cierre) y una hora límite opcional (si no está registrado a esa hora,
-- sale en «Necesita atención» de Hoy). La columna antigua `momento` se conserva, pero ya no se edita.
-- Los pasos siguen pudiendo tener su propio día de la semana o semana del mes (protocolo_pasos).
-- Además: «veces al día» (p. ej. los aseos dos veces al día) y «día del mes» (p. ej. el día 15 de cada mes).
-- Las averías no son rutinas: se avisan desde Hoy («Avisar de una avería») y el procedimiento de avería se sigue entonces.
-- ════════════════════════════════════════════════════════════════════

-- Todo va dentro de un único bloque «do»: no usa tablas temporales (Supabase avisaría de «tabla sin RLS»).
-- `primera` es verdadero solo si todavía no existía la columna `categoria`, es decir, la primera vez que se ejecuta:
-- los valores iniciales (al final) solo se ponen entonces, y si se vuelve a ejecutar no se pisa lo que el
-- propietario haya cambiado en la app.
do $$
declare
    primera boolean := not exists (select 1 from information_schema.columns
                                    where table_name = 'protocolos' and column_name = 'categoria');
begin
    alter table protocolos add column if not exists categoria text not null default 'rutina';
    alter table protocolos add column if not exists frecuencia text not null default 'diaria';
    alter table protocolos add column if not exists dias_semana int[];      -- semanal: 1 = lunes … 7 = domingo
    alter table protocolos add column if not exists semana_mes int;         -- mensual/trimestral/anual: 1–4, 5 = la última
    alter table protocolos add column if not exists dia_mes int;            -- mensual/trimestral/anual: día del mes (1–31; si el mes es más corto, el último día)
    alter table protocolos add column if not exists mes_periodo int;        -- trimestral: mes del trimestre (1–3); anual: mes (1–12)
    alter table protocolos add column if not exists veces_dia int not null default 1;   -- cuántas veces al día (1–6): aseos 2, etc.
    alter table protocolos add column if not exists franja text;            -- apertura, durante el turno o cierre
    alter table protocolos add column if not exists hora_limite time;       -- opcional: hora a la que debe estar hecho

    alter table protocolos drop constraint if exists protocolos_categoria_check;
    alter table protocolos add constraint protocolos_categoria_check check (categoria in ('appcc', 'rutina'));
    alter table protocolos drop constraint if exists protocolos_frecuencia_check;
    alter table protocolos add constraint protocolos_frecuencia_check
        check (frecuencia in ('diaria', 'semanal', 'mensual', 'trimestral', 'anual'));
    alter table protocolos drop constraint if exists protocolos_franja_check;
    alter table protocolos add constraint protocolos_franja_check check (franja in ('apertura', 'turno', 'cierre'));
    alter table protocolos drop constraint if exists protocolos_semana_mes_check;
    alter table protocolos add constraint protocolos_semana_mes_check check (semana_mes between 1 and 5);
    alter table protocolos drop constraint if exists protocolos_dia_mes_check;
    alter table protocolos add constraint protocolos_dia_mes_check check (dia_mes between 1 and 31);
    alter table protocolos drop constraint if exists protocolos_mes_periodo_check;
    alter table protocolos add constraint protocolos_mes_periodo_check check (mes_periodo between 1 and 12);
    alter table protocolos drop constraint if exists protocolos_veces_dia_check;
    alter table protocolos add constraint protocolos_veces_dia_check check (veces_dia between 1 and 6);

    -- ── Valores iniciales (solo la primera vez; el propietario los ajusta luego en la app) ──
    if primera then
        -- Apertura y cierre: rutinas diarias, en su momento del día
        update protocolos set categoria = 'rutina', frecuencia = 'diaria', franja = 'apertura'
         where tipo = 'apertura' or nombre ilike '%apertura%';
        update protocolos set categoria = 'rutina', frecuencia = 'diaria', franja = 'cierre'
         where tipo = 'cierre' or nombre ilike '%cierre%';

        -- Aseos/baños, planes de limpieza, temperaturas y averías: procedimientos oficiales del APPCC.
        -- Siguen siendo diarios a nivel de procedimiento: la «Limpieza semanal y mensual» ya reparte sus pasos por
        -- semana del mes (y tiene pasos de todos los días), así que sale exactamente los mismos días que antes.
        update protocolos set categoria = 'appcc'
         where tipo not in ('apertura', 'cierre')
           and (tipo in ('limpieza', 'averia') or nombre ilike '%aseo%' or nombre ilike '%baño%' or nombre ilike '%bano%'
                or nombre ilike '%limpieza%' or nombre ilike '%temperatura%' or nombre ilike '%averia%'
                or nombre ilike '%avería%');

        -- La limpieza de la plancha (ahora dentro del Cierre, desactivada) se hacía al cierre
        update protocolos set franja = 'cierre' where nombre ilike '%plancha%';
    end if;
end $$;

-- Para comprobarlo:
-- select nombre, tipo, categoria, frecuencia, veces_dia, dia_mes, franja, hora_limite from protocolos order by local_id, nombre;
