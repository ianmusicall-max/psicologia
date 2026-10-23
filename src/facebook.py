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


def _leer(camino, **params):
    """GET a la API, devolviendo siempre un dict (con "error" si algo falló)."""
    try:
        r = requests.get("%s/%s" % (GRAPH, camino), params=params, timeout=30)
    except requests.RequestException as e:
        return {"error": {"message": "no se pudo llegar a Facebook: %s" % e}}
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
