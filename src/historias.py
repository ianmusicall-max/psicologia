"""Las historias de la pagina: el flyer de cada frase y el reel del dia.

Lo pidio el usuario el 2026-10-26: "sube las frases y los videos a las
historias de facebook". No cuesta nada -el flyer y el reel ya estan hechos y
aprobados, la version vertical se arma aca, y Facebook no cobra- y es la unica
superficie de la pagina que hoy no se usa.

Facebook no deja poner un sticker de enlace desde la API, asi que la historia
no lleva link al post: es un aviso de que hay algo nuevo.

**Una historia que falla nunca tumba el post ni el reel.** Lo que ya salio
salio; la historia es el extra. Por eso `del_flyer` y `del_reel` no levantan
ningun error: anotan y siguen.

EL REEL NO ENTRA DE UNA. Facebook corta una historia de video en 60 segundos y
los reels de esta pagina duran entre 76 y 85 -el usuario los pidio de mas de
un minuto el 2026-10-25-.

**Va UNA tarjeta y el reel cortado, y lo eligio el usuario**: "no puedes subir
la historia a medida que demanda la historia, no importa que se corte el reel".
Se le habia hecho primero de dos tarjetas justamente para no perder el
**mensaje final** -que es lo que se les agrego a los siete textos a pedido suyo,
"acaba muy seco sin ningun mensaje"- y con eso a la vista eligio una sola.

Lo que SI se conserva es que el corte **cae donde termina un renglon** y no a
mitad de palabra: eso no cuesta nada. Los renglones duran unos 2,5 s cada uno
-33 en un reel de 83 s, medido-, asi que cortar en el ultimo que entra pierde
menos de 3 segundos mas que cortar en el tope exacto, y se oye como un final y
no como un error.

`PARTIR_EL_REEL = True` vuelve a las dos tarjetas sin tocar nada mas: el camino
esta entero y probado.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import requests
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .config import Pagina

GRAPH = "https://graph.facebook.com/v21.0"
ANCHO, ALTO = 1080, 1920

# El fondo de la historia del flyer: el mismo flyer agrandado, desenfocado y
# oscurecido. Sin esto quedan dos franjas lisas arriba y abajo, porque el
# flyer es 1080x1350 y la historia 1080x1920.
DESENFOQUE = 38
BRILLO_FONDO = 0.55

# Lo que Facebook acepta en una historia de video. 59,5 y no 60 porque el
# contenedor redondea para arriba y un reel de 60,02 se rechaza entero.
VIDEO_MAXIMO = 59.5
# Mas corto que esto no es una tarjeta, es un parpadeo.
TRAMO_MINIMO = 8.0

# Si el reel se parte en varias tarjetas o se corta en una.
#
# FALSE, y lo eligio el usuario con el precio a la vista: la historia se ajusta
# a lo que la historia aguanta y el reel se corta. Lo que se pierde son los
# ultimos 20 a 25 segundos, donde vive el mensaje final.
#
# True reparte el reel entero en tarjetas parejas que se ven una detras de la
# otra. El camino esta entero y probado, asi que volver es cambiar este numero.
PARTIR_EL_REEL = False

# Los dos permisos que usa este camino. `pages_show_list` NO esta a proposito:
# es el que sirve para CONSEGUIR el token de la pagina, asi que si algo de
# esto llego a hablar con Meta ya estaba, y nombrarlo mandaria a buscar un
# permiso que no es el que falta.
PERMISOS = ("pages_manage_posts", "pages_read_engagement")

# Donde queda anotado como salio la ultima. El aviso por Telegram se borra o
# se pierde entre los del dia, y entonces el unico rastro queda en el log de
# GitHub Actions, que no se lee desde el telefono.
ESTADO = Path(__file__).resolve().parent.parent / "data" / "historias_estado.json"


def activas() -> bool:
    """Las pruebas las apagan con HISTORIAS=0: nunca se publica una de verdad."""
    return os.getenv("HISTORIAS", "1") != "0"


def _al_lado_de(archivo: Path, sufijo: str) -> Path:
    """Donde escribir: al lado del original y NO en una carpeta temporal.

    En el proyecto de salud las historias de las cuatro paginas fallaron un dia
    con "No usable temporary directory found in [...]": `tempfile` no pudo
    escribir en ninguna de las cuatro carpetas que prueba. El flyer, en cambio,
    estaba ahi y se habia podido dibujar y publicar, asi que su carpeta SI se
    puede escribir. Pedir una temporal es pedir permiso en lugares que a esto
    no le importan.
    """
    archivo = Path(str(archivo))
    return archivo.with_name("%s-%s" % (archivo.stem, sufijo))


# El flyer de la frase.
# ---------------------------------------------------------------------------

def vertical(imagen, destino: Optional[Path] = None) -> Path:
    """El flyer entero en 1080x1920, centrado sobre su propia copia borrosa."""
    imagen = Path(str(imagen))
    flyer = Image.open(imagen).convert("RGB")
    fondo = ImageOps.fit(flyer, (ANCHO, ALTO), method=Image.LANCZOS)
    fondo = fondo.filter(ImageFilter.GaussianBlur(DESENFOQUE))
    fondo = ImageEnhance.Brightness(fondo).enhance(BRILLO_FONDO)
    escala = min(ANCHO / flyer.width, ALTO / flyer.height)
    chico = flyer.resize((round(flyer.width * escala), round(flyer.height * escala)),
                         Image.LANCZOS)
    fondo.paste(chico, ((ANCHO - chico.width) // 2, (ALTO - chico.height) // 2))
    destino = Path(destino) if destino else _al_lado_de(imagen, "historia.jpg")
    fondo.save(destino, "JPEG", quality=92)
    return destino


# Partir el reel.
# ---------------------------------------------------------------------------

def _segundos(marca: str) -> float:
    """De `0:01:23.45` a segundos."""
    h, m, s = marca.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def cortes_del_guion(ass: Path) -> List[float]:
    """Donde TERMINA cada renglon del subtitulo, que es donde se puede cortar.

    Sale del `.ass` que `video.armar` deja al lado del mp4, y no de buscar
    silencios en el audio: la musica suena todo el tiempo debajo de la voz, asi
    que `silencedetect` no encuentra ni uno -comprobado, cero silencios a
    -32 dB en un reel entero-. El guion, en cambio, sabe exactamente donde
    termina cada frase.
    """
    try:
        texto = Path(str(ass)).read_text(encoding="utf-8")
    except OSError:
        return []
    fines = []
    for linea in texto.splitlines():
        if not linea.startswith("Dialogue:"):
            continue
        partes = linea.split(",", 9)
        if len(partes) < 3:
            continue
        try:
            fines.append(_segundos(partes[2]))
        except (ValueError, IndexError):
            continue
    return sorted(set(fines))


def guion_de(video: Path) -> Path:
    """El `.ass` del reel, que `video.armar` escribe al lado con el mismo nombre."""
    return Path(str(video)).with_suffix(".ass")


def tramos(dura: float, cortes: Sequence[float] = (),
           tope: float = VIDEO_MAXIMO,
           partir_todo: Optional[bool] = None) -> List[Tuple[float, float]]:
    """Que tramos del reel van a la historia, como `(desde, hasta)`.

    Si el reel entra de una, devuelve uno solo y no se toca nada. Si no entra,
    depende de `PARTIR_EL_REEL`:

    - apagado -lo que eligio el usuario-: UNA tarjeta, del arranque al ultimo
      renglon que entra. El reel se corta y el final se pierde;
    - prendido: el reel entero en tarjetas parejas, no una de 59 s y otra de
      20. El objetivo se recalcula en cada vuelta sobre lo que falta, asi que
      un corte que caiga lejos no desbalancea las que siguen.

    En los dos casos **el corte cae donde termina un renglon del guion**. Si no
    hay ninguno que sirva -un reel sin `.ass`, o uno viejo- se corta en el tope
    o en el objetivo: media frase partida es peor que un corte limpio, pero
    perder la historia entera es peor que las dos cosas.

    `partir_todo` se resuelve ACA y no en la firma: en la firma se evalua al
    importar y `PARTIR_EL_REEL` dejaria de mandar.
    """
    if partir_todo is None:
        partir_todo = PARTIR_EL_REEL
    if dura <= tope + 0.05:
        return [(0.0, dura)]
    posibles_todas = sorted(c for c in cortes if 0.0 < c < dura)
    if not partir_todo:
        # El ultimo renglon que entra. Los renglones duran unos 2,5 s, asi que
        # esto pierde menos de 3 segundos mas que cortar en el tope exacto, y
        # el corte se oye como un final en vez de como un archivo roto.
        entran = [c for c in posibles_todas if TRAMO_MINIMO <= c <= tope]
        return [(0.0, max(entran) if entran else tope)]
    puntos: List[float] = []
    desde = 0.0
    while dura - desde > tope + 0.05:
        cuantas_faltan = max(2, int(math.ceil((dura - desde) / tope)))
        objetivo = desde + (dura - desde) / cuantas_faltan
        sirven = [c for c in posibles_todas
                  if desde + TRAMO_MINIMO <= c <= desde + tope]
        # Sin un renglon donde cortar, se corta en el objetivo y no en el tope:
        # los dos parten una frase al medio, pero 40 y 40 se miran y 59 y 20 no.
        corte = (min(sirven, key=lambda c: abs(c - objetivo)) if sirven
                 else objetivo)
        puntos.append(round(corte, 2))
        desde = corte
    return list(zip([0.0] + puntos, puntos + [dura]))


def duracion(video: Path) -> float:
    """Cuanto dura, o 0.0 si no se puede saber.

    Se delega en `video.duracion`, que le pregunta a FFMPEG y no a ffprobe. La
    primera version de este archivo llamaba a ffprobe y una prueba vieja la
    puso en rojo con razon: **el ffmpeg que trae `imageio-ffmpeg` -el camino
    sin Homebrew, que es el del Mac del usuario- no incluye ffprobe**. O sea
    que las historias del reel habrian fallado ahi y en ningun otro lado, con
    un error que no dice que el que falta es otro programa.
    """
    from . import video as v
    try:
        return float(v.duracion(Path(str(video))) or 0.0)
    except Exception:                                   # noqa: BLE001
        return 0.0


def _es_el_entero(trozos: Sequence[Tuple[float, float]], dura: float) -> bool:
    """Si lo pedido es el video tal cual, de punta a punta.

    Esto existe por un bug que una prueba unitaria NO vio y que aparecio al
    correrlo de verdad: la primera version devolvia el original cuando habia
    `len(trozos) <= 1`, razonando que un solo trozo es el reel entero. Eso era
    cierto cuando un reel largo siempre se partia en varias tarjetas, y dejo de
    serlo el mismo dia en que un solo trozo pasa a significar «el reel
    CORTADO». O sea que la historia se habria subido con el reel completo de 80
    segundos a una ranura de 60, y el que decide que pasa ahi es Facebook.

    La prueba no lo vio porque solo probaba el caso en que el trozo SI era el
    entero, que es el unico que existia cuando se escribio.
    """
    return (len(trozos) == 1 and trozos[0][0] <= 0.01
            and bool(dura) and trozos[0][1] >= dura - 0.05)


def partir(video, trozos: Sequence[Tuple[float, float]],
           dura: float = 0.0) -> List[Path]:
    """Las tarjetas en disco. Si lo pedido es el video entero, lo devuelve tal cual.

    `dura` es cuanto dura el video, y hace falta para poder distinguir «un
    trozo que es todo» de «un trozo que es un recorte»: ver `_es_el_entero`.
    Sin ella se corta, que es la falla segura -una tarjeta recortada de mas se
    ve; una historia de 80 s en una ranura de 60 la arregla Facebook como
    quiera-.

    Se REENCODIFICA y no se copia el flujo: un corte con `-c copy` tiene que
    caer en un cuadro clave, y los del reel estan cada 10 segundos. Copiando,
    la tarjeta arrancaria congelada o directamente en el corte anterior, y eso
    se ve en Facebook y no aca.
    """
    from . import video as v
    video = Path(str(video))
    if _es_el_entero(trozos, dura):
        return [video]
    hechas = []
    for i, (desde, hasta) in enumerate(trozos, start=1):
        salida = _al_lado_de(video, "historia-%d.mp4" % i)
        subprocess.run(
            [v.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
             "-ss", "%.3f" % desde, "-i", str(video), "-t", "%.3f" % (hasta - desde),
             "-c:v", "libx264", "-preset", "fast", "-crf", "20",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart", str(salida)],
            check=True, capture_output=True, timeout=900)
        hechas.append(salida)
    return hechas


# Hablar con Facebook.
# ---------------------------------------------------------------------------

def _revisar(resp) -> dict:
    try:
        datos = resp.json()
    except ValueError:
        datos = {}
    if isinstance(datos, dict) and "error" in datos:
        from .facebook import sin_token
        mensaje = (datos["error"] or {}).get("message") or str(datos["error"])
        raise RuntimeError(sin_token(mensaje)[:300])
    if resp.status_code >= 400:
        from .facebook import sin_token
        raise RuntimeError(sin_token("Facebook contesto %s: %s"
                                     % (resp.status_code, resp.text[:200])))
    return datos


def subir_foto(pagina: Pagina, imagen: Path) -> str:
    """Publica la historia de foto y devuelve su id."""
    with open(imagen, "rb") as fh:
        foto = _revisar(requests.post(
            "%s/%s/photos" % (GRAPH, pagina.fb_page_id), timeout=120,
            data={"published": "false", "access_token": pagina.fb_token},
            files={"source": fh}))
    listo = _revisar(requests.post(
        "%s/%s/photo_stories" % (GRAPH, pagina.fb_page_id), timeout=60,
        data={"photo_id": foto["id"], "access_token": pagina.fb_token}))
    return str(listo.get("post_id") or listo.get("id") or foto["id"])


def subir_video(pagina: Pagina, video: Path) -> str:
    """Publica UNA tarjeta de video y devuelve su id.

    Son tres llamadas, como el reel: se abre la sesion, se mandan los bytes a
    `rupload` y recien entonces se publica.
    """
    inicio = _revisar(requests.post(
        "%s/%s/video_stories" % (GRAPH, pagina.fb_page_id), timeout=60,
        data={"upload_phase": "start", "access_token": pagina.fb_token}))
    datos = Path(str(video)).read_bytes()
    resp = requests.post(inicio["upload_url"], timeout=600, data=datos, headers={
        "Authorization": "OAuth %s" % pagina.fb_token, "offset": "0",
        "file_size": str(len(datos)), "Content-Type": "application/octet-stream"})
    if resp.status_code != 200:
        from .facebook import sin_token
        raise RuntimeError(sin_token("no se pudo subir el video: %s"
                                     % resp.text[:200]))
    listo = _revisar(requests.post(
        "%s/%s/video_stories" % (GRAPH, pagina.fb_page_id), timeout=120,
        data={"upload_phase": "finish", "video_id": inicio["video_id"],
              "access_token": pagina.fb_token}))
    return str(listo.get("post_id") or inicio["video_id"])


def de_la_pagina(pagina: Pagina, limite: int = 25) -> list:
    """Las historias que la pagina tiene AHORA. SOLO LEE.

    Existe porque "no se estan publicando" no se puede contestar de otra
    manera: una historia que falla avisa por Telegram, y si ese mensaje no
    esta no queda ningun rastro en el telefono.

    Facebook borra una historia a las 24 horas, asi que esto contesta por hoy
    y nunca por la semana pasada.
    """
    datos = _revisar(requests.get(
        "%s/%s/stories" % (GRAPH, pagina.fb_page_id), timeout=60,
        params={"fields": "status,creation_time,post_id,media_type",
                "limit": limite, "access_token": pagina.fb_token}))
    return datos.get("data") or []


# Lo que queda anotado.
# ---------------------------------------------------------------------------

def _leer() -> dict:
    try:
        datos = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def anotar(que: str, error: str = "", cuantas: int = 0) -> None:
    """Deja en disco como salio la ultima. No puede fallar.

    Se anotan las dos, no solo los fallos: "la ultima salio bien a las 14:05"
    es la mitad de la respuesta a "no se estan publicando", y sin el camino en
    verde un fallo viejo y ya arreglado seria para siempre lo unico que el
    archivo dice.
    """
    try:
        datos = _leer()
        datos.update({"cuando": datetime.now().isoformat(timespec="seconds"),
                      "que": que, "error": error[:300], "tarjetas": cuantas})
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    except Exception:                                   # noqa: BLE001
        pass


def ultima() -> dict:
    """Como salio la ultima historia, o vacio si no hay nada anotado."""
    return _leer()


def _avisar(que: str, exc: Exception) -> None:
    from .facebook import sin_token
    motivo = sin_token(str(exc))[:200]
    print("  La historia del %s no salio: %s" % (que, motivo))
    anotar(que, motivo)
    try:
        from . import telegram
        telegram.enviar("El %s salio, pero su historia no (%s)." % (que, motivo))
    except Exception:                                   # noqa: BLE001
        pass


# Lo que llaman los que publican.
# ---------------------------------------------------------------------------

def del_flyer(pagina: Pagina, imagen) -> str:
    """La historia del flyer recien publicado. Nunca levanta error."""
    if not activas() or not imagen or not Path(str(imagen)).exists():
        return ""
    hecha = None
    try:
        hecha = vertical(Path(str(imagen)))
        historia = subir_foto(pagina, hecha)
        print("  Historia publicada: %s" % historia)
        anotar("flyer", cuantas=1)
        return historia
    except Exception as exc:                            # noqa: BLE001
        _avisar("flyer", exc)
        return ""
    finally:
        # La vertical ya esta en Facebook: guardarla seria media copia mas de
        # cada flyer. Se borra SOLO el archivo que esta funcion habria creado,
        # comparando el camino exacto: no alcanza con "borra lo que devolvio
        # `vertical`", porque si eso devolviera el original -y en el proyecto
        # de salud una prueba con un doble lo hizo- esto borraria el flyer de
        # un post ya publicado. Ahi se llevo el archivo de pruebas entero.
        propia = _al_lado_de(Path(str(imagen)), "historia.jpg")
        if hecha is not None and Path(hecha) == propia:
            try:
                propia.unlink(missing_ok=True)
            except OSError:
                pass


def del_reel(pagina: Pagina, video) -> List[str]:
    """Las historias del reel recien publicado. Nunca levanta error.

    Devuelve la lista de ids, una por tarjeta. Un reel de 80 s son dos.
    """
    if not activas() or not video or not Path(str(video)).exists():
        return []
    video = Path(str(video))
    trozos: List[Path] = []
    try:
        dura = duracion(video)
        if not dura:
            raise RuntimeError("no pude medir cuanto dura el reel")
        reparto = tramos(dura, cortes_del_guion(guion_de(video)))
        if len(reparto) > 1:
            print("  El reel dura %.0f s y una historia aguanta %.0f: %d tarjetas"
                  % (dura, VIDEO_MAXIMO, len(reparto)))
        elif reparto[-1][1] < dura - 0.1:
            # Se dice cuanto se pierde y no solo que se corto: es la decision
            # del usuario, y el numero es lo que deja cambiarla a la vuelta.
            print("  El reel dura %.0f s y una historia aguanta %.0f: la historia "
                  "sale con los primeros %.0f y se cortan %.0f"
                  % (dura, VIDEO_MAXIMO, reparto[-1][1], dura - reparto[-1][1]))
        trozos = partir(video, reparto, dura)
        ids = []
        for i, trozo in enumerate(trozos, start=1):
            ident = subir_video(pagina, trozo)
            print("  Historia del reel %d/%d: %s" % (i, len(trozos), ident))
            ids.append(ident)
        anotar("reel", cuantas=len(ids))
        return ids
    except Exception as exc:                            # noqa: BLE001
        _avisar("reel", exc)
        return []
    finally:
        for trozo in trozos:
            if Path(trozo) != video:
                try:
                    Path(trozo).unlink(missing_ok=True)
                except OSError:
                    pass
