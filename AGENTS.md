# AGENTS.md · LilOS Gerencia

Lo que tiene que saber cualquier agente de IA antes de tocar este código. `CLAUDE.md` y `GEMINI.md` mandan aquí.

## De qué va esto

Una app para que los gerentes de mis tres restaurantes lleven el mantenimiento de sus máquinas, con un asistente de IA que mira los datos de la propia app.

## Cómo está montada

- Python 3.11 o más nuevo, con Streamlit (ruta A). Se arranca desde `gerencia/app.py`.
- La IA es Gemini, en su plan gratis, usando la librería `openai`. La lista de modelos está en `MODELOS_GEMINI`, en `gerencia/core/ia.py`. Si uno se satura, pasa al siguiente.
- Sin claves de Supabase, la app funciona con datos inventados (`gerencia/core/demo.py`). Con claves, usa Supabase, con las tablas de `supabase/`.
- La lógica está en `gerencia/core/`, las pantallas en `gerencia/paginas/`, las pruebas en `gerencia/tests/` y las dependencias en `gerencia/requirements.txt`.
- Lo que tiene que hacer la app está en [especificacion.md](especificacion.md).

## Reglas

- Las claves van SIEMPRE en los secretos: `.streamlit/secrets.toml` en local (no se sube) y Settings → Secrets en Streamlit Cloud. Se leen con `db.config()`. Nunca en el código, en el README ni en el chat.
- Todas las llamadas a la IA pasan por `_completar()`, en `gerencia/core/ia.py`. Si algo falla, el usuario tiene que ver un mensaje que se entienda.
- Todo lo que se guarda pasa por `gerencia/core/db.py`, que lo bloquea para los invitados. No te lo saltes.
- Textos en español, sencillos y directos. Quien lo usa está trabajando en sala y no sabe de tecnología.
- Cambios pequeños, de uno en uno. Al terminar, cuéntame qué has cambiado y por qué.
- Si añades una librería, ponla también en `gerencia/requirements.txt` y dímelo.
- Nada de datos reales de personas. Para probar, invéntatelos.

## Cómo comprobar que funciona

- En local: `streamlit run gerencia/app.py`. Sin claves arranca con los datos inventados. O sube los cambios y mira la app en Streamlit Cloud.
- Las pruebas: `pytest gerencia/tests`.
- Tres preguntas para probar a mano:
  1. «¿Qué tengo pendiente esta semana y por dónde empiezo?» → las tareas de verdad, primero lo más urgente.
  2. La foto de la placa de una máquina → la ficha rellenada, para revisarla antes de guardar.
  3. Algo que no está en la app ni en internet → dice que no lo sabe y no se inventa nada.

## Lo que no debes hacer

- No borres ni reescribas el README sin preguntar.
- No cambies los modelos ni cómo está montada la app sin preguntar.
- No subas ni publiques nada sin que yo lo haya visto.
