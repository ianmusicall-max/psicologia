#!/usr/bin/env python3
"""Vuelve a escribir libro/borrador.md a partir del banco de frases.

El borrador se regenera entero: lo que se escriba a mano va en otros archivos
de libro/. Hay una prueba que exige que el borrador versionado esté al día
con el banco, así que después de tocar una frase hay que correr esto.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import frases, libro  # noqa: E402

BORRADOR = libro.BORRADOR


def main() -> int:
    temas = frases.leer()
    texto = libro.borrador(temas)
    BORRADOR.write_text(texto, encoding="utf-8")
    print("%s: %d capítulos, %d frases, %d palabras"
          % (BORRADOR.relative_to(ROOT), len(temas), len(frases.todas(temas)), len(texto.split())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
