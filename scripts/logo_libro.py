#!/usr/bin/env python3
"""El logo del libro: la figura que cae, sola y sin fondo.

Es LA MISMA que dibuja la tapa -`libro_pdf.cayendo`- y no una copia: el dia
que cambie la postura, el logo cambia con ella. Un logo que se parece a la
tapa pero no es el mismo dibujo es el peor caso, porque nadie lo nota hasta
verlos uno al lado del otro.

Deja tres archivos en `libro/salida/`:

  -logo.pdf          vector, sin fondo. El que sirve para imprimir o agrandar.
  -logo.png          sin fondo, para poner sobre cualquier color.
  -logo-blanco.png   sobre blanco, para donde la transparencia sale negra
                     (WhatsApp, algunas fotos de perfil).

Los PNG salen con `pdftocairo` y `pdftoppm` (poppler). Si no estan, el PDF se
escribe igual y el script lo dice: el vector es el original y de el salen
todos los demas tamanos.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.lib.colors import HexColor  # noqa: E402
from reportlab.pdfgen import canvas as cv  # noqa: E402

from scripts.libro_pdf import ROJO, SALIDA, cayendo, caja_de_cayendo  # noqa: E402
from src import libro  # noqa: E402

# El lado del dibujo en el PDF. Es vector, asi que el numero no limita nada:
# decide con que medida se abre en un programa de diseno, no la calidad.
LADO = 120.0
# El aire alrededor, en partes del lado. Sin nada de aire, cualquier programa
# que recorte un pelo se come una punta del trazo.
AIRE = 0.06


def armar_logo(destino: Path, color=ROJO, lado: float = LADO) -> Path:
    """El PDF, del tamano justo del dibujo mas el aire. SIN fondo.

    Sin rectangulo de fondo a proposito: un PDF sin pintar es transparente, y
    un logo con el fondo blanco pegado encima deja un recuadro visible sobre
    cualquier color que no sea blanco.
    """
    x0, y0, x1, y1 = caja_de_cayendo(lado)
    aire = lado * AIRE
    ancho, alto = (x1 - x0) + 2 * aire, (y1 - y0) + 2 * aire
    c = cv.Canvas(str(destino), pagesize=(ancho, alto))
    cayendo(c, aire - x0, aire - y0, lado, color)
    c.showPage()
    c.save()
    return destino


def _rasterizar(pdf: Path, destino: Path, ancho: int, transparente: bool):
    """Un PNG del PDF. Devuelve el camino, o None si no hay con que."""
    orden = (["pdftocairo", "-png", "-transp", "-singlefile"] if transparente
             else ["pdftoppm", "-png", "-singlefile"])
    # El -r no sirve aca: el PDF mide lo que mide el dibujo, asi que la unica
    # forma de pedir un ancho concreto es decirselo.
    orden += ["-scale-to-x", str(ancho), "-scale-to-y", "-1",
              str(pdf), str(destino.with_suffix(""))]
    try:
        subprocess.run(orden, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return destino if destino.exists() else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--color", default=None,
                    help="el color del trazo en hexadecimal (#9E2B25 por "
                         "defecto, el acento del libro)")
    ap.add_argument("--ancho", type=int, default=2000,
                    help="el ancho de los PNG en pixeles (2000)")
    args = ap.parse_args(argv)

    color = HexColor(args.color) if args.color else ROJO
    SALIDA.mkdir(parents=True, exist_ok=True)
    base = unicodedata.normalize("NFKD", libro.TITULO.lower())
    base = "".join(ch for ch in base if not unicodedata.combining(ch))
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-") + "-logo"

    pdf = armar_logo(SALIDA / (base + ".pdf"), color)
    print("Logo vector:  %s" % pdf.name)

    faltan = []
    for sufijo, transparente, para in ((".png", True, "sin fondo"),
                                       ("-blanco.png", False, "sobre blanco")):
        png = _rasterizar(pdf, SALIDA / (base + sufijo), args.ancho,
                          transparente)
        if png:
            print("Logo %-12s %s (%d px de ancho)"
                  % (para + ":", png.name, args.ancho))
        else:
            faltan.append(sufijo)
    if faltan:
        print("Sin los PNG: hace falta poppler (pdftocairo y pdftoppm). En la"
              " Mac: brew install poppler. El PDF ya esta y de el sale"
              " cualquier tamano.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
