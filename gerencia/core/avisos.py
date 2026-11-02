"""Avisos por email cuando se vence una fecha de mantenimiento.

Cada mañana se comprueba (GitHub Actions), pero solo se envía email si ayer se venció algo: una tarea del plan de
mantenimiento o la revisión de un equipo o servicio (friorista, plagas, extintores…). Si a los 7 días sigue sin
hacerse, se envía un segundo aviso: escalado a dirección. Nunca se repite el mismo aviso otros días.

Se envía por SMTP (por ejemplo, Gmail / Google Workspace con una contraseña de aplicación). Configuración:
    AVISOS_PARA    destinatarios, separados por comas (por defecto ops@lilobrunch.com)
    SMTP_USUARIO   cuenta que envía (ej. ops@lilobrunch.com)
    SMTP_CLAVE     contraseña de aplicación de esa cuenta
    SMTP_SERVIDOR  por defecto smtp.gmail.com · SMTP_PUERTO por defecto 587
"""
import html
import smtplib
from datetime import date, timedelta
from email.message import EmailMessage

from core import db, plan, registro

DESTINO = "ops@lilobrunch.com"
VENCIDO = "🔴 Vencido"
ESCALADO = f"🚨 Escalado a dirección (más de {plan.DIAS_ESCALADO} días sin hacerse)"


def configurado() -> bool:
    return bool(db.config("SMTP_USUARIO") and db.config("SMTP_CLAVE")) and not db.solo_lectura()


def recopilar(hoy: date | None = None, todos: bool = False) -> dict:
    """{local: {apartado: [líneas]}} con lo que se venció ayer o pasó a escalado ayer.
    Con todos=True, todo lo que está vencido ahora mismo (para verlo en la app)."""
    hoy = hoy or date.today()
    vence_ayer = hoy - timedelta(days=1)
    escala_ayer = hoy - timedelta(days=plan.DIAS_ESCALADO + 1)
    proveedores = {p["id"]: p for p in db.proveedores()}

    def apartado(fecha: date) -> str | None:
        if todos:
            return ESCALADO if (hoy - fecha).days > plan.DIAS_ESCALADO else VENCIDO if fecha < hoy else None
        return VENCIDO if fecha == vence_ayer else ESCALADO if fecha == escala_ayer else None

    resultado = {}
    for local in db.locales():
        equipos = {e["id"]: e for e in db.equipos(local["id"])}
        avisos = {}
        for t in db.tareas(list(equipos)):
            fecha = date.fromisoformat(t["proxima_fecha"])
            if clave := apartado(fecha):
                avisos.setdefault(clave, []).append(
                    f"{t['tarea']} · {equipos[t['equipo_id']]['nombre']} · tocaba el {plan.fecha_es(fecha)}")
        revisables = [e for e in equipos.values() if e["estado"] != "baja"] + db.servicios(local["id"])
        for objeto in revisables:
            if not objeto.get("proxima_revision"):
                continue
            fecha = date.fromisoformat(objeto["proxima_revision"])
            if clave := apartado(fecha):
                prov = proveedores.get(objeto.get("proveedor_id"))
                avisos.setdefault(clave, []).append(
                    f"Revisión de {objeto['nombre']} · tocaba el {plan.fecha_es(fecha)}"
                    + (f" · llamar a {prov['nombre']} {prov.get('telefono') or ''}" if prov else ""))
        if avisos:
            resultado[local["nombre"]] = avisos
    return resultado


def componer(avisos: dict, hoy: date | None = None) -> tuple[str, str, str]:
    """Devuelve (asunto, texto, html) del email."""
    hoy = hoy or date.today()
    total = sum(len(lineas) for apartados in avisos.values() for lineas in apartados.values())
    escalados = any(ESCALADO in apartados for apartados in avisos.values())
    asunto = (f"LilOS · {'🚨 ' if escalados else ''}{total} mantenimiento{'s' if total != 1 else ''} "
              f"vencido{'s' if total != 1 else ''} · {', '.join(avisos)}")
    texto, partes = [], []
    for local, apartados in avisos.items():
        texto.append(f"\n{local.upper()}")
        partes.append(f"<h2 style='color:#A44A3F;font-size:18px;margin:24px 0 8px'>{html.escape(local)}</h2>")
        for apartado, lineas in apartados.items():
            texto.append(f"\n{apartado}\n" + "\n".join(f"  - {l}" for l in lineas))
            partes.append(f"<p style='margin:12px 0 4px;font-weight:bold'>{html.escape(apartado)}</p><ul style='margin:0'>"
                          + "".join(f"<li>{html.escape(l)}</li>" for l in lineas) + "</ul>")
    pie = ("Aviso automático de LilOS. Cuando esté hecho, regístralo en la app de gerencia (Alertas, Equipos o "
           "Servicios) y la próxima fecha se calcula sola.")
    cuerpo_html = (
        "<div style='font-family:Inter,Arial,sans-serif;color:#292524;max-width:640px'>"
        f"<h1 style='font-size:20px;margin:0 0 4px'>Mantenimiento vencido · {plan.fecha_es(hoy)}</h1>"
        + "".join(partes) + f"<p style='color:#78716C;font-size:12px;margin-top:24px'>{pie}</p></div>")
    return asunto, f"Mantenimiento vencido · {plan.fecha_es(hoy)}\n" + "\n".join(texto) + f"\n\n{pie}", cuerpo_html


@registro.capturar("Avisos · email")
def enviar(asunto: str, texto: str, cuerpo_html: str) -> list[str]:
    """Envía el email y devuelve los destinatarios."""
    usuario, clave = db.config("SMTP_USUARIO"), db.config("SMTP_CLAVE")
    if not (usuario and clave):
        raise RuntimeError("Faltan SMTP_USUARIO y SMTP_CLAVE en la configuración.")
    para = [d.strip() for d in (db.config("AVISOS_PARA") or DESTINO).split(",") if d.strip()]
    mensaje = EmailMessage()
    mensaje["Subject"], mensaje["From"], mensaje["To"] = asunto, f"LilOS <{usuario}>", ", ".join(para)
    mensaje.set_content(texto)
    mensaje.add_alternative(cuerpo_html, subtype="html")
    with smtplib.SMTP(db.config("SMTP_SERVIDOR") or "smtp.gmail.com", int(db.config("SMTP_PUERTO") or 587),
                      timeout=30) as smtp:
        smtp.starttls()
        smtp.login(usuario, clave)
        smtp.send_message(mensaje)
    return para
