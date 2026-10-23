#!/usr/bin/env python3
"""El calendario de la prueba: cuantos posts cada dia, a que hora y con que diseno.

    parrilla.py              desde el primer dia publicado, o desde hoy
    parrilla.py --desde 2026-10-24

SOLO LEE. Sirve para ver la rampa entera antes de encenderla, y para saber
que dia se agota el banco de frases.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, diseno, frases, parrilla  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--desde", help="el primer dia de la prueba (YYYY-MM-DD)")
    args = ap.parse_args(argv)

    pagina = config.cargar()
    temas = frases.leer()
    ya = frases.publicadas()
    quedan = len(frases.todas(temas)) - len(ya)
    desde = (date.fromisoformat(args.desde) if args.desde
             else frases.primer_dia(ya) or date.today())

    print("Quedan %d frases sin publicar. La prueba se cuenta desde el %s."
          % (quedan, desde.isoformat()))
    print()
    filas = parrilla.calendario(pagina, desde, quedan)
    for f in filas:
        detalle = "  ".join(
            "%02dh %s" % (h, diseno.estilo_de(pagina, f["dia"], h, f["horas"]))
            for h in f["horas"])
        print("dia %-3d %s  %d posts   %s" % (f["numero"], f["dia"].isoformat(),
                                              f["posts"], detalle))
    if filas:
        ultimo = filas[-1]
        print()
        print("El banco alcanza hasta el %s (dia %d). Despues hay que escribir mas."
              % (ultimo["dia"].isoformat(), ultimo["numero"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
