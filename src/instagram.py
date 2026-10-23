"""Lo que hace falta saber antes de intentar publicar en Instagram.

Acá no se publica nada: esto solo averigua si la cuenta está en condiciones.
Publicar en Instagram es otra cosa y tiene un requisito que no depende de
permisos (ver PORQUE_HACE_FALTA_UNA_URL).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .config import Pagina
from .facebook import GRAPH, _leer

# Los dos que la página no necesita para Facebook y sí para Instagram.
PERMISOS = ("instagram_basic", "instagram_content_publish")

PORQUE_HACE_FALTA_UNA_URL = (
    "Instagram no acepta que le subas el archivo: baja la imagen de una "
    "dirección pública de internet. Los flyers viven en el disco de tu Mac, "
    "así que hoy no hay de dónde bajarlos."
)


def cuenta_vinculada(pagina: Pagina) -> Dict[str, str]:
    """La cuenta de Instagram vinculada a la página, o {} si no hay ninguna.

    Se pregunta por la PÁGINA y no por la cuenta de Instagram: el vínculo lo
    declara la página, y preguntar al revés necesita un id que todavía no se
    tiene.
    """
    r = _leer(str(pagina.fb_page_id or ""),
              fields="name,instagram_business_account{id,username,name}",
              access_token=pagina.fb_token or "")
    if "error" in r:
        return {"error": (r["error"] or {}).get("message") or str(r["error"])}
    cuenta = r.get("instagram_business_account") or {}
    return {"pagina": r.get("name") or "", "id": cuenta.get("id") or "",
            "usuario": cuenta.get("username") or "", "nombre": cuenta.get("name") or ""}


def permisos_que_faltan(scopes: List[str]) -> List[str]:
    return [p for p in PERMISOS if p not in scopes]


def scopes_del_token(pagina: Pagina, app_id: str, app_secret: str) -> Optional[List[str]]:
    """Los permisos del token, o None si no se pudo preguntar.

    None y [] no son lo mismo: [] es «no tiene ninguno» y None es «no pude
    averiguarlo», y confundirlos manda a regenerar un token que estaba bien.
    """
    datos = _leer("debug_token", input_token=pagina.fb_token or "",
                  access_token="%s|%s" % (app_id, app_secret)).get("data")
    if not datos:
        return None
    return list(datos.get("scopes") or [])
