"""Subir el reel a YouTube como Short.

El reel ya sirve tal cual: 1080x1920 y menos de tres minutos es lo que hace
que YouTube lo tome como Short. Acá no se vuelve a armar nada, se sube el mp4
que `video.armar` dejó.

**Lo que hay que saber antes de usarlo**, porque no es un problema del código
y no se arregla desde acá: Google obliga a una auditoría del proyecto, y hasta
que la pase, los videos que entran por la API quedan **bloqueados en privado**.
No falla y no avisa: la llamada devuelve 200 y el video sube. Por eso
`publicar_short` compara lo que se pidió con lo que YouTube contestó y
`quedo_privado` lo dice en una línea: sin eso, un video que nadie puede ver se
vería igual que uno publicado.

Son tres llamadas:

1. el token de refresco se cambia por uno de acceso (duran una hora),
2. se abre una sesión de subida con la ficha del video (título, descripción),
3. se mandan los bytes a la dirección que esa sesión devolvió.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import requests

API = "https://www.googleapis.com/youtube/v3"
SUBIDA = "https://www.googleapis.com/upload/youtube/v3/videos"
TOKEN = "https://oauth2.googleapis.com/token"
AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"

# El único permiso que hace falta para subir. NO se pide `youtube.readonly`
# aunque serviría para releer el estado después: es otro permiso sensible, o
# sea otro casillero en la pantalla de consentimiento, y la ficha que devuelve
# la propia subida ya dice en qué estado quedó.
PERMISO = "https://www.googleapis.com/auth/youtube.upload"

CLIENTE, SECRETO, REFRESCO = "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"

# Los topes de YouTube. El título se recorta en el que arma el texto y no acá
# -`frases.para_youtube` prefiere el título del capítulo antes que una frase
# cortada-, así que si llega uno más largo es un error de programación y no un
# caso normal: se avisa en vez de recortarlo en silencio.
TITULO_MAXIMO = 100
DESCRIPCION_MAXIMA = 5000

# «Gente y blogs». Es la categoría de una página que habla de vínculos y
# emociones; `27` es Educación, que promete clase y acá no hay ninguna.
CATEGORIA = "22"

# Un reel pesa unos pocos megas, así que una subida tarda segundos. El tope
# está por si la conexión se arrastra, no porque se espere tardar.
ESPERA = 300

# Los errores de Google que no se explican solos. El primero es el que se va a
# ver seguro: con la app en modo Prueba, el token de refresco se vence a los
# siete días y la respuesta es un `invalid_grant` que no nombra el plazo.
PISTAS = {
    "invalid_grant":
        "el permiso se venció o lo revocaste. Con la app en modo «Prueba» "
        "Google lo vence cada 7 días: pasala a «En producción» en la pantalla "
        "de consentimiento y volvé a correr youtube_token.py",
    "invalid_client":
        "el YT_CLIENT_ID o el YT_CLIENT_SECRET no son los del proyecto",
    "youtubeSignupRequired":
        "esa cuenta de Google no tiene canal de YouTube todavía",
    "quotaExceeded":
        "se agotó la cuota del día del proyecto (son unas seis subidas)",
    "forbidden":
        "el proyecto no tiene habilitada la YouTube Data API v3, o el permiso "
        "que diste no incluye subir",
}


class YoutubeError(RuntimeError):
    pass


def _pista(texto: str) -> str:
    """Le agrega al error de Google lo que ese error no dice."""
    for clave, pista in PISTAS.items():
        if clave.lower() in (texto or "").lower():
            return "%s  (%s)" % (texto, pista)
    return texto or "YouTube no dijo por qué"


def faltan() -> List[str]:
    """Las claves del .env que no están. Vacía quiere decir que se puede subir."""
    return [c for c in (CLIENTE, SECRETO, REFRESCO) if not os.environ.get(c)]


def configurado() -> bool:
    return not faltan()


def acceso(espera: int = 30) -> str:
    """Cambia el token de refresco por uno de acceso, que dura una hora.

    El de refresco es el que se guarda; el de acceso no se guarda nunca a
    propósito: dura una hora, así que un archivo con uno viejo sería una
    credencial tirada que además no sirve.
    """
    falta = faltan()
    if falta:
        raise YoutubeError("falta %s en el .env. Corré scripts/youtube_token.py"
                           % ", ".join(falta))
    try:
        r = requests.post(TOKEN, timeout=espera, data={
            "client_id": os.environ[CLIENTE],
            "client_secret": os.environ[SECRETO],
            "refresh_token": os.environ[REFRESCO],
            "grant_type": "refresh_token"})
    except requests.RequestException as e:
        raise YoutubeError("no pude hablar con Google: %s" % e)
    datos = _como_json(r)
    token = datos.get("access_token")
    if not token:
        raise YoutubeError(_pista(datos.get("error_description")
                                 or datos.get("error") or r.text[:300]))
    return token


def _como_json(r) -> Dict:
    try:
        return r.json() or {}
    except ValueError:
        return {}


def _error_de(datos: Dict, r) -> str:
    """El mensaje de un error de la API, que viene anidado de otra forma."""
    e = datos.get("error")
    if isinstance(e, dict):
        razones = [x.get("reason", "") for x in (e.get("errors") or [])]
        return _pista(" ".join([e.get("message") or ""] + razones).strip())
    return _pista(str(e or r.text[:300]))


def ficha(titulo: str, descripcion: str, etiquetas: Sequence[str] = (),
          privacidad: str = "public") -> Dict:
    """La ficha del video, ya revisada.

    `selfDeclaredMadeForKids` va siempre: es obligatorio declararlo y, sin el
    campo, YouTube rechaza la subida con un error que habla de otra cosa.
    """
    titulo = (titulo or "").strip().replace("<", "").replace(">", "")
    if not titulo:
        raise YoutubeError("el video necesita un título")
    if len(titulo) > TITULO_MAXIMO:
        raise YoutubeError("el título pasa de %d caracteres (%d): %r"
                           % (TITULO_MAXIMO, len(titulo), titulo))
    descripcion = (descripcion or "").replace("<", "").replace(">", "")
    if len(descripcion) > DESCRIPCION_MAXIMA:
        raise YoutubeError("la descripción pasa de %d caracteres"
                           % DESCRIPCION_MAXIMA)
    return {
        "snippet": {"title": titulo, "description": descripcion,
                    "tags": [t.lstrip("#") for t in etiquetas if t],
                    "categoryId": CATEGORIA},
        "status": {"privacyStatus": privacidad,
                   "selfDeclaredMadeForKids": False},
    }


def publicar_short(ruta: Path, titulo: str, descripcion: str,
                   etiquetas: Sequence[str] = (), privacidad: str = "public",
                   token: Optional[str] = None, espera: int = ESPERA) -> Dict:
    """Sube el mp4 y devuelve lo que YouTube contestó.

    La ficha se revisa ANTES de abrir la sesión de subida: un título largo
    rebota sin haber mandado un solo byte.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise YoutubeError("no existe el video %s" % ruta)
    cuerpo = ficha(titulo, descripcion, etiquetas, privacidad)
    token = token or acceso()
    peso = ruta.stat().st_size

    try:
        abrir = requests.post(
            SUBIDA, timeout=60,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={"Authorization": "Bearer %s" % token,
                     "Content-Type": "application/json; charset=UTF-8",
                     "X-Upload-Content-Length": str(peso),
                     "X-Upload-Content-Type": "video/mp4"},
            data=json.dumps(cuerpo).encode("utf-8"))
    except requests.RequestException as e:
        raise YoutubeError("no pude abrir la subida: %s" % e)
    if abrir.status_code >= 400:
        raise YoutubeError(_error_de(_como_json(abrir), abrir))
    donde = abrir.headers.get("Location") or abrir.headers.get("location")
    if not donde:
        raise YoutubeError("Google no dijo a dónde subir el archivo")

    # Los bytes de una vez. La sesión se podría reanudar desde donde se cortó,
    # y hoy no se hace: con un archivo de unos pocos megas, volver a subirlo
    # entero cuesta segundos y la maquinaria de reanudar no se podría probar.
    try:
        with ruta.open("rb") as f:
            r = requests.put(donde, timeout=espera, data=f,
                             headers={"Authorization": "Bearer %s" % token,
                                      "Content-Type": "video/mp4",
                                      "Content-Length": str(peso)})
    except requests.RequestException as e:
        raise YoutubeError("se cortó la subida: %s" % e)
    datos = _como_json(r)
    if r.status_code >= 400:
        raise YoutubeError(_error_de(datos, r))
    if not datos.get("id"):
        raise YoutubeError("subió pero YouTube no devolvió el id del video")
    return datos


