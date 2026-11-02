# LilOS Gerencia

**Enlace a la app:** https://lilos-gerencia.streamlit.app (versión de demostración, con datos inventados; los PIN de prueba salen al entrar)
**Autor/a:** Guillermo Jesús Pinto Henriques

## Pitch

Los gerentes de los tres restaurantes de Lilo Brunch tienen que mantener neveras, hornos y demás equipos mientras trabajan en plena sala, y las revisiones se les pueden pasar de fecha. LilOS Gerencia les enseña qué toca esta semana, guarda la ficha y la bitácora de cada equipo, y escala a dirección lo que lleva más de 7 días atrasado. La IA contesta con los datos de la propia app, lee la foto de la placa de un equipo y orienta ante una avería, sin que el gerente tenga que buscar en documentos. Mis trabajadores la han probado en el día a día de los locales y eso ha cambiado el producto: por ejemplo, el teclado del iPhone no tenía «-» para apuntar temperaturas negativas, y las alertas pasaron a verlas todos. Después llevaría lo aprendido a una web propia para las tablets de cada local, que ya está en marcha, con la pantalla Hoy como lista de comprobación de un avión.

## El problema

Los gerentes son los responsables del mantenimiento de su local, pero casi nunca están en una oficina. Hoy dependen de los documentos del plan APPCC, de las llamadas a los técnicos y de su memoria. Una revisión olvidada puede acabar en una avería en pleno servicio o en un problema de seguridad alimentaria, y el historial y el gasto de cada equipo están dispersos.

## Qué hace la app

1. El gerente entra con su PIN personal y ve lo que tiene que hacer hoy.
2. En **Alertas** consulta las tareas de esta semana, este mes o este trimestre, y las atrasadas.
3. En **Equipos y mobiliario** abre la ficha técnica, la garantía, el plan, el historial y el gasto de cada equipo. Puede rellenar la ficha con una foto de la placa o pedir un plan de mantenimiento a la IA.
4. En **Bitácora** cualquier trabajador apunta mantenimientos, inspecciones, averías o reparaciones. Al cumplir una tarea se recalcula su próxima fecha, y una avería marca el equipo como averiado.
5. En **Asistente** pregunta lo que necesite, por ejemplo: «¿Qué equipos han dado más problemas y cuánto nos han costado?».

Para enseñarla sin riesgo hay un **perfil invitado**: puede recorrer la app, pero no puede guardar, borrar ni enviar nada.

## La pieza de IA

- **Qué usa:** la API de Gemini en su plan gratuito (`gemini-flash-lite-latest`, con `gemini-3.5-flash-lite` y `gemini-flash-latest` de reserva), con herramientas que consultan la base de datos. Si hace falta buscar en internet, usa Tavily o la Wikipedia.
- **Por qué esa opción:** es gratis, entiende fotos y puede consultar datos que cambian cada día sin mantener un índice aparte. Al usar la API compatible con OpenAI, se puede cambiar de proveedor desde la configuración.
- **Qué pasa si falla:** si un modelo se satura o se queda sin cuota, se prueba el siguiente. Si fallan todos, la app avisa con un mensaje claro («Se ha agotado la cuota gratuita de la IA por ahora. Prueba dentro de un rato.») y el resto de la app sigue funcionando.

## Cómo la he construido

