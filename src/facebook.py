"""Publicar una foto con texto en la página. Una sola llamada a la API Graph."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import requests

from .config import Pagina

GRAPH = "https://graph.facebook.com/v21.0"


class FacebookError(RuntimeError):
    pass


def identificar(token, app_id=None, app_secret=None):
    """Dice de quién es el token y si es de USUARIO o de PÁGINA.

    Devuelve {"tipo": "usuario"|"pagina"|"", "id": ..., "nombre": ...} o
    {"error": "..."} si el token no sirve.

    El tipo NO se pregunta pidiendo `fields=id,name,category` y mirando si
    vino `category`. Cuando el objeto no tiene ese campo, la API no lo omite:
    devuelve el ERROR «(#100) Tried accessing nonexisting field (category)»,
    y entonces un token de usuario perfectamente válido se lee como un token
    roto. Pasó, y el mensaje no deja adivinar la causa.

    Se pregunta con `metadata=1`, que es la introspección de la propia API:
    contesta qué clase de objeto es `/me`. Si por lo que sea no viniera, se
    cae a `debug_token`, que trae el tipo cuando hay credenciales de la app.
    """
    r = _leer("me", metadata=1, fields="id,name", access_token=token)
    if "error" in r:
        return {"error": r["error"].get("message") or str(r["error"])}
    tipo = str((r.get("metadata") or {}).get("type") or "").lower()
    if not tipo and app_id and app_secret:
        d = _leer("debug_token", input_token=token,
                  access_token="%s|%s" % (app_id, app_secret)).get("data") or {}
        tipo = str(d.get("type") or "").lower()
    return {"tipo": {"user": "usuario", "page": "pagina"}.get(tipo, ""),
            "id": r.get("id"), "nombre": r.get("name")}


def sin_token(texto: str) -> str:
    """El mismo texto con el token tapado.

    Hace falta porque un error de red de `requests` trae la URL ENTERA, y la
    URL lleva `access_token=` con el token de la página. Ese texto termina en
    el chat de Telegram, en el log y en las capturas de pantalla: la
    credencial quedaría a la vista sin que nadie la haya pegado en ningún
    lado. Se vio el 2026-10-24, comprobando las credenciales del reel.
    """
    import re
    return re.sub(r"(access_token=)[^&\s)]+", r"\1OCULTO", str(texto))


def _leer(camino, **params):
    """GET a la API, devolviendo siempre un dict (con "error" si algo falló)."""
    try:
        r = requests.get("%s/%s" % (GRAPH, camino), params=params, timeout=30)
    except requests.RequestException as e:
        return {"error": {"message": sin_token("no se pudo llegar a Facebook: %s" % e)}}
    try:
        return r.json()
    except ValueError:
        return {"error": {"message": "respuesta que no es JSON: %s" % r.text[:200]}}


def subir_foto(pagina: Pagina, caption: str, imagen: Path) -> dict:
    """Publica el flyer y devuelve {"post_id", "foto_id"}.

    `/photos` publica la foto como post de la página. La respuesta trae `id`
    (el de la FOTO) y `post_id` (el del POST). Los dos sirven para cosas
    distintas: el del post para leer comentarios, el de la foto para pedirle
    a Meta la dirección pública de la imagen, que es lo que necesita
    Instagram.
    """
    if not pagina.fb_page_id or not pagina.fb_token:
        raise FacebookError("Faltan %s y %s en el .env" % (pagina.page_id_env, pagina.token_env))
    with open(imagen, "rb") as f:
        r = requests.post(
            "%s/%s/photos" % (GRAPH, pagina.fb_page_id),
            data={"message": caption, "access_token": pagina.fb_token},
            files={"source": f},
            timeout=120,
        )
    try:
        datos = r.json()
    except ValueError:
        datos = {}
    if r.status_code >= 400 or "error" in datos:
        raise FacebookError("Facebook contestó %s: %s" % (r.status_code, datos.get("error") or r.text[:300]))
    post_id = datos.get("post_id") or datos.get("id")
    if not post_id:
        raise FacebookError("Facebook no devolvió un id: %s" % datos)
    return {"post_id": str(post_id), "foto_id": str(datos.get("id") or "")}


def publicar(pagina: Pagina, caption: str, imagen: Path) -> str:
    """El id del post. Es la forma corta de `subir_foto` y la que usa casi todo."""
    return subir_foto(pagina, caption, imagen)["post_id"]


def url_de_la_foto(pagina: Pagina, foto_id: str) -> Optional[str]:
    """La dirección pública de una foto ya publicada, la más grande que haya.

    Es lo que permite publicar en Instagram sin tener un servidor: Instagram
    no acepta que le subas el archivo, pero sí baja la imagen de una URL, y
    Meta ya está sirviendo esa misma foto.

    `images` viene de mayor a menor según la documentación, pero se elige por
    ancho y no por posición: si algún día cambia el orden, lo que saldría es
    una miniatura, y eso se vería recién en Instagram.
    """
    if not foto_id:
        return None
    datos = _leer(foto_id, fields="images", access_token=pagina.fb_token or "")
    if "error" in datos:
        raise FacebookError(str((datos["error"] or {}).get("message") or datos["error"]))
    imagenes = [x for x in (datos.get("images") or []) if x.get("source")]
    if not imagenes:
        return None
    return max(imagenes, key=lambda x: int(x.get("width") or 0))["source"]


# Los reels de la página.
# ---------------------------------------------------------------------------
#
# Son TRES llamadas y no una, al revés que una foto: se abre una sesión, se
# mandan los bytes a otro servidor (`rupload`) y recién entonces se publica.
# Es la misma forma que usa Instagram, y por una buena razón: un video pesa
# demasiado para que una sola llamada aguante una conexión que se corta.
#
# Por qué existe esto y no estaba: los reels se subían a Instagram y a YouTube,
# y a Facebook iban solo las frases. En el programa de monetización de Meta,
# los reels son el grueso de lo que se paga, así que faltaba justo en la única
# plataforma donde la página cobra.
REELS = "https://graph.facebook.com/v21.0"
SUBIDA_REELS = "https://rupload.facebook.com/video-upload/v21.0"

# Cuánto se espera a que Facebook termine de procesar el video. No es el
# tiempo de la subida -eso lo manda la conexión- sino el de después.
ESPERA_REEL = 300


def publicar_reel(pagina: Pagina, video: Path, descripcion: str = "",
                  espera: int = ESPERA_REEL) -> str:
    """Publica el reel en la página y devuelve su id.

    `video_state=PUBLISHED` lo deja visible de una. Con `DRAFT` quedaría
    guardado sin salir, que es lo que hay que cambiar el día que se quiera
    aprobar desde el teléfono antes de que salga.
    """
    video = Path(video)
    if not video.is_file():
        raise FacebookError("no existe el video %s" % video)
    if not pagina.fb_page_id or not pagina.fb_token:
        raise FacebookError("Faltan %s y %s en el .env"
                            % (pagina.page_id_env, pagina.token_env))
    peso = video.stat().st_size

    # 1. Abrir la sesión. Devuelve a dónde subir y con qué id.
    try:
        r = requests.post("%s/%s/video_reels" % (REELS, pagina.fb_page_id),
                          data={"upload_phase": "start",
                                "access_token": pagina.fb_token},
                          timeout=60)
    except requests.RequestException as e:
        raise FacebookError(sin_token("no pude abrir la subida del reel: %s" % e))
    datos = _json_de(r)
    if r.status_code >= 400 or "error" in datos:
        raise FacebookError("Facebook contestó %s: %s"
                            % (r.status_code, datos.get("error") or r.text[:300]))
    video_id = str(datos.get("video_id") or "")
    donde = datos.get("upload_url") or "%s/%s" % (SUBIDA_REELS, video_id)
    if not video_id:
        raise FacebookError("Facebook no devolvió el id del video: %s" % datos)

    # 2. Los bytes. El token va en la cabecera y no como parámetro: este
    # servidor es otro y no lee la query, cosa que su error no dice.
    try:
        with video.open("rb") as f:
            r = requests.post(donde, timeout=espera, data=f, headers={
                "Authorization": "OAuth %s" % pagina.fb_token,
                "offset": "0", "file_size": str(peso)})
    except requests.RequestException as e:
        raise FacebookError(sin_token("se cortó la subida del reel: %s" % e))
    datos = _json_de(r)
    if r.status_code >= 400 or "error" in datos:
        raise FacebookError("Facebook rechazó el video: %s"
                            % (datos.get("error") or r.text[:300]))

    # 3. Publicarlo. Hasta acá el video existe y no lo ve nadie.
    try:
        r = requests.post("%s/%s/video_reels" % (REELS, pagina.fb_page_id),
                          data={"upload_phase": "finish", "video_id": video_id,
                                "video_state": "PUBLISHED",
                                "description": descripcion,
                                "access_token": pagina.fb_token},
                          timeout=60)
    except requests.RequestException as e:
        raise FacebookError(sin_token("subió pero no pude publicarlo: %s" % e))
    datos = _json_de(r)
    if r.status_code >= 400 or "error" in datos:
        raise FacebookError("subió pero Facebook no lo publicó: %s"
                            % (datos.get("error") or r.text[:300]))
    return video_id


def enlace_de_reel(video_id: str) -> str:
    return "https://www.facebook.com/reel/%s" % video_id


def _json_de(r) -> dict:
    try:
        return r.json() or {}
    except ValueError:
        return {}
