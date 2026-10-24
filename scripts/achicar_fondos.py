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
    """Los clips de la carpeta, sin entrar en `originales`.

    Sin esa exclusion, una segunda corrida volveria a achicar los originales
    que la primera guardo, y cada pasada perderia un poco mas de imagen.
    """
    if not carpeta.is_dir():
        return []
    return sorted(x for x in carpeta.iterdir()
                  if x.is_file() and x.suffix.lower() in CLIPS)


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


# Donde van a parar los originales. NO se reemplazan: el usuario los quiere
# para subirlos a YouTube, y un original tirado no vuelve. Esta carpeta queda
# fuera del repositorio -son los archivos pesados- asi que viven en su Mac,
# que es donde los necesita.
ORIGINALES = "originales"

# Cuanto se guarda de cada clip. El reel cambia de clip cada `video.ESCENA`
# segundos -hoy 4- asi que de un clip de un minuto se ven cuatro. Guardar el
# resto es peso puro, y es de donde salen los archivos de 44 MB.
#
# Ocho y no cuatro para que un mismo clip pueda salir dos veces sin que se
# vea el mismo tramo.
SEGUNDOS = 8

# Con el recorte a 8 segundos, comprimir bien ya casi no cuesta tiempo: lo
# que habia hecho fallar a `slow` era un 4K de un minuto entero, no la
# compresion en si. `medium` y CRF 20 dan practicamente la misma imagen que
# el original a la medida del reel.
#
# 20 y no 24 porque el usuario pidio no perder calidad: la diferencia de peso
# entre uno y otro son un par de megas y el archivo igual queda diez veces
# mas chico que el original.
PRESET = "medium"
CALIDAD = 20


def achicar(ruta: Path) -> Path:
    """Lo deja en la medida del reel, corto y sin audio. Reemplaza el archivo.

    Escribe aparte y renombra: si se corta a la mitad, lo que queda es un
    archivo a medio hacer y no un clip roto que despues se lea como bueno.

    El temporal NO termina en `.mp4` a proposito: con `.parcial.mp4` el
    archivo a medio hacer seguia contando como clip -lo encuentra el mismo
    filtro de extensiones- y el reel lo habria usado de fondo. Paso de verdad.
    """
    tmp = ruta.with_suffix(".amedias")
    try:
        video._correr([
            video.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-t", str(SEGUNDOS),
            "-i", str(ruta),
            # Igual que al armar el reel: se agranda hasta cubrir y se recorta
            # el sobrante, asi no quedan franjas negras ni se deforma.
            "-vf", ("scale=%d:%d:force_original_aspect_ratio=increase,"
                    "crop=%d:%d" % (ANCHO, ALTO, ANCHO, ALTO)),
            "-c:v", "libx264", "-preset", PRESET, "-crf", str(CALIDAD),
            "-pix_fmt", "yuv420p",
            "-an",                  # el reel nunca usa el audio del clip
            str(tmp)], "achicar el clip", espera=600)
    except video.VideoError:
        # Un intento fallido no puede dejar basura: ese archivo a medio hacer
        # ocupa lugar y confunde la cuenta de la proxima corrida.
        if tmp.exists():
            tmp.unlink()
        raise
    # El original se GUARDA, no se pisa. Es lo que pidio el usuario -los
    # quiere para YouTube- y ademas es como se trabaja con video: la copia de
    # trabajo se puede rehacer, el original no.
    guardados = ruta.parent / ORIGINALES
    guardados.mkdir(parents=True, exist_ok=True)
    destino = ruta.with_suffix(".mp4")
    ruta.replace(guardados / ruta.name)
    tmp.replace(destino)
    return destino


def limpiar(carpeta: Path) -> int:
    """Borra lo que quedo de intentos anteriores, incluido el `.parcial.mp4`
    que dejaba la primera version y que contaba como clip."""
    cuantos = 0
    for x in list(carpeta.glob("*.amedias")) + list(carpeta.glob("*.parcial.mp4")):
        x.unlink()
        cuantos += 1
    return cuantos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver", action="store_true", help="no toca nada")
    ap.add_argument("--carpeta", default=str(CARPETA))
    args = ap.parse_args(argv)

    carpeta = Path(args.carpeta)
    sobras = limpiar(carpeta) if not args.ver else 0
    if sobras:
        print("Borre %d archivo(s) a medio hacer de una corrida anterior." % sobras)
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
        print("El reel es de %dx%d, cambia de clip cada %.0f s y no usa el "
              "audio." % (ANCHO, ALTO, video.ESCENA))
        print("Se guardan %d s de cada uno; el resto es peso que no se ve."
              % SEGUNDOS)
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
    print()
    print("Los originales quedaron en %s/, sin tocar." % (carpeta / ORIGINALES))
    print("Esa carpeta NO se sube al repositorio: es tu copia para YouTube.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
