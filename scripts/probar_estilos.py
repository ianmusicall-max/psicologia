#!/usr/bin/env python3
"""Dibuja la misma frase en los cinco estilos, para elegir mirando.

    probar_estilos.py                 usa la frase que toca
    probar_estilos.py --id rup-03     usa esa
    probar_estilos.py --todas         cada estilo con una frase distinta

Deja los archivos en data/estilos. SOLO DIBUJA: no publica ni anota nada.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, diseno, frases  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", help="qué frase dibujar")
    ap.add_argument("--todas", action="store_true", help="una frase distinta por estilo")
    ap.add_argument("--carpeta", default=str(ROOT / "data" / "estilos"))
    args = ap.parse_args(argv)

    pagina = config.cargar()
    temas = frases.leer()
    ya = frases.publicadas()
    carpeta = Path(args.carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)

    estilos = sorted(diseno.ESTILOS)
    if args.todas:
        pendientes = [f for f in frases.todas(temas) if f.id not in ya][:len(estilos)]
        elegidas = pendientes or frases.todas(temas)[:len(estilos)]
    else:
        una = frases.por_id(temas, args.id) if args.id else frases.siguiente(temas, ya)
        if una is None:
            print("No encuentro esa frase.")
            return 2
        elegidas = [una] * len(estilos)

    for estilo, frase in zip(estilos, elegidas):
        tema = frases.tema_de(temas, frase)
        img = diseno.render(frase, tema, pagina, escala=1, estilo=estilo)
        ruta = carpeta / ("%s-%s.jpg" % (estilo, frase.id))
        diseno.guardar(img, ruta)
        print(ruta)
    print()
    print("El que quieras queda fijo con una linea en config/pagina.yaml: estilo: <nombre>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
