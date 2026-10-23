#!/usr/bin/env python3
"""El reel de una frase: vertical, el texto renglon a renglon sobre un fondo.

    reel.py                      la frase que toca, sin voz, sobre el papel
    reel.py --id aut-01          esa frase
    reel.py --fondo data/fondos  un clip de naturaleza (o una carpeta con varios)
    reel.py --voz mi-voz.m4a     tu voz grabada leyendo el texto
    reel.py --voz-mac            la voz de la Mac (`say`), renglon por renglon
    reel.py --ver                dice que haria, sin armar nada

NO PUBLICA NADA. Deja el mp4 en data/reels y lo subis vos, o lo mandas por
Telegram para mirarlo en el telefono.

La voz es lo unico que hay que decidir: tu voz grabada es gratis y es la que
mejor suena; `say` es gratis y suena sintetico; sin voz el reel sale mudo y se
lee igual. `--voz-mac` lee RENGLON POR RENGLON, asi que el subtitulo cae
exacto donde se lo dice; con un audio entero el tiempo se reparte proporcional
al largo de cada renglon, que es lo mas cerca que se puede estar sin tener los
tiempos palabra por palabra.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, frases, video  # noqa: E402

CLIPS = (".mp4", ".mov", ".m4v", ".webm", ".mkv")


def elegir_fondo(donde: str, semilla: str) -> list:
    """Los clips del fondo, en el orden en que se van a turnar.

    Varios y no uno: la referencia que mando el usuario va cortando entre
    clips cada pocos segundos, y es buena parte de por que no se hace larga.

    El orden sale de una semilla que es el id de la frase y no del azar: asi
    volver a armar el mismo reel da el mismo video -el que aprobaste es el que
    sale- y dos frases seguidas no arrancan con el mismo clip.
    """
    ruta = Path(donde)
    if ruta.is_file():
        return [ruta]
    if not ruta.is_dir():
        raise SystemExit("No encuentro %s" % ruta)
    clips = sorted(x for x in ruta.iterdir() if x.suffix.lower() in CLIPS)
    if not clips:
        raise SystemExit("En %s no hay ningun video (%s)" % (ruta, ", ".join(CLIPS)))
    random.Random(semilla).shuffle(clips)
    return clips


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", help="que frase")
    ap.add_argument("--fondo", help="un clip o una carpeta con clips")
    ap.add_argument("--voz", help="un audio tuyo leyendo el texto")
    ap.add_argument("--voz-mac", nargs="?", const=video.VOZ_MAC, default=None,
                    metavar="VOZ", help="usar `say` (Paulina, Jorge, Monica...)")
    ap.add_argument("--ver", action="store_true", help="decir que haria, sin armar")
    ap.add_argument("--carpeta", default=str(video.REELS))
    args = ap.parse_args(argv)

    pagina = config.cargar()
    temas = frases.leer()
    ya = frases.publicadas()
    frase = frases.por_id(temas, args.id) if args.id else frases.siguiente(temas, ya)
    if frase is None:
        print("No encuentro esa frase." if args.id else "Ya salieron todas.")
        return 2
    tema = frases.tema_de(temas, frase)
    carpeta = Path(args.carpeta)

    unidades = video.guion(frase)
    fondo = elegir_fondo(args.fondo, frase.id) if args.fondo else None
    cuerpo, _ = video.reparto(unidades)

    print("%s · capitulo %d, %s" % (frase.id, tema.capitulo, tema.titulo))
    print("%d renglones, cuerpo %d, fondo %s"
          % (len(unidades), cuerpo,
             ", ".join(x.name for x in fondo[:3]) if fondo else "papel de la marca"))
    for u in unidades:
        print("   %s" % u)

    if args.voz and args.voz_mac:
        print()
        print("Elegi una voz sola: --voz es tu grabacion y --voz-mac es la de la Mac.")
        return 2

    if args.ver:
        print()
        print("Duraria %.0f s." % video.duracion_del_guion(unidades))
        return 0

    marcas = None
    voz = Path(args.voz) if args.voz else None
    if args.voz_mac:
        print()
        print("Leyendo renglon por renglon con la voz %s..." % args.voz_mac)
        try:
            voz, duraciones = video.voz_por_unidades(
                unidades, carpeta / ("%s-voz" % frase.id), args.voz_mac)
        except video.VideoError as e:
            print(e)
            hay = video.voces_en_espanol()
            if hay:
                print("Voces en espanol instaladas: %s" % ", ".join(hay))
                print("Si la que pediste no esta: Ajustes del sistema -> "
                      "Accesibilidad -> Contenido hablado -> Voz del sistema.")
            else:
                print("`say` solo existe en Mac. Sin voz el reel sale igual, mudo.")
            return 1
        marcas = video.tiempos_exactos(duraciones)

    try:
        ruta = video.armar(frase, pagina, titulo=tema.titulo, fondo=fondo, voz=voz,
                           carpeta=carpeta, marcas=marcas)
    except video.VideoError as e:
        print(e)
        return 1
    print()
    print(ruta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
