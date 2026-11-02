# Especificación · LilOS Gerencia

> Especificación de la app de mantenimiento de equipos de Lilo Brunch, entregada en el reto del máster. De ella sale la ficha del hito de la semana 2.

## 1. Problema y usuario

- **Quién tiene el problema:** los gerentes de los tres restaurantes de Lilo Brunch (dos en Barcelona y uno en Madrid), que trabajan en plena sala y casi nunca en una oficina.
- **Cómo lo resuelve hoy:** con documentos del plan APPCC, llamadas a técnicos y lo que cada gerente recuerda.
- **Qué le molesta de cómo lo hace hoy:** las revisiones se pasan de fecha, el historial y el gasto de cada equipo están dispersos, y ante una avería hay que buscar a quién llamar y qué comprobar.
- **Qué parte resuelve la IA:** responde preguntas con los datos reales de la app, lee la foto de la placa de un equipo, propone su plan de mantenimiento, orienta ante una avería y resume por dónde empezar. Quedan fuera las decisiones y las reparaciones: el gerente revisa lo que propone la IA antes de guardarlo, y la avería la resuelve un técnico.

## 2. Qué hace el producto

1. **Plan y alertas:** muestra las tareas de mantenimiento de esta semana, este mes o este trimestre, y escala a dirección las atrasadas más de 7 días.
2. **Equipos y bitácora:** guarda la ficha técnica, la garantía, el historial y el gasto de cada equipo. Al apuntar una tarea cumplida se recalcula su próxima fecha, y una avería marca el equipo como averiado.
3. **Asistente con IA:** un chat que consulta los datos de la app y, si hace falta, internet. También lee placas, sugiere planes, orienta ante averías y resume la situación del local.

La app tiene además otras páginas del día a día del restaurante (Hoy, Rumbo, comunicados, inspecciones). Estas tres funcionalidades son el alcance de este reto.

## 3. Entradas y salidas

| El usuario da… | La app devuelve… | Ejemplo |
|---|---|---|
| Una pregunta en el chat | Una respuesta breve basada en los datos de la app | «¿Qué tengo pendiente esta semana y por dónde empiezo?» → lista de tareas ordenada por prioridad |
| La foto de la placa de un equipo | Los campos de la ficha, para revisar y guardar | Foto de una nevera → tipo, marca, modelo, número de serie y temperaturas |
| Un equipo | Las tareas de mantenimiento que le faltan, para marcar y añadir | Horno → limpieza y revisión periódicas propuestas |
| El síntoma de una avería | Qué hacer ya, qué comprobar, causas posibles y si llamar al técnico | «La nevera no enfría» → pasos ordenados |
| Un apunte en la bitácora | La próxima fecha recalculada o el equipo marcado como averiado | «Revisión hecha» → la tarea pasa a su siguiente fecha |

## 4. La pieza de IA

- **Opción elegida:** API de un LLM (Gemini), en su plan gratuito, con herramientas que consultan la base de datos de la app.
- **Por qué:** el asistente responde con los datos que cambian cada día, sin copiarlos a un índice, y Gemini también lee fotos. Se usa la API compatible con OpenAI, de modo que se puede cambiar de proveedor desde la configuración, sin tocar el código.
- **Instrucciones para el modelo (system prompt):** está en `SISTEMA`, en `gerencia/core/ia.py`. Le dice que es el asistente del gerente, que escribe en español de España, claro y práctico para leer en el móvil en mitad del servicio, que tiene presente la seguridad alimentaria y que no inventa datos: si algo no está en la app ni lo encuentra, lo dice.

## 5. Flujo del usuario

1. El usuario entra con su PIN personal (o como invitado, solo lectura) y ve lo que tiene que hacer hoy.
2. Consulta las alertas, abre la ficha de un equipo, apunta algo en la bitácora o escribe al asistente.
3. Recibe las tareas actualizadas o la respuesta de la IA. Lo que propone la IA no se guarda hasta que lo revisa.

## 6. Restricciones

- Coste cero: capa gratuita de la API y despliegue gratuito (ruta A).
- Las claves van en secretos, nunca en el código.
- Sin datos personales reales en el repositorio ni en la versión pública: la app del reto debe conectarse a una base de demostración con datos inventados.
- Lenguaje sencillo, para alguien sin conocimientos técnicos.
- Pocos clics y textos directos: se usa en mitad del servicio, muchas veces desde el móvil.
- El invitado puede recorrer la app, pero no guardar, borrar ni enviar nada.

## 7. Criterios de aceptación

La app está bien si:

| Entrada | Resultado esperado |
|---|---|
| «¿Qué tengo pendiente esta semana y por dónde empiezo?» | Responde con las tareas reales del local, lo más importante primero |
| Foto de una placa | Rellena la ficha para que el usuario la revise antes de guardar |
| Archivo que no es una imagen válida | «No se ha podido abrir la foto. Prueba con otra en JPG o PNG.» |
| Mensaje vacío | No se envía nada a la IA |
| Pregunta sobre algo que no está en la app ni en internet | Dice que no lo sabe, sin inventar datos |
| Se agota la cuota de un modelo | Prueba el siguiente; si se agotan todos: «Se ha agotado la cuota gratuita de la IA por ahora. Prueba dentro de un rato.» |
| No hay conexión con la IA | «No hay conexión con la IA. Revisa internet.» |
| El invitado intenta guardar | «Modo invitado: no se ha guardado nada» |

## 8. Fuera de alcance (por ahora)

- La etiquetadora y la impresión de etiquetas desde el local.
- Fotos en la bitácora.
- Sondas de temperatura y acciones automáticas según la temperatura.
- Comparativa entre locales para dirección.

## 9. Despliegue

- **Ruta:** A (Streamlit Community Cloud), con `gerencia/app.py` como archivo principal.
- **Si trabajáis en equipo (opcional):** trabajo individual.
