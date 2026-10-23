"""Publicar en Instagram, y saber antes si la cuenta está en condiciones.

Instagram no acepta que le subas el archivo: baja la imagen de una dirección
pública. **Acá esa dirección es la de la foto que Facebook acaba de publicar**,
así que no hace falta ningún servidor: el flyer ya está en los servidores de
Meta, sirviéndose para el post de la página.

Publicar son dos llamadas y una espera en el medio: se crea un contenedor con
la imagen y el texto, Instagram la procesa, y recién entonces se publica.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

from . import facebook
from .config import Pagina
from .facebook import GRAPH, FacebookError

# Se llama `facebook.subir_foto(...)` y no `subir_foto(...)` a proposito. Un
# `from .facebook import subir_foto` ata el nombre a la funcion que habia al
# importar: cambiarla despues -en una prueba, o envolviendola- no cambia lo
# que corre aca. Es el mismo error de las rutas clavadas en las firmas.


class InstagramError(RuntimeError):
    pass


# Cuánto esperar a que Instagram termine de procesar la imagen.
ESPERA = 90
PASO = 3
# El flyer es 1080x1350, o sea 4:5 exacto, que es el formato más alto que
# Instagram acepta. Si algún día cambia el alto del lienzo, hay que mirar
# esto antes que nada: Instagram rechaza el contenedor y el error no dice
# que el problema es la proporción.
PROPORCION_MINIMA = 0.8
PROPORCION_MAXIMA = 1.91

# Los dos que la página no necesita para Facebook y sí para Instagram.
PERMISOS = ("instagram_basic", "instagram_content_publish")

DE_DONDE_SALE_LA_IMAGEN = (
    "Instagram no acepta que le subas el archivo: baja la imagen de una "
    "dirección pública. Esa dirección es la de la foto que Facebook acaba de "
    "publicar, así que no hace falta ningún servidor ni hospedaje."
)


def cuenta_vinculada(pagina: Pagina) -> Dict[str, str]:
    """La cuenta de Instagram vinculada a la página, o {} si no hay ninguna.

    Se pregunta por la PÁGINA y no por la cuenta de Instagram: el vínculo lo
    declara la página, y preguntar al revés necesita un id que todavía no se
    tiene.
    """
    r = facebook._leer(str(pagina.fb_page_id or ""),
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
    datos = facebook._leer("debug_token", input_token=pagina.fb_token or "",
                           access_token="%s|%s" % (app_id, app_secret)).get("data")
    if not datos:
        return None
    return list(datos.get("scopes") or [])


def _pedir(camino: str, **datos) -> dict:
    try:
        r = requests.post("%s/%s" % (GRAPH, camino), data=datos, timeout=60)
    except requests.RequestException as e:
        raise InstagramError("no se pudo llegar a Instagram: %s" % e)
    try:
        cuerpo = r.json()
    except ValueError:
        raise InstagramError("Instagram contestó algo que no es JSON: %s" % r.text[:200])
    if r.status_code >= 400 or "error" in cuerpo:
        raise InstagramError(str((cuerpo.get("error") or {}).get("message") or r.text[:300]))
    return cuerpo


def _esperar_listo(contenedor: str, token: str, espera: int = ESPERA, paso: int = PASO) -> None:
    """Instagram procesa la imagen en segundo plano.

    Publicar antes de que esté lista devuelve un error que no dice que el
    problema es la espera, así que se pregunta hasta que diga FINISHED.
    """
    hasta = time.time() + espera
    while True:
        datos = facebook._leer(contenedor, fields="status_code,status", access_token=token)
        estado = datos.get("status_code")
        if estado == "FINISHED":
            return
        if estado == "ERROR":
            raise InstagramError(datos.get("status") or "Instagram rechazó la imagen")
        if time.time() >= hasta:
            raise InstagramError("Instagram no terminó de procesar la imagen en %ds" % espera)
        time.sleep(paso)


def publicar(pagina: Pagina, caption: str, url_imagen: str,
             cuenta: Optional[str] = None, espera: int = ESPERA, paso: int = PASO) -> str:
    """Publica esa imagen en el Instagram de la página y devuelve el id."""
    if not url_imagen:
        raise InstagramError("Sin dirección de la imagen no hay nada que publicar")
    ig = cuenta or cuenta_vinculada(pagina).get("id")
    if not ig:
        raise InstagramError("La página no tiene ninguna cuenta de Instagram vinculada")
    contenedor = _pedir("%s/media" % ig, image_url=url_imagen, caption=caption,
                        access_token=pagina.fb_token or "").get("id")
    if not contenedor:
        raise InstagramError("Instagram no devolvió el contenedor")
    _esperar_listo(str(contenedor), pagina.fb_token or "", espera, paso)
    publicado = _pedir("%s/media_publish" % ig, creation_id=contenedor,
                       access_token=pagina.fb_token or "").get("id")
    if not publicado:
        raise InstagramError("Instagram no devolvió el id del post")
    return str(publicado)


def publicar_las_dos(pagina: Pagina, caption: str, imagen: Path,
                     espera: int = ESPERA, paso: int = PASO) -> dict:
    """Publica en Facebook y después en Instagram, con la foto ya subida.

    Devuelve {"post_id", "instagram", "error_instagram"}.

    El orden no es casual y la forma de fallar tampoco: **si Instagram falla,
    el post de Facebook YA SALIÓ**. Por eso esta función no levanta la
    excepción de Instagram: devuelve el post de Facebook y el motivo aparte.
    Levantarla haría que quien llama trate el turno como fallido y la frase
    quede sin anotar, o sea publicada en Facebook y ofrecida de nuevo mañana.
    """
    subido = facebook.subir_foto(pagina, caption, imagen)
    resultado = {"post_id": subido["post_id"], "instagram": "", "error_instagram": ""}
    try:
        url = facebook.url_de_la_foto(pagina, subido["foto_id"])
        if not url:
            raise InstagramError("Facebook no devolvió la dirección de la foto")
        resultado["instagram"] = publicar(pagina, caption, url, espera=espera, paso=paso)
    except (InstagramError, FacebookError) as e:
        resultado["error_instagram"] = str(e)
    return resultado