def enlace(video_id: str) -> str:
    """La dirección corta, que es la que abre el Short en el teléfono."""
    return "https://youtube.com/shorts/%s" % video_id


def quedo_privado(respuesta: Dict, pedida: str = "public") -> bool:
    """Si se pidió público y YouTube lo dejó en privado.

    Es la auditoría pendiente del proyecto y no un error de la subida. Se
    pregunta aparte porque la subida sale bien igual: el video está, pesa, se
    procesa, y no lo ve nadie más que el dueño del canal.
    """
    quedo = ((respuesta or {}).get("status") or {}).get("privacyStatus")
    return bool(quedo and pedida != "private" and quedo != pedida)


def como_quedo(respuesta: Dict) -> str:
    """Una línea con el estado, para el aviso."""
    estado = (respuesta or {}).get("status") or {}
    partes = [estado.get("privacyStatus") or "?"]
    if estado.get("uploadStatus"):
        partes.append(estado["uploadStatus"])
    if estado.get("rejectionReason"):
        partes.append("rechazado: %s" % estado["rejectionReason"])
    return ", ".join(partes)


def enlace_de_permiso(cliente: str, redireccion: str) -> str:
    """La dirección que se abre en el navegador para dar el permiso una vez.

    `access_type=offline` es lo que hace que Google devuelva un token de
    refresco, que es el único que se guarda. `prompt=consent` lo pide de nuevo
    aunque ya lo hayas dado: sin eso, la segunda vuelta vuelve sin token de
    refresco y el .env se quedaría con el viejo, que es justo el que no sirve.
    """
    from urllib.parse import urlencode
    return "%s?%s" % (AUTORIZAR, urlencode({
        "client_id": cliente, "redirect_uri": redireccion,
        "response_type": "code", "scope": PERMISO,
        "access_type": "offline", "prompt": "consent"}))


