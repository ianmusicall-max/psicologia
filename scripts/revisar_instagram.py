#!/usr/bin/env python3
"""Dice si la pagina esta en condiciones de publicar en Instagram.

    revisar_instagram.py
    revisar_instagram.py --telegram    manda la respuesta al chat

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


# Lo que hace falta para que un REEL salga por API, y como se supo, porque
# costo una tarde y la primera respuesta estaba equivocada.
#
# El 2026-10-24 el reel se rechazaba con un «ProcessingFailedError» mientras
# la foto de cada frase salia sin problema en la MISMA cuenta y con el MISMO
# token. La primera hipotesis fue el TIPO DE CUENTA -Empresa contra Creador-
# y era FALSA. Lo que fallaba era el mecanismo: la foto no se le sube a
# Instagram, se la baja el de una direccion publica, y el reel se le estaba
# subiendo byte a byte. Dandole la direccion del mp4, el mismo reel entro en
# la misma cuenta sin tocar una sola cosa del perfil.
#
# Queda escrito con ese detalle a proposito. «Cambia la cuenta a Empresa» es
# el consejo que uno encuentra en cualquier foro, y cambiarla no es gratis:
# en Instagram una cuenta de Empresa pierde parte de la biblioteca de musica,
# y en TikTok una cuenta de Empresa queda fuera del programa que paga.
# Mandar a cambiarla por un problema que era otro se paga caro.
REELS_PIDEN = (
    "que el mp4 se le pase por DIRECCION publica y no subiendole los bytes: "
    "es lo unico que de verdad fallaba, y ya esta arreglado",
    "que la cuenta NO sea privada",
    "que no tenga restricciones de contenido abiertas (un aviso de derechos "
    "de autor sin resolver alcanza para que un reel se rechace)",
)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--telegram", action="store_true",
                    help="mandar la respuesta al chat")
    args = ap.parse_args(argv or [])
    load_dotenv(ROOT / ".env")
    # El texto se arma UNA vez y se usa dos: en pantalla y en el chat. Con dos
    # copias de los mismos prints, el dia que una cambie el otro mensaje dice
    # otra cosa, y el del telefono es el que se lee.
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        codigo = _revisar()
    texto = buf.getvalue()
    print(texto, end="")
    if args.telegram:
        from src import telegram
        telegram.enviar("Instagram, cómo está:\n\n" + texto)
    return codigo


def _revisar() -> int:
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

    # La cuenta y su cupo. El cupo es la prueba de que la API de publicado
    # esta habilitada para esta cuenta: si no lo estuviera, esto falla.
    if cuenta.get("id"):
        print()
        ficha = instagram.ficha_de_la_cuenta(pagina, cuenta["id"])
        datos = ficha.get("cuenta") or {}
        if "error" in datos:
            print("La cuenta: no pude preguntar (%s)"
                  % (datos["error"] or {}).get("message"))
        else:
            print("La cuenta: @%s · %s seguidores · %s publicaciones"
                  % (datos.get("username") or "?",
                     datos.get("followers_count", "?"),
                     datos.get("media_count", "?")))
        cupo = (ficha.get("cupo") or {}).get("data")
        if cupo:
            c = cupo[0] or {}
            print("Cupo de publicado: %s de %s en 24 h"
                  % (c.get("quota_usage", "?"),
                     (c.get("config") or {}).get("quota_total", "?")))
            print("  (que conteste un numero es la prueba de que la API de "
                  "publicado esta habilitada para esta cuenta)")
        else:
            print("Cupo de publicado: NO pude saberlo. Es la senal mas fuerte "
                  "de que la API de publicado no esta habilitada en esta cuenta.")

    print()
    print("Para un REEL, Instagram pide ademas, y esto NO se puede preguntar "
          "por API:")
    for i, x in enumerate(REELS_PIDEN, 1):
        print("  %d. %s" % (i, x))

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