- **Herramientas:** Claude Code para programar y Claude Design para el diseño.
- **Fichero de contexto del agente:** [AGENTS.md](AGENTS.md), con [CLAUDE.md](CLAUDE.md) y [GEMINI.md](GEMINI.md) remitiendo a él. La especificación está en [especificacion.md](especificacion.md).
- **Prompts clave** (copiados de mis conversaciones; `[…]` marca lo que he recortado):
  1. «tengo que hacer una parte de este programa por medio de streamlit para la universidad. algo que lleve integrado la IA para resolver problemas. […] que se ocurre para hacer por alla para el trabajo del master que luego no sea un trabajo perdido?»
  2. «que te parece si ahora hacemos el control de mantenimiento del mobiliario? mesones, neveras, hornos, etc. todo aquello que merezca ser enlistado con su ficha tecnica, su bitácora de cambios/mantenimientos/reparaciones, y sus propio sistema de alertas segun desplegable de tiempos (de aqui a una semana, un mes, un trimestre) por planificacion.»
  3. «uno de los pilares de esta app es que es una app que será una solucion y no más trabajo para los trabajadores. […] debo darles flujos de trabajo con los menores clicks y menores pantallas y menores formularios posibles. quizá para implementarlo por primera vez si, pero luego tiene que funcionar como encender un avión.»
  4. «para mi admin debe haber un terminal o algun sitio donde todos los errores o warnings de la aplicacion se acumulen en lista.»
  5. «crea un perfil para la version de streamlit que no pueda dañar nada de lo que tenemos. actualmente tiene clave y si le doy la mia podran ver todo.»
- **Qué delegué al agente y qué revisé a mano:** delegué el código, las tablas de la base de datos y las pruebas automáticas. Decidí yo qué debía hacer la app y cómo debía sentirse, usé cada pantalla y le devolví los fallos tal como me salían, y configuré los Secrets en Streamlit Cloud.

## Prueba y mejora

| Quién la probó | Qué probó | Qué pasó | Qué cambié |
|---|---|---|---|
| Yo como usuario | La pantalla Hoy | Botones muy grandes para textos cortos, y la plancha como rutina aparte | Pantalla más limpia y la plancha dentro del cierre |
| Yo como usuario | Entrar a la pantalla Hoy | Error `TypeError` en `registro_rapido()` | Corregido el fallo |
| Yo como usuario | La app publicada en Streamlit Cloud | No encontraba las claves de Supabase y no estaba claro por qué | Un diagnóstico que enseña los nombres de las claves, nunca sus valores |
| Yo como usuario | Entrar como invitado | La app iba directa al PIN y no había por dónde entrar | Botón «Entrar como invitado» en la pantalla del PIN |
| Trabajadores de los locales | Apuntar temperaturas desde un iPhone | El teclado numérico no tiene «-» y no se podían apuntar negativas | Ya se pueden apuntar temperaturas negativas |
| Trabajadores de los locales | Consultar las alertas | Solo salían a gerencia | Alertas en el menú de todo el equipo |
| Trabajadoras de los locales | Crear etiquetas | Pidieron categorías propias, filtrar por partida y una etiqueta de «abierto el día» | Categorías, partidas y etiqueta `ABIERTO` con fecha y hora |

Las tres últimas filas salen del Q&A con los trabajadores en el uso diario, sobre la versión web de LilOS que continúa esta app y sobre la etiquetadora. Las cuatro primeras son de la app de este repositorio.

## Ejecutar en local (opcional)

```bash
pip install -r gerencia/requirements.txt
streamlit run gerencia/app.py
```

Sin ninguna clave arranca en **modo demostración**: datos inventados que viven en tu sesión y se pierden al cerrar la pestaña (`gerencia/core/demo.py`). Para que funcione el asistente, copia `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml` y pon solo `GEMINI_API_KEY`. Ese archivo no se sube nunca a git.

Para usarla con una base de datos propia, añade también las claves de Supabase, ejecuta en su editor SQL `supabase/schema.sql`, `supabase/mantenimiento.sql`, `supabase/appcc.sql`, `supabase/comunicados.sql` y `supabase/acceso.sql` (el resto de `supabase/` activa módulos opcionales) y crea la primera cuenta con `python gerencia/crear_admin.py`.

Para las pruebas: `pip install pytest` y `pytest gerencia/tests`.

Este repositorio es la entrega del máster, separada del sistema completo de LilOS: no incluye la etiquetadora, ni datos reales ni claves. La versión de la app se lee de `package.json`.

## Capturas

[PENDIENTE: la app funcionando, la app ante un caso límite, un momento del trabajo con la IA y la prueba. Sin ninguna clave a la vista.]
