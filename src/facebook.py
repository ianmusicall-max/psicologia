"""Publicar una foto con texto en la página. Una sola llamada a la API Graph."""
from __future__ import annotations

from pathlib import Path

import requests

from .config import Pagina

GRAPH = "https://graph.facebook.com/v21.0"


class FacebookError(RuntimeError):
    pass


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
