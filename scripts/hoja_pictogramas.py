#!/usr/bin/env python3
"""Los veintinueve pictogramas en UNA hoja, para mirarlos juntos.

Existe por un motivo concreto: dos capitulos no pueden compartir el dibujo, y
eso no se ve dibujandolos de a uno. Separados se ven bien. En la primera
tanda, autoestima y soledad eran el mismo circulo con un punto, y habitos y
duelo el mismo anillo abierto; se noto recien al ponerlos en una grilla.

    python3 scripts/hoja_pictogramas.py             -> libro/salida/pictogramas.pdf

No toca el libro. Es para mirar.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.lib.colors import HexColor  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.pdfgen import canvas as cv  # noqa: E402

from src import frases, pictogramas  # noqa: E402

SALIDA = ROOT / "libro" / "salida"
SERIF = "/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf"
COLUMNAS = 5


def main(argv=None) -> int:
    destino = Path(argv[0]) if argv else SALIDA / "pictogramas.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        pdfmetrics.registerFont(TTFont("S", SERIF))
        fuente = "S"
    except Exception:                                     # noqa: BLE001
        fuente = "Helvetica"

    temas = {t.capitulo: t.titulo for t in frases.leer()}
    filas = (len(pictogramas.DIBUJOS) + COLUMNAS - 1) // COLUMNAS
    ancho = 20 * mm + COLUMNAS * 38 * mm
    alto = 34 * mm + filas * 38 * mm
    c = cv.Canvas(str(destino), pagesize=(ancho, alto))
    c.setFont(fuente, 11)
    c.setFillGray(0.2)
    c.drawCentredString(ancho / 2, alto - 15 * mm,
                        "Los pictogramas del libro · un trazo, un tamaño")
    for i, numero in enumerate(sorted(pictogramas.DIBUJOS)):
        col, fila = i % COLUMNAS, i // COLUMNAS
        x = 29 * mm + col * 38 * mm
        y = alto - 40 * mm - fila * 38 * mm
        pictogramas.dibujar(c, numero, x, y, 11 * mm, HexColor("#1F2933"))
        c.setFillGray(0.45)
        c.setFont(fuente, 6.5)
        nombre = temas.get(numero, "")
        c.drawCentredString(x, y - 13 * mm, "%d · %s" % (numero, nombre[:26]))
    c.showPage()
    c.save()
    print("%d pictogramas en %s" % (len(pictogramas.DIBUJOS), destino))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
