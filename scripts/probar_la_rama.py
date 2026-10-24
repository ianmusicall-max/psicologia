#!/usr/bin/env python3
"""Prueba el hospedaje del reel SIN publicar nada en ninguna red.

    probar_la_rama.py

Deja el mp4 que haya en `data/reels/ultimo.mp4` en la rama publica -la que se
reemplaza en cada turno- y comprueba que las direcciones contesten de verdad.

Existe porque es la unica forma de probar ese camino sin gastar un reel: en el
turno de todos los dias, el archivo se empuja y Instagram se lo baja, y si
algo de eso falla el reel se pierde. Aca se empuja y se mira, y nada sale a
Facebook, a Instagram ni a YouTube.

Hace falta correrlo donde el token de GitHub exista -la pestania Actions- y
donde el CDN se alcance. Desde la Mac dice que no puede y no toca nada.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import reel_del_dia as reel  # noqa: E402

VIDEO = ROOT / "data" / "reels" / "ultimo.mp4"


def main(argv=None) -> int:
    if not VIDEO.is_file():
        print("No hay ningun reel en %s para probar." % VIDEO)
        return 2

    print("Empujando %s a la rama «%s»..." % (VIDEO.name, reel.RAMA_PUBLICA))
    sha = reel.subir_a_la_rama(VIDEO)
    if not sha:
        print("No pude empujar la rama. Sin GITHUB_TOKEN y GITHUB_REPOSITORY "
              "esto no se puede probar: hay que correrlo desde Actions.")
        return 1
    print("Quedo en el commit %s" % sha[:12])
    print()

    urls = reel.direcciones_de(sha, reel.NOMBRE_PUBLICO)
    if not urls:
        print("No pude armar ninguna direccion: falta GITHUB_REPOSITORY.")
        return 1
    andan = []
    for u in urls:
        # Un solo intento por direccion y corto: aca se quiere SABER cual
        # anda, no esperar a que ande. El turno si espera, que es su trabajo.
        bien = reel.anda(u, intentos=3, espera=4)
        print("  %s  %s" % ("ANDA " if bien else "no   ", u))
        if bien:
            andan.append(u)
    print()
    if not andan:
        print("Ninguna direccion contesta, asi que el reel de manana caeria al "
              "camino de subir los bytes, que es el que Instagram rechaza.")
        return 1
    print("Instagram se bajaria el reel de: %s" % andan[0])
    print("El camino del reel diario esta en condiciones.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
