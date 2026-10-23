#!/usr/bin/env python3
"""Deja los clips de fondo en la medida del reel, para que no pesen de mas.

    achicar_fondos.py --ver     dice cuanto pesan y cuanto quedarian
    achicar_fondos.py           los achica (reemplaza los archivos)

Por que hace falta: los clips de Pexels vienen en 4K (2160x3840) y el reel es
1080x1920. Esa foto de mas no se ve en ningun lado -ffmpeg la achica igual al
armar el video- pero el archivo pesa cuatro veces.

Y el peso importa mas de lo que parece: estos clips viven en el repositorio,
asi que CADA corrida de GitHub se los baja. El turno que publica corre cuatro
veces por hora; con medio giga de clips eso es media hora de descarga por dia
para algo que ese turno ni usa.

Ademas:

- **Se les saca el audio.** El reel arma su propia pista -voz y musica- y
  nunca usa la de los clips: la cadena de ffmpeg solo toma `[N:v]`. Es peso
  que no se oye.
- GitHub RECHAZA un archivo de mas de 100 MB. Un clip 4K largo llega.

SOLO TOCA ARCHIVOS DE VIDEO. No publica nada ni toca el banco de frases.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import video  # noqa: E402

CLIPS = (".mp4", ".mov", ".m4v", ".webm", ".mkv")
CARPETA = ROOT / "data" / "fondos"

# La medida del reel. Mas que esto no se ve.
ANCHO, ALTO = video.ANCHO, video.ALTO


def pesan(archivos) -> float:
    return sum(a.stat().st_size for a in archivos) / 1048576.0


def clips_de(carpeta: Path):
    if not carpeta.is_dir():
        return []
    return sorted(x for x in carpeta.iterdir() if x.suffix.lower() in CLIPS)


def medida(ruta: Path):
    """Ancho y alto del clip, o None si no se puede leer.

    `ffmpeg -i` sin salida termina con error y escribe la ficha en stderr:
    eso es lo normal, no una falla, asi que no se mira el codigo de salida.
    """
    import re
    import subprocess
    try:
        r = subprocess.run([video.ffmpeg(), "-hide_banner", "-i", str(ruta)],
                           capture_output=True, text=True)
    except OSError:
        return None
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", r.stderr or "", re.S)
    return (int(m.group(1)), int(m.group(2))) if m else None


def achicar(ruta: Path) -> Path:
    """Lo deja en la medida del reel y sin audio. Reemplaza el archivo.

    Escribe aparte y renombra: si se corta a la mitad, lo que queda es un
    `.parcial` y no un clip roto que despues se lea como bueno.
    """
    tmp = ruta.with_suffix(".parcial.mp4")
    video._correr([
        video.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(ruta),
        # Igual que al armar el reel: se agranda hasta cubrir y se recorta el
        # sobrante, asi no quedan franjas negras ni se deforma.
        "-vf", ("scale=%d:%d:force_original_aspect_ratio=increase,"
                "crop=%d:%d" % (ANCHO, ALTO, ANCHO, ALTO)),
        "-c:v", "libx264", "-preset", "slow", "-crf", "24",
        "-pix_fmt", "yuv420p",
        "-an",                      # el reel nunca usa el audio del clip
        str(tmp)], "achicar el clip")
    destino = ruta.with_suffix(".mp4")
    tmp.replace(destino)
    if ruta != destino and ruta.exists():
        ruta.unlink()
    return destino


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver", action="store_true", help="no toca nada")
    ap.add_argument("--carpeta", default=str(CARPETA))
    args = ap.parse_args(argv)

    carpeta = Path(args.carpeta)
    clips = clips_de(carpeta)
    if not clips:
        print("No hay ningun video en %s" % carpeta)
        return 1

    antes = pesan(clips)
    print("%d clips, %.0f MB en total." % (len(clips), antes))
    print()
    for c in clips:
        tam = medida(c)
        grande = tam and (tam[0] > ANCHO or tam[1] > ALTO)
        print("  %-42s %7.1f MB  %s%s"
              % (c.name[:42], c.stat().st_size / 1048576.0,
                 ("%dx%d" % tam) if tam else "?",
                 "  <- mas grande que el reel" if grande else ""))
    if args.ver:
        print()
        print("El reel es de %dx%d y no usa el audio de los clips." % (ANCHO, ALTO))
        print("Con --ver no toque nada.")
        return 0

    print()
    for c in clips:
        print("Achicando %s..." % c.name)
        try:
            achicar(c)
        except video.VideoError as e:
            # Un clip que falla no se lleva los demas.
            print("  no pude: %s" % e)
    despues = pesan(clips_de(carpeta))
    print()
    print("De %.0f MB a %.0f MB (%.0f%% menos)."
          % (antes, despues, 100 * (1 - despues / antes) if antes else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