def canjear(codigo: str, cliente: str, secreto: str, redireccion: str,
            espera: int = 30) -> Dict:
    """Cambia el código que devolvió el navegador por el token de refresco."""
    try:
        r = requests.post(TOKEN, timeout=espera, data={
            "code": codigo, "client_id": cliente, "client_secret": secreto,
            "redirect_uri": redireccion, "grant_type": "authorization_code"})
    except requests.RequestException as e:
        raise YoutubeError("no pude hablar con Google: %s" % e)
    datos = _como_json(r)
    if not datos.get("refresh_token"):
        raise YoutubeError(_pista(datos.get("error_description")
                                  or datos.get("error")
                                  or "Google no devolvió el token de refresco"))
    return datos


# La ficha al lado del mp4.
# ---------------------------------------------------------------------------
#
# El reel se guarda en el repositorio SIEMPRE con el mismo nombre
# (`ultimo.mp4`, que se pisa a si mismo), asi que de ese archivo no se puede
# sacar de que frase es: el nombre ya no lo dice. La ficha viaja al lado y lo
# dice.
#
# Y guarda el texto YA ARMADO en vez del id: asi lo que se sube es exactamente
# lo que se vio al armar el reel, aunque la frase se haya editado en el banco
# en el medio.
FICHA = ".youtube.json"


def ruta_de_ficha(video: Path) -> Path:
    return Path(video).with_suffix(FICHA)


def guardar_ficha(video: Path, titulo: str, descripcion: str,
                  etiquetas: Sequence[str] = (), frase: str = "") -> Path:
    """Deja el titulo y la descripcion al lado del mp4."""
    ruta = ruta_de_ficha(video)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(
        {"frase": frase, "titulo": titulo, "descripcion": descripcion,
         "etiquetas": list(etiquetas)}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return ruta


def ficha_guardada(video: Path) -> Dict:
    """Lo que dice la ficha de al lado, o {} si no hay o esta rota.

    Una ficha ilegible NO revienta: el que sube tiene otra forma de armar el
    texto -el id en el nombre del archivo- y perder la subida por un json a
    medias seria peor.
    """
    ruta = ruta_de_ficha(video)
    if not ruta.is_file():
        return {}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return datos if isinstance(datos, dict) and datos.get("titulo") else {}
