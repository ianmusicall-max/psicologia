#!/usr/bin/env python3
"""Dice si la pagina esta en condiciones de publicar en Instagram.

    revisar_instagram.py

Comprueba las tres cosas, en orden, y dice cual falta:

  1. que haya una cuenta de Instagram PROFESIONAL vinculada a la pagina,
  2. que el token traiga instagram_basic e instagram_content_publish,
La direccion publica de la imagen NO es un requisito: es la de la foto que
Facebook acaba de publicar. Este script pedia un PUBLIC_BASE_URL cuando
todavia no existia ese camino, y seguia pidiendolo despues: decia que faltaba
algo que ya estaba resuelto.

SOLO LEE. No publica ni cambia nada, ni en Facebook ni en Instagram.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import config, instagram  # noqa: E402


def main(argv=None) -> int:
    load_dotenv(ROOT / ".env")
    pagina = config.cargar()
    if not (pagina.fb_page_id and pagina.fb_token):
        print("Faltan %s y %s en el .env." % (pagina.page_id_env, pagina.token_env))
        return 2

    falta = []

    cuenta = instagram.cuenta_vinculada(pagina)
    if "error" in cuenta:
        print("No pude preguntarle a Facebook: %s" % cuenta["error"])
        return 1
    print("Pagina: %s" % cuenta.get("pagina"))
    if cuenta.get("id"):
        print("Instagram vinculado: @%s (id %s)" % (cuenta.get("usuario") or "?", cuenta["id"]))
    else:
        print("Instagram vinculado: NINGUNO")
        falta.append("vincular una cuenta de Instagram profesional a la pagina, "
                     "desde la configuracion de la pagina en Facebook")

    app_id, app_secret = os.environ.get("FB_APP_ID"), os.environ.get("FB_APP_SECRET")
    if not (app_id and app_secret):
        print("Permisos: no pude mirarlos, faltan FB_APP_ID y FB_APP_SECRET en el .env")
    else:
        scopes = instagram.scopes_del_token(pagina, app_id, app_secret)
        if scopes is None:
            print("Permisos: no pude mirarlos, revisa FB_APP_ID y FB_APP_SECRET")
        else:
            faltantes = instagram.permisos_que_faltan(scopes)
            if faltantes:
                print("Permisos: FALTAN %s" % ", ".join(faltantes))
                falta.append("generar el token de usuario otra vez con %s tildados, "
                             "y correr scripts/token_permanente.py --guardar --pagina %s"
                             % (", ".join(faltantes), pagina.fb_page_id))
            else:
                print("Permisos: estan los dos (%s)" % ", ".join(instagram.PERMISOS))

    print("Imagen: %s" % instagram.DE_DONDE_SALE_LA_IMAGEN)

    print()
    if not falta:
        if pagina.instagram:
            print("Esta todo y ya esta prendido: cada publicacion sale en las dos.")
        else:
            print("Esta todo. Para prenderlo: instagram: true en config/pagina.yaml")
        return 0
    print("Para publicar en Instagram falta:")
    for i, x in enumerate(falta, 1):
        print("  %d. %s" % (i, x))
    return 1


if __name__ == "__main__":
    sys.exit(main())
