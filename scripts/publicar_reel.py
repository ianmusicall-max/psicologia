#!/usr/bin/env python3
"""Publica un reel ya armado en el Instagram de la pagina.

    publicar_reel.py data/reels/due-01.mp4
    publicar_reel.py data/reels/due-01.mp4 --ver     dice que haria, sin publicar
    publicar_reel.py data/reels/due-01.mp4 --caption "Otro texto"

El caption sale solo de la frase que dio origen al reel -se deduce del nombre
del archivo- asi que lleva los mismos hashtags y la misma fuente que el post
de esa frase. Con `--caption` se escribe a mano.

ESTO PUBLICA. Es el unico script del proyecto que manda un video a Instagram,
y lo hace porque se lo pediste: el reel ya esta armado y lo miraste.

No toca `data/publicadas.json`. Un reel es contenido APARTE del post diario de
esa frase: si lo anotara ahi, la frase quedaria como publicada y su flyer no
saldria nunca.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import config, frases, instagram, video  # noqa: E402


def frase_del_archivo(temas, ruta: Path):
    """La frase que dio origen al reel, por el nombre del archivo.

    `data/reels/due-01.mp4` -> la frase `due-01`. Devuelve None si el nombre
    no es un id, que es lo normal si alguien renombro el archivo.
    """
    try:
        return frases.por_id(temas, ruta.stem)
    except Exception:                       # noqa: BLE001
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", help="el mp4 del reel")
    ap.add_argument("--caption", help="el texto; por defecto, el de la frase")
    ap.add_argument("--ver", action="store_true", help="no publica nada")
    ap.add_argument("--sin-feed", action="store_true",
                    help="dejarlo solo en reels, sin que aparezca en el perfil")
    args = ap.parse_args(argv)

    ruta = Path(args.video)
    if not ruta.is_file():
        print("No encuentro %s" % ruta)
        return 2

    load_dotenv(ROOT / ".env")
    pagina = config.cargar()
    temas = frases.leer()

    caption = args.caption
    frase = frase_del_archivo(temas, ruta)
    if not caption and frase is not None:
        caption = frases.caption(frase, frases.tema_de(temas, frase), pagina)
    if not caption:
        print("No pude deducir el caption del nombre del archivo (%s)." % ruta.stem)
        print("Pasalo con --caption.")
        return 2

    dura = video.duracion(ruta)
    pesa = ruta.stat().st_size
    print("%s" % ruta)
    print("  %.0f s, %.1f MB" % (dura, pesa / 1048576.0))
    print()
    print("Caption:")
    for linea in caption.splitlines():
        print("   %s" % linea)
    print()

    # Se comprueba ANTES de subir. Instagram rechaza el contenedor despues de
    # recibir el archivo entero, y el error no dice que el problema es el
    # largo: con un reel de 2 MB da igual, pero el aviso claro vale mas que
    # los segundos que ahorra.
    if dura > video.TOPE_SEGUNDOS:
        print("Dura %.0f s y el tope de Instagram son %d. No lo publico."
              % (dura, video.TOPE_SEGUNDOS))
        return 1
    if pesa > instagram.PESO_MAXIMO:
        print("Pesa demasiado para la API de Instagram. No lo publico.")
        return 1

    if args.ver:
        print("Con --ver no publique nada.")
        return 0

    try:
        ident = instagram.publicar_reel(pagina, caption, ruta,
                                        compartir=not args.sin_feed)
    except instagram.InstagramError as e:
        print("No pude publicarlo: %s" % e)
        return 1
    print("Publicado. id %s" % ident)
    print("No anote nada en data/publicadas.json: el reel es contenido aparte")
    print("del post de esa frase, que sigue pendiente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
