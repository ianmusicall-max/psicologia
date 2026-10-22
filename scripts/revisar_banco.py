#!/usr/bin/env python3
"""Revisa el banco entero contra la línea editorial y dice cómo va.

Solo lee. Sale con 1 si hay algo que impediría publicar. Es lo que conviene
correr después de escribir frases nuevas, antes de hacer commit.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import frases  # noqa: E402


def main() -> int:
    temas = frases.leer()
    ya = frases.publicadas()
    print("%-14s %-38s %6s %10s %7s" % ("tema", "capítulo", "frases", "publicadas", "quedan"))
    total = 0
    for t in temas:
        salieron = sum(1 for f in t.frases if f.id in ya)
        total += len(t.frases)
        print("%-14s %-38s %6d %10d %7d" % (t.tema, t.titulo[:38], len(t.frases), salieron, len(t.frases) - salieron))
    print("%-14s %-38s %6d %10d %7d" % ("total", "", total, len(ya), total - len(ya)))
    print()
    problemas = frases.revisar(temas)
    if not problemas:
        print("Sin problemas: las %d frases pasan la línea editorial." % total)
        return 0
    print("%d problemas:" % len(problemas))
    for p in problemas:
        print("  -", p)
    return 1


if __name__ == "__main__":
    sys.exit(main())
