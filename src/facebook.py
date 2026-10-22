"""Publicar una foto con texto en la página. Una sola llamada a la API Graph."""
from __future__ import annotations

from pathlib import Path

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


def publicar(pagina: Pagina, caption: str, imagen: Path) -> str:
    """Sube el flyer con su caption y devuelve el id del post.

    `/photos` publica la foto como post de la página. La respuesta trae `id`
    (el de la foto) y `post_id` (el del post, que es el que sirve para leer
    comentarios después); se devuelve el segundo y, si no viene, el primero.
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
    return str(post_id)
