"""Envía un email si ayer se venció algún mantenimiento (lo ejecuta GitHub Actions cada mañana).

Uso, desde la carpeta LilOS:
    gerencia/.venv/Scripts/python gerencia/enviar_avisos.py            # envía solo si ayer venció algo
    gerencia/.venv/Scripts/python gerencia/enviar_avisos.py --prueba   # solo muestra el email, no envía
    gerencia/.venv/Scripts/python gerencia/enviar_avisos.py --enviar-prueba   # envía un email de ejemplo
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import avisos  # noqa: E402

if __name__ == "__main__":
    if "--enviar-prueba" in sys.argv:
        ejemplo = {"LilOS": {avisos.VENCIDO: ["PRUEBA · Email de prueba de los avisos de LilOS: no hay que hacer nada",
                                              "Así llegará el aviso cuando venza un mantenimiento"]}}
        asunto, texto, cuerpo_html = avisos.componer(ejemplo)
        para = avisos.enviar("[PRUEBA] " + asunto, texto, cuerpo_html)
        print(f"Email de prueba enviado a {', '.join(para)}")
        sys.exit(0)
    pendientes = avisos.recopilar()
    if not pendientes:
        print("Nada vencido ayer: no se envía email.")
        sys.exit(0)
    asunto, texto, cuerpo_html = avisos.componer(pendientes)
    if "--prueba" in sys.argv:
        print(asunto, texto, sep="\n")
        sys.exit(0)
    para = avisos.enviar(asunto, texto, cuerpo_html)
    print(f"Enviado a {', '.join(para)}: {asunto}")
