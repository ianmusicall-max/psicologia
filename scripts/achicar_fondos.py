#!/usr/bin/env python3
"""Deja los clips de fondo en la medida del reel, para que no pesen de mas.

    achicar_fondos.py --ver        dice cuanto pesan y cuanto duran
    achicar_fondos.py --repetidos  dice si dos son el mismo video
    achicar_fondos.py --recortar   deja en 6 s los que pasan, SIN recomprimir
    achicar_fondos.py              los achica entero (reemplaza los archivos)

`--recortar` es lo que se corre cuando entra un clip nuevo, y es la regla que
puso el usuario el 2026-10-26: mas de 6 segundos se recorta a 6, y 6 o menos
no se toca. Copia los paquetes tal cual (`-c copy`), asi que no pierde imagen
y tarda un segundo.

Por que hace falta: los clips de Pexels vienen en 4K (2160x3840) y el reel es
1080x1920. Esa foto de mas no se ve en ningun lado -ffmpeg la achica igual al
armar el video- pero el archivo pesa cuatro veces.

Y el peso importa mas de lo que parece: estos clips viven en el repositorio,
asi que CADA corrida de GitHub se los baja. El turno que publica corre cuatro
veces por hora; con medio giga de clips eso es media hora de descarga por dia
para algo que ese turno ni usa. (El 2026-10-26 el recorte a 6 s dejo la
carpeta en 263 MB. Esto achica mas todavia -en un clip 4K de 17 s, de 22,5 MB
a 2,5- porque ademas reencoda a la medida del reel y saca el audio.)

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


def huella(ruta: Path):
    """Identifica el clip por los CUADROS que el reel usa, no por el archivo.

    El md5 del archivo entero dejo de servir el dia que los clips se recortan
    al entrar (2026-10-26): si el usuario vuelve a mandar un clip que ya esta
    en la carpeta, el de la carpeta mide 6 s y el que llega mide 15, asi que
    los bytes no coinciden y el repetido entra como nuevo. Paso ese mismo dia
    con `ladera-bruma-anochecer`.

    Esto compara los `video.ESCENA` segundos que el reel muestra de verdad, con
    `framemd5`, que es la huella de los cuadros decodificados. Un recorte sin
    recomprimir no la cambia, y es justamente lo que hace falta.

    Devuelve None si no se puede leer: un archivo ilegible no es un repetido.
    """
    import hashlib
    import subprocess
    try:
        r = subprocess.run(
            [video.ffmpeg(), "-v", "error", "-i", str(ruta),
             "-map", "0:v:0", "-t", str(video.ESCENA), "-an",
             "-f", "framemd5", "-"],
            capture_output=True, text=True)
    except OSError:
        return None
    cuadros = [l for l in (r.stdout or "").splitlines() if l and not l.startswith("#")]
    if not cuadros:
        return None
    return hashlib.md5("\n".join(cuadros).encode()).hexdigest()


def repetidos(carpeta: Path):
    """Los clips de la carpeta que son el mismo video, agrupados por huella."""
    por_huella = {}
    for c in clips_de(carpeta):
        h = huella(c)
        if h:
            por_huella.setdefault(h, []).append(c.name)
    return [sorted(v) for v in por_huella.values() if len(v) > 1]


def ficha(ruta: Path):
    """Ancho, alto y segundos del clip en UNA sola llamada, o None.

    `ffmpeg -i` sin salida termina con error y escribe la ficha en stderr: eso
    es lo normal, no una falla, asi que no se mira el codigo de salida.

    Una llamada y no dos porque el listado necesita las dos cosas de cada
    clip, y son 54.

    Aca se intento antes leer la duracion del `mvhd` del mp4, sin ffmpeg, para
    que la prueba que recorre la carpeta no pagara 54 procesos. NO SIRVE y
    conviene que quede escrito: los cinco clips que traen el `moov` adelante
    declaran `duration` 0 en esa cabecera -la duracion de verdad vive en cada
    pista- y el lector devolvia 0,000 para `espejo-luces-noche`, que dura
    2,98. Un guardian que mide mal es peor que no tenerlo.
    """
    import re
    import subprocess
    try:
        r = subprocess.run([video.ffmpeg(), "-hide_banner", "-i", str(ruta)],
                           capture_output=True, text=True)
    except OSError:
        return None
    salida = r.stderr or ""
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", salida, re.S)
    d = re.search(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)", salida)
    if not m and not d:
        return None
    return (
        (int(m.group(1)), int(m.group(2))) if m else None,
        (int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)))
        if d else None,
    )


def medida(ruta: Path):
    """Ancho y alto del clip, o None si no se puede leer."""
    f = ficha(ruta)
    return f[0] if f else None


def segundos(ruta: Path):
    """Cuanto dura el clip, o None si no se puede leer."""
    f = ficha(ruta)
    return f[1] if f else None


# Donde van a parar los originales. NO se reemplazan: el usuario los quiere
# para subirlos a YouTube, y un original tirado no vuelve. Esta carpeta queda
# fuera del repositorio -son los archivos pesados- asi que viven en su Mac,
# que es donde los necesita.
ORIGINALES = "originales"

# EL TOPE DE LARGO, y es la regla que puso el usuario el 2026-10-26:
#
#     mas de 6 segundos  -> se recorta a 6
#     6 o menos          -> NO SE TOCA, queda tal cual
#
# Primero pidio 6, despues 8, y al final 6. Lo que quedo firme en las tres
# vueltas es la segunda linea: un clip que ya entra no se toca.
#
# Las dos mitades importan igual. El reel cambia de clip cada `video.ESCENA`
# segundos -hoy 4- asi que de un clip de un minuto se ven cuatro y el resto es
# peso puro: de ahi salian los archivos de 44 MB. Pero un clip que ya entra en
# el tope no gana nada con que lo toquemos, y volver a escribirlo solo puede
# empeorarlo: es un archivo mas en la historia de git para el mismo video.
#
# Por eso `recortar` no es un "recortar todo a 8": compara primero y devuelve
# None cuando no hay nada que hacer. Hay una prueba que exige que un clip
# corto quede BYTE POR BYTE igual.
#
# Antes el comentario de aca decia "ocho y no cuatro para que un mismo clip
# pueda salir dos veces sin que se vea el mismo tramo", y eso el reel NO lo
# hace: cada tramo es una entrada propia con `trim=duration` desde el
# principio y sin `-ss` (`video.comando`), asi que un clip repetido muestra
# los mismos cuatro segundos las dos veces. Los dos de margen son para el dia
# que `video.ESCENA` suba, no para variar el tramo.
SEGUNDOS = 6

# El sobrante del ultimo paquete. `-t 6 -c copy` corta por paquete y no por
# cuadro, asi que el archivo puede terminar unos milisegundos despues del
# segundo 6 -el mas pasado de la carpeta esta en 6,13-. Sin esta tolerancia,
# los 49 clips que ya se recortaron volverian a
# recortarse en cada corrida -y cada pasada seria otro archivo en git-.
COLA = 0.5

def recortar(ruta: Path):
    """Deja el clip en `SEGUNDOS` SIN recomprimir. Devuelve None si no hacia falta.

    Esta es la regla del 2026-10-26 y es lo que se corre cuando entra un clip
    nuevo. `-c copy` copia los paquetes tal cual: los cuadros que el reel usa
    salen bit por bit iguales a los del original y tarda un segundo, contra el
    minuto y la perdida de imagen que cuesta `achicar`.

    Un clip que ya entra en el tope se devuelve con None y NO se abre siquiera:
    "los que duran menos de 8 no los toques", y volver a escribirlo seria otro
    archivo en la historia de git para el mismo video.

    Escribe aparte y renombra, y el temporal no termina en `.mp4` a proposito:
    con `.parcial.mp4` el archivo a medio hacer seguia contando como clip y el
    reel lo habria usado de fondo. Paso de verdad.
    """
    dura = segundos(ruta)
    if dura is None:
        raise video.VideoError("no pude leer cuanto dura %s" % ruta.name)
    if dura <= SEGUNDOS + COLA:
        return None
    tmp = ruta.with_suffix(".amedias")
    try:
        video._correr([
            video.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(ruta), "-t", str(SEGUNDOS), "-c", "copy",
            # `-f mp4` porque el temporal no termina en .mp4 y ffmpeg deduce
            # el formato de la extension: sin esto no arranca siquiera.
            "-f", "mp4", str(tmp)], "recortar el clip", espera=300)
    except video.VideoError:
        if tmp.exists():
            tmp.unlink()
        raise
    destino = ruta.with_suffix(".mp4")
    tmp.replace(destino)
    return destino


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
            # Lo mismo que en `recortar`: el temporal no termina en .mp4.
            # Esto FALTABA desde que se escribio la funcion y nadie lo vio,
            # porque su prueba reemplaza `video._correr` por un doble y
            # ffmpeg nunca llegaba a correr. El script entero habria fallado
            # en el primer clip.
            "-f", "mp4", str(tmp)], "achicar el clip", espera=600)
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
    ap.add_argument("--repetidos", action="store_true",
                    help="dice si dos clips de la carpeta son el mismo video")
    ap.add_argument("--recortar", action="store_true",
                    help="solo recorta a %d s, sin recomprimir (la regla de "
                         "los clips nuevos)" % SEGUNDOS)
    ap.add_argument("--carpeta", default=str(CARPETA))
    args = ap.parse_args(argv)

    carpeta = Path(args.carpeta)
    if args.repetidos:
        iguales = repetidos(carpeta)
        for grupo in iguales:
            print("  el mismo video: %s" % ", ".join(grupo))
        print("%d clip(s) repetido(s) en %s" % (len(iguales), carpeta)
              if iguales else "Ninguno repetido en %s." % carpeta)
        return 1 if iguales else 0

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
        f = ficha(c) or (None, None)
        tam, dura = f
        grande = tam and (tam[0] > ANCHO or tam[1] > ALTO)
        print("  %-42s %7.1f MB  %6s  %s%s"
              % (c.name[:42], c.stat().st_size / 1048576.0,
                 ("%.1f s" % dura) if dura else "? s",
                 ("%dx%d" % tam) if tam else "?",
                 "  <- mas grande que el reel" if grande else ""))
    if args.ver:
        print()
        print("El reel es de %dx%d, cambia de clip cada %.0f s y no usa el "
              "audio." % (ANCHO, ALTO, video.ESCENA))
        print("Nada pasa de %d s: lo que dura mas se recorta y lo que dura "
              "menos queda tal cual." % SEGUNDOS)
        print("Para recortar sin recomprimir: --recortar")
        print("Con --ver no toque nada.")
        return 0

    if args.recortar:
        print()
        tocados = 0
        for c in clips:
            try:
                hecho = recortar(c)
            except video.VideoError as e:
                print("  %-42s no pude: %s" % (c.name[:42], e))
                continue
            if hecho is None:
                print("  %-42s ya entra en %d s, no la toque"
                      % (c.name[:42], SEGUNDOS))
            else:
                tocados += 1
                print("  %-42s recortada a %d s" % (c.name[:42], SEGUNDOS))
        despues = pesan(clips_de(carpeta))
        print()
        print("Recorte %d de %d clips. De %.0f MB a %.0f MB."
              % (tocados, len(clips), antes, despues))
        print("Sin recomprimir: los %.0f s que usa el reel quedaron intactos."
              % video.ESCENA)
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
