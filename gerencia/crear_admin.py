"""Crea (o actualiza) la cuenta admin de LilOS, la que está por encima de todo.

Se ejecuta UNA vez en tu ordenador, desde la carpeta LilOS:
    gerencia/.venv/Scripts/python gerencia/crear_admin.py

Pide nombre, usuario y contraseña en la terminal (la contraseña no se ve al escribirla ni se guarda tal cual).
Con esa cuenta entras en la app → «Dirección: entrar con usuario» y desde Perfiles das PIN a los demás.
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import db, sesion  # noqa: E402


def main() -> None:
    nombre = input("Tu nombre (como aparecerá en la app): ").strip()
    usuario = input("Usuario para entrar: ").strip().lower()
    clave = getpass.getpass("Contraseña (mínimo 8 caracteres): ")
    if not nombre or not usuario or len(clave) < 8:
        sys.exit("Falta el nombre o el usuario, o la contraseña tiene menos de 8 caracteres. No se ha guardado nada.")
    if clave != getpass.getpass("Repítela: "):
        sys.exit("Las contraseñas no coinciden. No se ha guardado nada.")

    personas = db.trabajadores()
    existente = next((t for t in personas if (t.get("usuario") or "").lower() == usuario
                      or t["name"].lower() == nombre.lower()), None)
    fila = {"name": nombre, "usuario": usuario, "rol": "admin", "activo": True, "pin_hash": sesion.huella(clave)}
    if existente:
        db.table("trabajadores").update(fila).eq("id", existente["id"]).execute()
        print(f"Cuenta admin actualizada: {nombre} ({usuario}).")
    else:
        db.table("trabajadores").insert({"id": f"admin-{usuario}", **fila}).execute()
        print(f"Cuenta admin creada: {nombre} ({usuario}).")


if __name__ == "__main__":
    main()
