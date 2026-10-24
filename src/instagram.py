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


# Lo que el nodo de la cuenta admite como campos. Pedir uno que no existe
# hace fallar la llamada ENTERA con un error que habla de otra cosa, asi que
# esta lista es cerrada a proposito.
CAMPOS_CUENTA = ("id", "ig_id", "username", "name", "biography", "website",
                 "followers_count", "follows_count", "media_count",
                 "profile_picture_url")


def ficha_de_la_cuenta(pagina: Pagina, cuenta: Optional[str] = None) -> Dict:
    """Todo lo que Meta cuenta de la cuenta vinculada, y su cupo de publicado.

    SOLO LEE. Existe porque un reel rechazado con «ProcessingFailedError» no
    dice nada de la cuenta, y lo primero que hay que saber es si la cuenta
    esta en condiciones de publicar por API: `content_publishing_limit`
    contesta eso con un numero -el cupo de 24 horas- y falla si no lo esta.

    **El tipo de cuenta no se puede preguntar.** La API no lo expone, y es
    justo la diferencia que importa para los reels: `instagram_business_account`
    viene con id tanto para una cuenta de Empresa como para una de Creador.
    Eso se mira en la app, y por eso el consejo del script manda ahi.
    """
    ig = cuenta or cuenta_vinculada(pagina).get("id")
    if not ig:
        return {"error": "la pagina no tiene ninguna cuenta profesional vinculada"}
    token = pagina.fb_token or ""
    return {"cuenta": facebook._leer(str(ig), fields=",".join(CAMPOS_CUENTA),
                                     access_token=token),
            "cupo": facebook._leer("%s/content_publishing_limit" % ig,
                                   fields="config,quota_usage",
                                   access_token=token)}


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


# ---------------------------------------------------------------------------
# Los reels.
#
# Un video NO se puede publicar con el truco de la foto. Para una imagen,
# Instagram baja el archivo de la direccion que Facebook ya sirve; para un
# video pide una direccion publica al mp4, y Facebook no devuelve ninguna que
# Instagram pueda leer. Hacia falta alojar el archivo en algun lado.
#
# La salida es la subida POR PARTES (`upload_type=resumable`): se crea el
# contenedor, se mandan los bytes a un host aparte y recien despues se
# publica. Asi el mp4 no tiene que estar en ningun lado publico, que es lo
# que hace que esto se pueda hacer desde la Mac sin subir nada.
#
# Esta disponible por el camino de Facebook Login -token de PAGINA sobre
# graph.facebook.com-, que es justo el que esta pagina ya usa para todo lo
# demas. Por el camino de Instagram Login solo se acepta la direccion
# publica.
# ---------------------------------------------------------------------------

# Los bytes NO van a graph.facebook.com: van a este host. Es el unico lugar
# del proyecto donde se habla con otra direccion de Meta.
SUBIDA = "https://rupload.facebook.com/ig-api-upload/v21.0"

# Un reel se procesa mucho mas que una foto: son 90 segundos de video.
ESPERA_REEL = 300

# Lo que Meta admite de un reel por la API. El tope de peso importa poco -los
# nuestros andan por los 2 MB- pero el de duracion es el mismo que ya cuida
# `video.TOPE_SEGUNDOS`, y conviene que este escrito de los dos lados.
PESO_MAXIMO = 300 * 1024 * 1024


def subir_los_bytes(contenedor: str, video: Path, token: str) -> None:
    """Le manda el mp4 a Meta, en una sola pieza.

    En una pieza y no en partes porque un reel nuestro pesa un par de megas:
    partirlo seria maquinaria para un problema que no tenemos. El protocolo lo
    permite igual, y por eso van `offset` y `file_size`.
    """
    video = Path(video)
    if not video.is_file():
        raise InstagramError("no encuentro el video %s" % video)
    pesa = video.stat().st_size
    if pesa > PESO_MAXIMO:
        raise InstagramError("el reel pesa %.0f MB y el tope de Instagram son %d"
                             % (pesa / 1e6, PESO_MAXIMO // (1024 * 1024)))
    try:
        with open(video, "rb") as f:
            r = requests.post(
                "%s/%s" % (SUBIDA, contenedor), data=f, timeout=600,
                headers={"Authorization": "OAuth %s" % token,
                         "offset": "0",
                         "file_size": str(pesa),
                         "Content-Type": "application/octet-stream"})
    except requests.RequestException as e:
        raise InstagramError("no se pudo subir el video: %s" % e)
    if r.status_code >= 400:
        raise InstagramError("Instagram rechazo el video (%d): %s"
                             % (r.status_code, r.text[:300]))


def publicar_reel(pagina: Pagina, caption: str, video: Path,
                  cuenta: Optional[str] = None, espera: int = ESPERA_REEL,
                  paso: int = PASO, compartir: bool = True) -> str:
    """Publica ese mp4 como reel y devuelve el id.

    `compartir` lo deja ademas en el feed del perfil, no solo en la pestania
    de reels: un reel que no aparece en el perfil lo ve mucha menos gente.
    """
    video = Path(video)
    ig = cuenta or cuenta_vinculada(pagina).get("id")
    if not ig:
        raise InstagramError("La página no tiene ninguna cuenta de Instagram vinculada")
    token = pagina.fb_token or ""
    contenedor = _pedir("%s/media" % ig, media_type="REELS",
                        upload_type="resumable", caption=caption,
                        share_to_feed="true" if compartir else "false",
                        access_token=token).get("id")
    if not contenedor:
        raise InstagramError("Instagram no devolvió el contenedor")
    subir_los_bytes(str(contenedor), video, token)
    _esperar_listo(str(contenedor), token, espera, paso)
    publicado = _pedir("%s/media_publish" % ig, creation_id=contenedor,
                       access_token=token).get("id")
    if not publicado:
        raise InstagramError("Instagram no devolvió el id del reel")
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
