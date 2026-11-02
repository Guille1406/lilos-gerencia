# AGENTS.md · LilOS Gerencia

> Este fichero lo leen los agentes de programación antes de tocar el código. `CLAUDE.md` y `GEMINI.md` remiten aquí.

## Qué es este proyecto

App para que los gerentes de los tres restaurantes de Lilo Brunch controlen el mantenimiento de sus equipos, con un asistente de IA que consulta los datos de la propia app.

## Cómo está hecho

- Python 3.11 o superior.
- Interfaz: Streamlit (ruta A). Archivo principal: `gerencia/app.py`.
- IA: API de Gemini en su plan gratuito, con el SDK `openai` y la dirección compatible de Google. Los modelos están en la constante `MODELOS_GEMINI` de `gerencia/core/ia.py`; si uno se satura, se prueba el siguiente.
- Datos: sin claves de Supabase, modo demostración con datos inventados en memoria (`gerencia/core/demo.py`). Con claves, Supabase (PostgreSQL), con las tablas de `supabase/`.
- Archivos: `gerencia/core/` (lógica), `gerencia/paginas/` (páginas), `gerencia/tests/` (pruebas), `gerencia/requirements.txt` (dependencias) y `README.md`.
- La especificación completa está en [especificacion.md](especificacion.md).

## Reglas

- Las claves van SIEMPRE en secretos: `.streamlit/secrets.toml` en local (fuera de git) y Settings → Secrets en Streamlit Cloud. Se leen con `db.config()`. Nunca en el código, en el README ni en el chat.
- Cada llamada a la API pasa por `_completar()` en `gerencia/core/ia.py`, que traduce los fallos a un `ErrorIA` con un mensaje claro para el usuario.
- Toda escritura en la base pasa por `gerencia/core/db.py`, que la corta en modo invitado. No la saltes.
- Textos de la interfaz en español, sencillos y directos, pensados para alguien sin conocimientos técnicos que trabaja en plena sala.
- Cambios pequeños: uno por petición. Al terminar, explica qué has cambiado y por qué.
- Si añades una librería, añádela también a `gerencia/requirements.txt` y dilo.
- No uses datos personales reales. Para probar, inventa ejemplos.

## Cómo comprobar que funciona

- `streamlit run gerencia/app.py` en local (con `.streamlit/secrets.toml`), o haz push y revisa la app en Streamlit Cloud.
- `pytest gerencia/tests`.
- Casos de prueba (entrada → lo que esperamos):
  1. «¿Qué tengo pendiente esta semana y por dónde empiezo?» → las tareas reales del local, lo más importante primero.
  2. Foto de la placa de un equipo → la ficha rellenada para revisarla antes de guardar.
  3. Una pregunta sobre algo que no está en la app ni en internet → dice que no lo sabe, sin inventar datos.

## Qué no hacer

- No borres ni reescribas el README sin preguntar.
- No cambies el modelo ni la arquitectura sin preguntar.
- No hagas push ni despliegues sin que lo haya revisado.
