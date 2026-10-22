#!/usr/bin/env python3
"""Dibuja el banco entero en data/flyers, para mirarlo antes de que salga.

    dibujar_todas.py            todas, a tamaño de publicación (2160x2700)
    dibujar_todas.py --tema duelo --chico   solo un tema, a 1080x1350
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, diseno, frases  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tema", help="solo este tema")
    ap.add_argument("--chico", action="store_true", help="a 1080x1350 en vez del doble")
    ap.add_argument("--carpeta", default=str(diseno.FLYERS))
    args = ap.parse_args(argv)
    pagina = config.cargar()
    n = 0
    for tema in frases.leer():
        if args.tema and tema.tema != args.tema:
            continue
        for frase in tema.frases:
            ruta = diseno.dibujar(frase, tema, pagina, Path(args.carpeta), escala=1 if args.chico else 2)
            print(ruta)
            n += 1
    print("%d flyers en %s" % (n, args.carpeta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
