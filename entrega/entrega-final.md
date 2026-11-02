# Entrega final · LilOS Gerencia

**Nombre y apellidos:** Guillermo Jesús Pinto Henriques

## 1. Enlaces

- **App:** https://lilos-gerencia-ewnoezk4zt3ej97vu4eqem.streamlit.app (es una demo con datos inventados; los PIN para entrar salen en la primera pantalla)
- **Repositorio:** https://github.com/Guille1406/lilos-gerencia

## 2. Problema y usuario

Tengo tres restaurantes, Lilo Brunch, y mis gerentes son los responsables del mantenimiento de neveras, hornos y demás máquinas. El problema es que se pasan el día en sala. Sin la app tiran de los papeles del APPCC, de llamar a los técnicos y de memoria, así que las revisiones se pasan de fecha y nadie tiene claro qué se le ha hecho a cada máquina ni cuánto ha costado. La IA contesta con los datos de la app, lee la foto de la placa de una máquina, propone qué revisar y orienta cuando algo se rompe. Lo que no hace es decidir ni arreglar nada: el gerente revisa lo que propone antes de guardarlo, y la avería la resuelve el técnico.

## 3. Especificación

https://github.com/Guille1406/lilos-gerencia/blob/main/especificacion.md

## 4. La pieza de IA

- **Qué usa:** Gemini, en su plan gratis (`gemini-flash-lite-latest`, y si falla, `gemini-3.5-flash-lite` o `gemini-flash-latest`). Le doy acceso a los datos de la app para que los consulte.
- **Por qué:** es gratis, entiende fotos y mira los datos del momento. Y si un día quiero cambiar de proveedor, no tengo que tocar el código.
- **Si falla:** prueba con otro modelo, y si no, avisa con un mensaje normal, como «Se ha agotado la cuota gratuita de la IA por ahora. Prueba dentro de un rato.». El resto de la app sigue funcionando. Eso sí, al ser gratis, a veces tarda: he visto respuestas de hasta 30 segundos.
- **Dónde está la clave:** en los Secrets de Streamlit Cloud, y en mi ordenador en un archivo que no se sube a GitHub. Nunca en el código.

## 5. Proceso con IA

- **Herramientas:** Claude Code para programar y Claude Design para el diseño.
- **Instrucciones para el agente:** https://github.com/Guille1406/lilos-gerencia/blob/main/AGENTS.md
- **Prompts que más me han servido** (copiados tal cual de mis conversaciones; […] es donde he recortado):
  1. «tengo que hacer una parte de este programa por medio de streamlit para la universidad. algo que lleve integrado la IA para resolver problemas. […] que se ocurre para hacer por alla para el trabajo del master que luego no sea un trabajo perdido?»
  2. «que te parece si ahora hacemos el control de mantenimiento del mobiliario? mesones, neveras, hornos, etc. todo aquello que merezca ser enlistado con su ficha tecnica, su bitácora de cambios/mantenimientos/reparaciones, y sus propio sistema de alertas segun desplegable de tiempos (de aqui a una semana, un mes, un trimestre) por planificacion.»
  3. «uno de los pilares de esta app es que es una app que será una solucion y no más trabajo para los trabajadores. […] debo darles flujos de trabajo con los menores clicks y menores pantallas y menores formularios posibles. quizá para implementarlo por primera vez si, pero luego tiene que funcionar como encender un avión.»
  4. «para mi admin debe haber un terminal o algun sitio donde todos los errores o warnings de la aplicacion se acumulen en lista.»
  5. «crea un perfil para la version de streamlit que no pueda dañar nada de lo que tenemos. actualmente tiene clave y si le doy la mia podran ver todo.»
- **Qué hizo el agente y qué hice yo:** el agente escribió el código, las tablas de la base de datos y las pruebas. Yo decidí qué tenía que hacer la app y cómo tenía que sentirse, usé cada pantalla y le fui pasando los fallos tal como me salían. Lo de configurar las claves en Streamlit también lo hice yo.

## 6. Prueba y mejora

| Quién | Qué probó | Qué pasó | Qué cambié |
|---|---|---|---|
| Yo | La pantalla Hoy | Botones enormes para textos cortos, y la plancha iba aparte | Pantalla más limpia y la plancha dentro del cierre |
| Yo | Entrar en Hoy | Saltaba un error y no se abría | Se corrigió |
| Yo | La app ya publicada | No encontraba las claves y no se entendía por qué | Un aviso que enseña los nombres de las claves que ve, nunca su valor |
| Yo | Entrar como invitado | Iba directa al PIN y no había por dónde entrar | Un botón para entrar como invitado |
| Yo | El asistente ya publicado | Se quedaba pensando y luego no respondía, porque la IA gratis a veces tarda mucho | Le di más margen de tiempo y un aviso claro si no contesta |
| Trabajadores | Apuntar temperaturas en el iPhone | El teclado no tiene «-» y no se podían poner negativas | Ya se pueden apuntar |
| Trabajadores | Ver las alertas | Solo las veía gerencia | Ahora salen en el menú de todo el equipo |
| Las chicas del equipo | Crear etiquetas | Pidieron categorías propias, filtrar por partida y una etiqueta de «abierto el día» | Añadidas |

Las tres últimas filas vienen de lo que me han ido diciendo mis trabajadores en el día a día. Esas pruebas fueron con la versión web de LilOS, que es la continuación de esta app, y con la etiquetadora. Las cinco primeras son de la app que entrego.

## 7. Pitch escrito

1. Tengo tres restaurantes y mis gerentes tienen que estar pendientes de neveras, hornos y demás máquinas mientras trabajan en sala, así que las revisiones se les pasan.
2. Esta app les dice qué toca esta semana, guarda lo que se le ha hecho a cada máquina y avisa a dirección si algo lleva más de 7 días atrasado.
3. La IA les contesta con los datos de la app, lee la placa de una máquina con una foto y les orienta si algo se rompe, sin tener que ponerse a buscar en papeles.
4. Mis trabajadores lo han ido probando en el día a día y eso me ha hecho cambiar cosas: por ejemplo, en el iPhone no salía el «-» para apuntar temperaturas negativas, y al final las alertas las ve todo el equipo.
5. Lo siguiente, que ya está en marcha, es llevar todo esto a una web propia para las tablets de cada local, con la pantalla Hoy funcionando como la lista de comprobación de un avión.

## 8. Capturas

1. **La app funcionando:** el asistente contestando en la app publicada.
   [PENDIENTE: captura]
2. **Cuando algo falla:** el aviso que sale si la clave de la IA no vale.
   [PENDIENTE: captura]
3. **Trabajando con la IA:** uno de mis prompts y lo que me devolvió Claude Code.
   [PENDIENTE: captura]
4. **Una prueba:** un error que me salió al abrir Hoy y que me hizo cambiar algo.
   [PENDIENTE: captura]
