"""La copia en alta de cada reel, en tu Drive.

Lo pidió el usuario varias veces: que el mp4 quede en Drive además de salir
publicado. El artefacto de GitHub ya lo guarda noventa días, pero eso vence y
hay que ir a buscarlo a la pestaña Actions; Drive es donde el archivo queda.

**No hace falta una credencial nueva, y eso es lo que vale saber.** Google usa
el mismo cliente de OAuth para todos sus servicios, así que esto va con el que
ya existe para YouTube (`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`)
y con la misma máquina de refresco de `src/youtube.py`.

LO QUE SÍ HACE FALTA es un permiso más dentro de ese token, y eso no se puede
hacer desde acá: un permiso lo da el dueño de la cuenta en el navegador. Son
tres pasos, una vez:

    1. En console.cloud.google.com, habilitar la API de Drive en el mismo
       proyecto donde está el cliente de YouTube.
    2. `python3 scripts/youtube_token.py` en la Mac. Pide los permisos de
       YouTube Y el de Drive, y escribe el `YT_REFRESH_TOKEN` nuevo.
    3. Copiar ese valor al secreto `YT_REFRESH_TOKEN` del repositorio.

Hasta que eso pase, `puede()` devuelve False y el turno del reel no intenta
nada: ni falla ni llena el log de errores, que es lo que dejó `RECETA_PRIVADA`
encendido durante días en el otro proyecto.

**El permiso es `drive.file`, el más chico que existe**: deja crear archivos y
tocar SOLO los que esta aplicación creó. No puede leer el resto de tu Drive,
que es exactamente lo que uno quiere de una credencial que vive en los
secretos de un repositorio.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

import requests

from src import youtube

# El permiso más acotado de Drive: crear archivos y ver solo los propios.
PERMISO = "https://www.googleapis.com/auth/drive.file"

SUBIDA = "https://www.googleapis.com/upload/drive/v3/files"
ARCHIVOS = "https://www.googleapis.com/drive/v3/files"

# Donde van los reels. Se crea sola la primera vez y despues se encuentra por
# nombre: un id escrito en el codigo se desincroniza el dia que alguien borre
# la carpeta, y un id en el .env es una cosa mas que configurar a mano.
CARPETA = "Reels de la pagina"

ESPERA = 120


class DriveError(RuntimeError):
    pass


def puede(espera: int = 30) -> bool:
    """Si el token guardado trae el permiso de Drive.

    Devuelve False tambien cuando no se pudo preguntar. Es a proposito: esto
    es un extra sobre un reel que YA se publico, y la falla segura es no
    intentar. Un error de red no tiene que convertirse en un renglon rojo en
    un turno que salio bien.
    """
    try:
        return PERMISO in youtube.permisos_del_token(espera)
    except Exception:                                     # noqa: BLE001
        return False


def _pedir(metodo: str, url: str, token: str, espera: int, **kw) -> Dict:
    try:
        r = requests.request(metodo, url, timeout=espera,
                             headers=dict({"Authorization": "Bearer %s" % token},
                                          **kw.pop("headers", {})), **kw)
    except requests.RequestException as e:
        raise DriveError("no pude hablar con Drive: %s" % e)
    try:
        datos = r.json() or {}
    except ValueError:
        datos = {}
    if r.status_code >= 400:
        detalle = (datos.get("error") or {}).get("message") or r.text[:300]
        raise DriveError("Drive dijo %d: %s" % (r.status_code, detalle))
    return datos


def carpeta(token: str, nombre: str = CARPETA, espera: int = ESPERA) -> str:
    """El id de la carpeta, creandola si no esta.

    La busqueda solo ve lo que esta aplicacion creo -es lo que significa
    `drive.file`- asi que encuentra la carpeta propia y nunca una carpeta tuya
    que se llame igual.
    """
    busca = _pedir("GET", ARCHIVOS, token, espera, params={
        "q": ("mimeType='application/vnd.google-apps.folder' and "
              "name='%s' and trashed=false" % nombre.replace("'", "\\'")),
        "fields": "files(id,name)", "pageSize": 10})
    hay = busca.get("files") or []
    if hay:
        return hay[0]["id"]
    nueva = _pedir("POST", ARCHIVOS, token, espera,
                   headers={"Content-Type": "application/json"},
                   data=json.dumps({
                       "name": nombre,
                       "mimeType": "application/vnd.google-apps.folder"}))
    if not nueva.get("id"):
        raise DriveError("Drive creo la carpeta y no devolvio su id")
    return nueva["id"]


def _multipart(meta: Dict, datos: bytes, tipo: str):
    """El cuerpo de una subida multipart, que Drive pide en UNA sola pieza.

    Se arma a mano y no con `files=` de requests porque Drive quiere las dos
    partes en este orden y con estos tipos, y `files=` manda `form-data`.
    """
    linde = "----reel" + os.urandom(8).hex()
    cuerpo = b"".join([
        ("--%s\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
         % linde).encode("utf-8"),
        json.dumps(meta).encode("utf-8"),
        ("\r\n--%s\r\nContent-Type: %s\r\n\r\n" % (linde, tipo)).encode("utf-8"),
        datos,
        ("\r\n--%s--\r\n" % linde).encode("utf-8"),
    ])
    return cuerpo, "multipart/related; boundary=%s" % linde


def subir(ruta: Path, nombre: Optional[str] = None, tipo: str = "video/mp4",
          en: Optional[str] = None, token: Optional[str] = None,
          espera: int = ESPERA) -> str:
    """Sube un archivo y devuelve su enlace. Levanta `DriveError` si falla."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise DriveError("no existe el archivo %s" % ruta)
    token = token or youtube.acceso()
    meta = {"name": nombre or ruta.name}
    destino = en or carpeta(token, espera=espera)
    if destino:
        meta["parents"] = [destino]
    cuerpo, content_type = _multipart(meta, ruta.read_bytes(), tipo)
    datos = _pedir("POST", SUBIDA, token, espera,
                   params={"uploadType": "multipart", "fields": "id,webViewLink"},
                   headers={"Content-Type": content_type}, data=cuerpo)
    return datos.get("webViewLink") or datos.get("id") or ""


def guardar_reel(video: Path, caption: Optional[Path] = None,
                 espera: int = ESPERA) -> Dict[str, str]:
    """El mp4 y su caption al lado, en la carpeta de los reels.

    NUNCA levanta error: el reel ya salió publicado cuando esto corre, y una
    copia que no se pudo guardar no puede convertir un turno que funcionó en
    un turno en rojo. Lo que devuelve dice qué pasó.
    """
    if not puede(min(espera, 30)):
        return {"error": "el token no tiene el permiso de Drive todavía"}
    try:
        token = youtube.acceso(min(espera, 30))
        donde = carpeta(token, espera=espera)
        salida = {"video": subir(video, en=donde, token=token, espera=espera)}
        if caption and Path(caption).is_file():
            salida["caption"] = subir(caption, tipo="text/plain; charset=utf-8",
                                      en=donde, token=token, espera=espera)
        return salida
    except Exception as e:                                # noqa: BLE001
        return {"error": str(e)}
