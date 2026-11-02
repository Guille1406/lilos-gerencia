# LilOS · Gerencia

App de gestión de **Lilo Brunch** (Lilo Sagrada Familia, Lilo Enric Granados y Lilo Madrid) para controlar el
mantenimiento de neveras, hornos y demás equipos de los tres locales, con un asistente de IA gratuito.

Es el proyecto de un máster de IA, hecho con **Python + Streamlit** y **Supabase** (PostgreSQL) y desarrollado con
**Claude Code** (agente de programación con IA de Anthropic).

## Qué hace

- **Acceso con PIN personal** (como un TPV) y perfiles por rol: admin > dirección > gerencia > trabajadores. Cada uno
  ve lo suyo; se bloquea sola tras unos minutos sin uso.
- **Alertas** de tareas para esta semana, este mes o este trimestre; las atrasadas más de 7 días se escalan a
  dirección. El responsable es el gerente de cada local y, como segunda línea, los directivos.
- **Equipos**: ficha técnica, plan de mantenimiento periódico, garantía, historial y gasto.
- **Bitácora**: cualquier trabajador apunta mantenimientos, inspecciones, averías o reparaciones; al cumplir una
  tarea se recalcula su próxima fecha y una avería marca el equipo como averiado.
- **Asistente del gerente** con IA gratuita: un chat que consulta los datos reales de la intranet (equipos, plan,
  bitácora y gastos, catálogo, etiquetas impresas, personal, documentación) y busca en internet cuando hace falta.
  También lee la foto de la placa de un equipo, sugiere su plan de mantenimiento, orienta ante averías y resume
  qué hacer primero (`gerencia/core/ia.py`, `gerencia/core/intranet.py`). Funciona con cualquier proveedor
  compatible con OpenAI; por defecto, el plan gratuito de Google Gemini.
- **Perfil invitado** de solo lectura para enseñar la app sin que se pueda guardar nada.

## Estructura

| Carpeta | Contenido |
|---|---|
| `gerencia/app.py` | Punto de entrada de la app |
| `gerencia/core/` | Lógica: datos, sesión, IA, plan de mantenimiento, avisos… |
| `gerencia/paginas/` | Páginas de la app |
| `gerencia/tests/` | Pruebas (`pytest`) |
| `supabase/` | Tablas de la base de datos |
| `.streamlit/` | Tema de la app y modelo de claves |

## Ejecutarla en local

Necesita Python 3.11 o superior y un proyecto de Supabase.

```bash
pip install -r gerencia/requirements.txt
streamlit run gerencia/app.py
```

1. Copia `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml` y pon tus claves de Supabase y, para la IA,
   `GEMINI_API_KEY`. Ese archivo no se sube nunca a git.
2. En el editor SQL de Supabase, ejecuta `supabase/schema.sql`, `supabase/mantenimiento.sql`, `supabase/appcc.sql`,
   `supabase/comunicados.sql` y `supabase/acceso.sql`. El resto de archivos de `supabase/` activan módulos opcionales.
3. Crea la primera cuenta (admin) con `python gerencia/crear_admin.py`; el resto de personas, desde la página
   👥 Perfiles.

## Publicarla en Streamlit Community Cloud

Elige este repositorio, la rama `main` y `gerencia/app.py` como archivo principal, y copia las claves en
**Settings → Secrets**. Conviene poner `APP_PASSWORD`, y `INVITADO_PASSWORD` para compartirla con el perfil invitado.

## Pruebas

```bash
pip install pytest
pytest gerencia/tests
```

## Qué no está aquí

Este repositorio es la entrega del máster, separada del sistema completo de LilOS. No incluye la etiquetadora ni el
resto de apps, y tampoco datos reales del negocio ni claves: están en la base de datos y en los Secrets. La versión
de la app se lee de `package.json`.
