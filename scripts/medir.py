#!/usr/bin/env python3
"""Que rindio cada cosa: por modelo, por tema, por eje y por hora.

    medir.py                 el informe
    medir.py --metrica comentarios

SOLO LEE. Pregunta los numeros a Facebook y a Instagram y los cruza con lo
que quedo guardado de cada post.

El texto lo arma `medir.informe`, que es el mismo que contesta el boton del
bot: el usuario lo lee desde el telefono, donde no hay terminal, y dos copias
de la misma cuenta es como se descubre tarde que una de las dos quedo vieja.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import config, frases, medir  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metrica", default="reacciones",
                    help="una de: %s" % ", ".join(medir.METRICAS))
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    pagina = config.cargar()
    ya = frases.publicadas()
    salidos = {k: v for k, v in ya.items() if v.get("post_id")}
    if not salidos:
        print("Todavia no salio ningun post.")
        return 1

    print(medir.informe(pagina, salidos, args.metrica))
    return 0


if __name__ == "__main__":
    sys.exit(main())
