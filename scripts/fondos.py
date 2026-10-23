#!/usr/bin/env python3
"""Baja clips de naturaleza para el fondo de los reels. Se corre UNA vez.

    fondos.py                      baja los que falten hasta llegar a 12
    fondos.py --cuantos 20
    fondos.py --termino "ocean waves"
    fondos.py --listar             dice los que ya hay, sin bajar nada

Los deja en data/fondos y de ahi los toma `scripts/reel.py --fondo data/fondos`.

NECESITA UNA CLAVE GRATUITA DE PEXELS, que no es una cuenta paga ni tiene
limite de descargas para esto: se saca en https://www.pexels.com/api/ con un
correo, y se guarda en el .env como PEXELS_API_KEY. Si preferis no sacarla, el
camino a mano es el mismo resultado: entrar a https://www.pexels.com/videos/,
buscar en ingles ("nature", "ocean", "forest"), filtrar por vertical y bajar
los que te gusten a esa carpeta.

Los videos de Pexels son de uso libre y no piden atribucion. Lo que no se
puede es revenderlos como si fueran propios, que no es lo que hace esto.

SOLO BAJA ARCHIVOS. No publica nada ni toca el banco de frases.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from src import video  # noqa: E402

API = "https://api.pexels.com/videos/search"

# En ingles porque es donde Pexels tiene el catalogo. La lista busca lo mismo
# que la pagina: calma, no espectaculo. Un dron sobre una cascada compite con
# el texto; una rama moviendose con el viento, no.
TERMINOS = ("calm nature", "ocean waves slow", "forest fog", "sunset clouds",
            "rain window", "grass field wind", "mountain mist", "river stones",
            "sky time lapse", "leaves sunlight")

CUANTOS = 12
# Mas chico que esto se ve pixelado al escalarlo a 1080 de ancho.
ANCHO_MINIMO = 900


def ya_hay(carpeta: Path) -> list:
    if not carpeta.is_dir():
        return []
    return sorted(x for x in carpeta.iterdir() if x.suffix.lower() == ".mp4")


def _mejor(archivos: list) -> dict:
    """El archivo vertical de mas calidad que no sea una barbaridad de peso."""
    verticales = [a for a in archivos
                  if (a.get("height") or 0) > (a.get("width") or 0)
                  and (a.get("width") or 0) >= ANCHO_MINIMO]
    if not verticales:
        return {}
    return sorted(verticales, key=lambda a: a.get("width") or 0)[0]


def buscar(clave: str, termino: str, cuantos: int) -> list:
    r = requests.get(API, headers={"Authorization": clave}, timeout=60,
                     params={"query": termino, "orientation": "portrait",
                             "size": "medium", "per_page": cuantos})
    if r.status_code == 401:
        raise SystemExit("Pexels no acepta la clave. Revisa PEXELS_API_KEY en el .env.")
    if r.status_code != 200:
        raise SystemExit("Pexels contesto %d: %s" % (r.status_code, r.text[:200]))
    return (r.json() or {}).get("videos") or []


def bajar(url: str, destino: Path) -> Path:
    """Escribe aparte y renombra: si se corta la descarga, lo que queda es un
    `.parcial` y no un mp4 de medio tamano que despues rompe el reel."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".parcial")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for trozo in r.iter_content(chunk_size=1 << 16):
                f.write(trozo)
    tmp.replace(destino)
    return destino


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cuantos", type=int, default=CUANTOS, help="cuantos tener en total")
    ap.add_argument("--termino", action="append", help="que buscar (se puede repetir)")
    ap.add_argument("--listar", action="store_true", help="decir los que hay y salir")
    ap.add_argument("--carpeta", default=str(video.FONDOS))
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    carpeta = Path(args.carpeta)
    tengo = ya_hay(carpeta)

    if args.listar:
        print("%d clips en %s" % (len(tengo), carpeta))
        for x in tengo:
            print("   %-28s %5.1f s" % (x.name, video.duracion(x)))
        return 0

    faltan = args.cuantos - len(tengo)
    if faltan <= 0:
        print("Ya hay %d clips en %s. Nada que bajar." % (len(tengo), carpeta))
        return 0

    clave = os.environ.get("PEXELS_API_KEY")
    if not clave:
        print("Falta PEXELS_API_KEY en el .env.")
        print()
        print("Se saca gratis en https://www.pexels.com/api/ con un correo.")
        print("O bajalos a mano de https://www.pexels.com/videos/ (buscar en")
        print("ingles, filtrar Vertical) y dejalos en %s" % carpeta)
        return 2

    terminos = args.termino or list(TERMINOS)
    print("Tengo %d, busco %d mas." % (len(tengo), faltan))
    vistos = {x.stem for x in tengo}
    bajados = 0
    for termino in terminos:
        if bajados >= faltan:
            break
        for v in buscar(clave, termino, 10):
            if bajados >= faltan:
                break
            nombre = "pexels-%s" % v.get("id")
            if nombre in vistos:
                continue
            archivo = _mejor(v.get("video_files") or [])
            if not archivo.get("link"):
                continue
            destino = carpeta / ("%s.mp4" % nombre)
            try:
                bajar(archivo["link"], destino)
            except requests.RequestException as e:
                print("   no pude bajar %s: %s" % (nombre, str(e)[:80]))
                continue
            vistos.add(nombre)
            bajados += 1
            print("   %-28s %4dx%-4d  %s" % (destino.name, archivo.get("width") or 0,
                                             archivo.get("height") or 0, termino))
    print()
    print("Ahora hay %d clips. Para usarlos:" % len(ya_hay(carpeta)))
    print("   scripts/reel.py --fondo %s --voz-mac" % carpeta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
