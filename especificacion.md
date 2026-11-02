# Especificación · LilOS Gerencia

Lo que quiero que haga la app, explicado para que otra persona (o una IA) pueda construirla sin tener que preguntarme mucho.

## 1. Problema y usuario

- **Quién tiene el problema:** los gerentes de mis tres restaurantes, Lilo Brunch (dos en Barcelona y uno en Madrid). Se pasan el día en sala, casi nunca están en una oficina.
- **Cómo lo resuelven hoy:** con los papeles del APPCC, llamando a los técnicos y tirando de memoria.
- **Qué les molesta:** las revisiones se pasan de fecha, nadie tiene a mano lo que se le ha hecho a cada máquina ni cuánto ha costado, y cuando algo se rompe hay que ponerse a buscar a quién llamar.
- **Qué hace la IA:** contesta preguntas con lo que hay en la app, lee la foto de la placa de una máquina, propone qué revisar y cada cuánto, y orienta cuando hay una avería. No decide ni arregla nada: el gerente revisa lo que propone antes de guardarlo, y la avería la resuelve el técnico.

## 2. Qué hace la app

1. **Avisa de lo que toca:** enseña las tareas de esta semana, este mes o este trimestre. Si algo lleva más de 7 días atrasado, se avisa a dirección.
2. **Guarda la historia de cada máquina:** su ficha, la garantía, lo que se le ha hecho y lo que ha costado. Si se apunta una tarea como hecha, se calcula sola la siguiente fecha. Si se apunta una avería, la máquina queda marcada como averiada.
3. **Tiene un asistente con IA:** un chat al que preguntarle cosas del local. También sirve para leer placas, sugerir planes de mantenimiento, ayudar con averías y hacer un resumen de por dónde empezar.

La app tiene más pantallas del día a día del restaurante (Hoy, Rumbo, comunicados, inspecciones), pero para este reto me quedo con estas tres cosas.

## 3. Qué entra y qué sale

| El usuario da… | La app devuelve… | Ejemplo |
|---|---|---|
| Una pregunta en el chat | Una respuesta corta con lo que hay en la app | «¿Qué tengo pendiente esta semana y por dónde empiezo?» → las tareas ordenadas por urgencia |
| La foto de la placa de una máquina | La ficha rellenada, para revisarla y guardarla | Foto de una nevera → marca, modelo, número de serie y temperaturas |
| Una máquina | Las tareas de mantenimiento que le faltan, para elegir cuáles añadir | Un horno → limpieza y revisiones periódicas |
| Lo que le pasa a una máquina | Qué hacer ya, qué comprobar y si hay que llamar al técnico | «La nevera no enfría» → pasos en orden |
| Un apunte en la bitácora | La siguiente fecha calculada, o la máquina marcada como averiada | «Revisión hecha» → la tarea pasa a su próxima fecha |

## 4. La IA

- **Qué uso:** Gemini, en su plan gratuito, y le doy acceso a los datos de la app para que consulte lo que necesite.
- **Por qué:** es gratis, entiende fotos y puede mirar los datos del momento, que cambian cada día. Además, si un día quiero cambiar de proveedor, no tengo que tocar el código.
- **Instrucciones que le doy:** están en `SISTEMA`, en `gerencia/core/ia.py`. Básicamente: eres el asistente del gerente, escribe claro porque lo va a leer en el móvil en mitad del servicio, ten siempre presente la seguridad alimentaria, y no te inventes nada; si no lo sabes, dilo.

## 5. Cómo se usa

1. Entras con tu PIN y ves lo que tienes que hacer hoy.
2. Miras las alertas, abres una máquina, apuntas algo en la bitácora o le preguntas al asistente.
3. Se actualizan las tareas o te responde la IA. Lo que propone la IA no se guarda hasta que tú lo revisas.

## 6. Condiciones

- Tiene que costar cero: IA gratis y publicación gratis (ruta A).
- Las claves van en los secretos, nunca en el código.
- Nada de datos reales de personas ni en el repositorio ni en la versión pública. Por eso, si la app no encuentra claves de Supabase, arranca con datos inventados (`gerencia/core/demo.py`). Cada visitante tiene los suyos y se borran al cerrar la pestaña.
- Tiene que entenderla cualquiera, sin saber nada de tecnología.
- Pocos clics y textos directos: se usa en pleno servicio y muchas veces desde el móvil.
- Si hay contraseña de invitado, ese perfil puede verlo, pero no guardar, borrar ni enviar nada.

## 7. Cómo sé que funciona

| Si pasa esto | Debería pasar esto |
|---|---|
| «¿Qué tengo pendiente esta semana y por dónde empiezo?» | Contesta con las tareas de verdad, primero lo más urgente |
| Subo la foto de una placa | Rellena la ficha y me deja revisarla antes de guardar |
| Subo un archivo que no es una foto válida | «No se ha podido abrir la foto. Prueba con otra en JPG o PNG.» |
| Envío un mensaje vacío | No pasa nada, no se le manda a la IA |
| Pregunto algo que no está en la app ni en internet | Dice que no lo sabe y no se inventa nada |
| Se acaba la cuota de un modelo | Prueba con otro; si se acaban todos: «Se ha agotado la cuota gratuita de la IA por ahora. Prueba dentro de un rato.» |
| No hay conexión con la IA | «No hay conexión con la IA. Revisa internet.» |
| La IA no contesta en mucho rato | «La IA está tardando demasiado. Prueba otra vez en un minuto.» |
| Un invitado intenta guardar | «Modo invitado: no se ha guardado nada» |

## 8. Lo que dejo para después

- La etiquetadora y la impresión de etiquetas desde el local.
- Fotos en la bitácora.
- Sondas de temperatura y que la app actúe sola según la temperatura.
- Comparar locales entre sí, para dirección.

## 9. Publicación

- **Ruta:** A, Streamlit Community Cloud. El archivo principal es `gerencia/app.py`.
- **Equipo:** lo he hecho yo solo.
