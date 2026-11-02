"""Hoja imprimible con un código QR por equipo (abre su ficha en la app al escanearlo)."""
import html

import segno


def enlace(base: str, equipo_id: str) -> str:
    return f"{base}/equipos?equipo={equipo_id}"


def hoja_qr(equipos: list[dict], base: str, local: str) -> str:
    tarjetas = "".join(
        f"<div class='t'>{segno.make(enlace(base, e['id']), error='m').svg_inline(scale=4, border=1)}"
        f"<b>{html.escape(e['nombre'])}</b><span>{html.escape(local)} · LilOS</span></div>"
        for e in sorted(equipos, key=lambda e: e["nombre"]))
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'><title>QR de equipos</title><style>"
        "body{font-family:Arial,sans-serif;margin:16px;color:#292524}"
        ".g{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}"
        ".t{border:1px dashed #DDC1A8;border-radius:8px;padding:10px;text-align:center;break-inside:avoid}"
        ".t svg{width:120px;height:120px}.t b{display:block;font-size:14px;margin-top:4px}"
        ".t span{display:block;font-size:10px;color:#78716C}"
        "@media print{body{margin:0}}</style></head><body>"
        f"<div class='g'>{tarjetas}</div></body></html>")
