# Entrega final · LilOS Gerencia

**Nombre y apellidos:** Guillermo Jesús Pinto Henriques

## 1. Enlaces

- **App desplegada:** https://lilos-gerencia-ewnoezk4zt3ej97vu4eqem.streamlit.app (versión de demostración, con datos inventados; los PIN de prueba salen al entrar)
- **Repositorio:** https://github.com/Guille1406/lilos-gerencia

## 2. Problema y usuario

Los gerentes de los tres restaurantes de Lilo Brunch son responsables del mantenimiento de neveras, hornos y demás equipos, pero trabajan en plena sala. Sin la app dependen de los documentos del plan APPCC, de las llamadas a los técnicos y de su memoria, de modo que las revisiones se pueden pasar de fecha y el historial y el gasto de cada equipo están dispersos. La IA responde con los datos de la app, lee la foto de la placa de un equipo, propone su plan de mantenimiento y orienta ante una avería. Quedan fuera las decisiones y las reparaciones: el gerente revisa lo que propone la IA antes de guardarlo, y la avería la resuelve un técnico.

## 3. Especificación

https://github.com/Guille1406/lilos-gerencia/blob/main/especificacion.md

## 4. La pieza de IA

- **Qué usa:** la API de Gemini en su plan gratuito (`gemini-flash-lite-latest`, con `gemini-3.5-flash-lite` y `gemini-flash-latest` de reserva), con herramientas que consultan la base de datos de la app.
- **Por qué esa opción:** es gratis, entiende fotos y puede consultar datos que cambian cada día sin mantener un índice aparte. Al usar la API compatible con OpenAI, se puede cambiar de proveedor desde la configuración.
- **Qué pasa si falla:** si un modelo se satura o se queda sin cuota, se prueba el siguiente. Si fallan todos, la app avisa con un mensaje claro («Se ha agotado la cuota gratuita de la IA por ahora. Prueba dentro de un rato.») y el resto de la app sigue funcionando.
- **Dónde está la clave:** en los Secrets de Streamlit Cloud, y en local en `.streamlit/secrets.toml`, fuera de git. Nunca en el código.

## 5. Proceso con IA

- **Herramientas:** Claude Code para programar y Claude Design para el diseño.
- **Fichero de contexto del agente:** https://github.com/Guille1406/lilos-gerencia/blob/main/AGENTS.md
- **Prompts clave** (copiados de mis conversaciones; `[…]` marca lo que he recortado):
  1. «tengo que hacer una parte de este programa por medio de streamlit para la universidad. algo que lleve integrado la IA para resolver problemas. […] que se ocurre para hacer por alla para el trabajo del master que luego no sea un trabajo perdido?»
  2. «que te parece si ahora hacemos el control de mantenimiento del mobiliario? mesones, neveras, hornos, etc. todo aquello que merezca ser enlistado con su ficha tecnica, su bitácora de cambios/mantenimientos/reparaciones, y sus propio sistema de alertas segun desplegable de tiempos (de aqui a una semana, un mes, un trimestre) por planificacion.»
  3. «uno de los pilares de esta app es que es una app que será una solucion y no más trabajo para los trabajadores. […] debo darles flujos de trabajo con los menores clicks y menores pantallas y menores formularios posibles. quizá para implementarlo por primera vez si, pero luego tiene que funcionar como encender un avión.»
  4. «para mi admin debe haber un terminal o algun sitio donde todos los errores o warnings de la aplicacion se acumulen en lista.»
  5. «crea un perfil para la version de streamlit que no pueda dañar nada de lo que tenemos. actualmente tiene clave y si le doy la mia podran ver todo.»
- **Qué delegué al agente y qué revisé a mano:** delegué el código, las tablas de la base de datos y las pruebas automáticas. Decidí yo qué debía hacer la app y cómo debía sentirse, usé cada pantalla y le devolví los fallos tal como me salían, y configuré los Secrets en Streamlit Cloud.

## 6. Prueba y mejora

| Quién la probó | Qué probó | Qué pasó | Qué cambié |
|---|---|---|---|
| Yo como usuario | La pantalla Hoy | Botones muy grandes para textos cortos, y la plancha como rutina aparte | Pantalla más limpia y la plancha dentro del cierre |
| Yo como usuario | Entrar a la pantalla Hoy | Error `TypeError` en `registro_rapido()` | Corregido el fallo |
| Yo como usuario | La app publicada en Streamlit Cloud | No encontraba las claves de Supabase y no estaba claro por qué | Un diagnóstico que enseña los nombres de las claves, nunca sus valores |
| Yo como usuario | Entrar como invitado | La app iba directa al PIN y no había por dónde entrar | Botón «Entrar como invitado» en la pantalla del PIN |
| Trabajadores de los locales | Apuntar temperaturas desde un iPhone | El teclado numérico no tiene «-» y no se podían apuntar negativas | Ya se pueden apuntar temperaturas negativas |
| Trabajadores de los locales | Consultar las alertas | Solo salían a gerencia | Alertas en el menú de todo el equipo |
| Trabajadoras de los locales | Crear etiquetas | Pidieron categorías propias, filtrar por partida y una etiqueta de «abierto el día» | Categorías, partidas y etiqueta `ABIERTO` con fecha y hora |

Las tres últimas filas salen del Q&A con los trabajadores en el uso diario, sobre la versión web de LilOS que continúa esta app y sobre la etiquetadora. Las cuatro primeras son de la app entregada.

## 7. Pitch escrito

1. Los gerentes de los tres restaurantes de Lilo Brunch tienen que mantener neveras, hornos y demás equipos mientras trabajan en plena sala, y las revisiones se les pueden pasar de fecha.
2. LilOS Gerencia les enseña qué toca esta semana, guarda la ficha y la bitácora de cada equipo, y escala a dirección lo que lleva más de 7 días atrasado.
3. La IA contesta con los datos de la propia app, lee la foto de la placa de un equipo y orienta ante una avería, sin que el gerente tenga que buscar en documentos.
4. Mis trabajadores la han probado en el día a día de los locales y eso ha cambiado el producto: por ejemplo, el teclado del iPhone no tenía «-» para apuntar temperaturas negativas, y las alertas pasaron a verlas todos.
5. Después llevaría lo aprendido a una web propia para las tablets de cada local, que ya está en marcha, con la pantalla Hoy como lista de comprobación de un avión.

## 8. Capturas

1. **La app funcionando** en su caso principal.
   [PENDIENTE: captura]
2. **La app ante un caso límite o un error:** una clave de IA no válida, con su mensaje.
   [PENDIENTE: captura]
3. **El trabajo con la IA:** uno de mis prompts clave y lo que devolvió Claude Code.
   [PENDIENTE: captura]
4. **La prueba:** la app con un caso que me hizo cambiar algo.
   [PENDIENTE: captura]
