#!/usr/bin/env python3
"""Dice cual es tu canal de YouTube y con que direccion se abre.

    mi_canal.py

SOLO LEE. No sube nada, no toca ningun video y no cuesta cuota que importe:
`channels.list` vale una unidad de las 10.000 del dia.

Existe porque la direccion del canal no estaba escrita en ningun lado del
repositorio, y adivinarla a partir de un video o de una lista no se puede.
Hace falta el permiso que ya esta en los secretos del repositorio, asi que se
corre desde la pestania Actions.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import youtube  # noqa: E402


def canal(token: str = "") -> dict:
    """Los datos del canal de quien dio el permiso."""
    token = token or youtube.acceso()
    datos = youtube._api("GET", "channels", token,
                         params={"part": "snippet,contentDetails,statistics",
                                 "mine": "true"})
    items = datos.get("items") or []
    return items[0] if items else {}


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env")
    if youtube.faltan():
        print("Faltan %s en el entorno." % ", ".join(youtube.faltan()))
        return 2
    try:
        c = canal()
    except Exception as e:                                # noqa: BLE001
        print("No pude preguntarle a YouTube: %s" % e)
        return 1
    if not c:
        print("El permiso anda pero esa cuenta no tiene ningun canal.")
        return 1

    ficha = c.get("snippet") or {}
    cuentas = c.get("statistics") or {}
    print("Canal: %s" % (ficha.get("title") or "?"))
    print("Id:    %s" % c.get("id"))
    if cuentas:
        print("Tiene %s videos y %s suscriptores."
              % (cuentas.get("videoCount", "?"), cuentas.get("subscriberCount", "?")))
    print()
    # El nombre corto (@algo) es el que conviene mostrar: se lee, se dicta y
    # no cambia si YouTube renumera nada. Si no hay, queda la del id.
    corto = ficha.get("customUrl") or ""
    if corto:
        print("Para la biografia:  https://www.youtube.com/%s" % corto)
        print("Solo los videos:    https://www.youtube.com/%s/videos" % corto)
        print("Solo los shorts:    https://www.youtube.com/%s/shorts" % corto)
    else:
        print("Para la biografia:  https://www.youtube.com/channel/%s" % c.get("id"))
        print("Solo los videos:    https://www.youtube.com/channel/%s/videos" % c.get("id"))
        print()
        print("El canal no tiene nombre corto (@algo). Se elige una sola vez "
              "en YouTube Studio -> Personalizacion -> Informacion basica, y "
              "despues la direccion queda para siempre.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
