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

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import requests

ROOT = Path(__file__).resolve().parent.parent

API = "https://www.googleapis.com/youtube/v3"
SUBIDA = "https://www.googleapis.com/upload/youtube/v3/videos"
TOKEN = "https://oauth2.googleapis.com/token"
AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"

# Los permisos. El primero es el de subir. El segundo hace falta SOLO para
# meter el video en la lista de reproducción: `playlistItems.insert` no lo
# acepta con el de subir, y el más angosto que sí lo acepta es este.
#
# NO se pide `youtube.readonly` aunque serviría para releer el estado
# después: la ficha que devuelve la propia subida ya dice en qué estado quedó.
PERMISO = "https://www.googleapis.com/auth/youtube.upload"
PERMISO_LISTAS = "https://www.googleapis.com/auth/youtube"
PERMISOS = (PERMISO, PERMISO_LISTAS)

# La lista donde van todos los videos. La eligió el usuario el 2026-10-24.
# Si no existe se crea sola: un nombre escrito en el código y una lista creada
# a mano en el panel se desincronizan el día que alguien la renombre.
PLAYLIST = "Lo que nadie te explicó"

# La descripción de la lista. El nombre dice quién es la página y no se busca
# en YouTube; estas palabras sí, y es lo que YouTube indexa de una lista.
PLAYLIST_DESCRIPCION = ("Psicología en claro: emociones, ansiedad, autoestima, "
                        "vínculos, límites y duelo. Un video corto por día.")

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
    return _refrescar(espera)[0]


def permisos_del_token(espera: int = 30) -> List[str]:
    """Qué permisos trae el token guardado.

    Hace falta porque un token que anda no es un token que alcance: el de
    subir no deja meter el video en la lista, y la diferencia solo se ve
    cuando el video ya está publicado y fuera de la lista.

    Google devuelve `scope` al refrescar. Si algún día no lo devolviera, esto
    da [] y quien pregunte NO debe leer eso como «faltan todos»: es «no se
    pudo saber».
    """
    return _refrescar(espera)[1]


def _refrescar(espera: int = 30):
    """(token de acceso, permisos que trae)."""
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
    return token, (datos.get("scope") or "").split()


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
                   token: Optional[str] = None, espera: int = ESPERA,
                   playlist: Optional[str] = PLAYLIST) -> Dict:
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

    # La lista va acá dentro y no en cada script: «todos los videos a la
    # lista» no puede depender de que cada uno se acuerde. Y si falla NO se
    # levanta: el video ya está publicado, y perderlo por una lista sería
    # cambiar un problema chico por uno grande.
    if playlist:
        try:
            datos["playlist"] = agregar_a_playlist(datos["id"], playlist, token)
        except YoutubeError as e:
            datos["playlist_error"] = str(e)
    return datos


def _api(metodo: str, camino: str, token: str, params=None, cuerpo=None,
         espera: int = 30) -> Dict:
    """Una llamada a la API, con el error ya desenrollado."""
    try:
        r = requests.request(metodo, "%s/%s" % (API, camino), timeout=espera,
                             params=params or {},
                             headers={"Authorization": "Bearer %s" % token,
                                      "Content-Type": "application/json"},
                             data=json.dumps(cuerpo).encode("utf-8") if cuerpo else None)
    except requests.RequestException as e:
        raise YoutubeError("no pude hablar con YouTube: %s" % e)
    datos = _como_json(r)
    if r.status_code >= 400:
        raise YoutubeError(_error_de(datos, r))
    return datos


def buscar_playlist(nombre: str, token: str) -> str:
    """El id de la lista con ese nombre, o "" si no está.

    Se busca por NOMBRE y no se guarda el id en ningún lado a propósito: un id
    guardado y una lista borrada o renombrada en el panel se desincronizan sin
    que nada falle, y el video se iría a una lista que ya no existe. Cuesta
    1 punto de cuota contra los 1.600 de la subida.
    """
    pagina = None
    while True:
        params = {"part": "snippet", "mine": "true", "maxResults": 50}
        if pagina:
            params["pageToken"] = pagina
        datos = _api("GET", "playlists", token, params)
        for x in datos.get("items") or []:
            if ((x.get("snippet") or {}).get("title") or "").strip() == nombre.strip():
                return str(x.get("id") or "")
        pagina = datos.get("nextPageToken")
        if not pagina:
            return ""


def crear_playlist(nombre: str, token: str, descripcion: str = PLAYLIST_DESCRIPCION) -> str:
    """Crea la lista y devuelve su id. Pública: una lista privada no la ve nadie."""
    datos = _api("POST", "playlists", token, {"part": "snippet,status"},
                 {"snippet": {"title": nombre, "description": descripcion},
                  "status": {"privacyStatus": "public"}})
    ident = str(datos.get("id") or "")
    if not ident:
        raise YoutubeError("YouTube no devolvió el id de la lista")
    return ident


def agregar_a_playlist(video_id: str, nombre: str = PLAYLIST,
                       token: Optional[str] = None) -> str:
    """Mete el video en la lista, creándola si no existe. Devuelve el id."""
    token = token or acceso()
    lista = buscar_playlist(nombre, token) or crear_playlist(nombre, token)
    _api("POST", "playlistItems", token, {"part": "snippet"},
         {"snippet": {"playlistId": lista,
                      "resourceId": {"kind": "youtube#video", "videoId": video_id}}})
    return lista


def enlace_de_playlist(lista: str) -> str:
    return "https://www.youtube.com/playlist?list=%s" % lista


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


def enlace_de_permiso(cliente: str, redireccion: str,
                      permisos: Sequence[str] = PERMISOS) -> str:
    """La dirección que se abre en el navegador para dar el permiso una vez.

    `permisos` es un argumento y no la constante de este archivo porque el
    mismo cliente de Google sirve para otros servicios: el token que se pide
    acá también es el que usa `src/drive.py`. Quien pide el consentimiento
    sabe para qué lo quiere; este módulo solo sabe de YouTube.

    `access_type=offline` es lo que hace que Google devuelva un token de
    refresco, que es el único que se guarda. `prompt=consent` lo pide de nuevo
    aunque ya lo hayas dado: sin eso, la segunda vuelta vuelve sin token de
    refresco y el .env se quedaría con el viejo, que es justo el que no sirve.
    """
    from urllib.parse import urlencode
    return "%s?%s" % (AUTORIZAR, urlencode({
        "client_id": cliente, "redirect_uri": redireccion,
        "response_type": "code", "scope": " ".join(permisos),
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


# Lo que ya se subio.
# ---------------------------------------------------------------------------
#
# YouTube NO se da cuenta de que un video es el mismo: subirlo dos veces deja
# dos Shorts iguales en el canal. Paso el primer dia, con el mismo mp4 subido
# dos veces por correr el comando dos veces.
#
# Y cuesta: cada subida son 1.600 de los 10.000 puntos de cuota diaria, o sea
# unas SEIS por dia. Una repetida se lleva un sexto del dia.
#
# La llave es la huella del ARCHIVO y no su nombre: `ultimo.mp4` se pisa a si
# mismo, asi que el mismo nombre son videos distintos de un dia a otro, y el
# mismo video puede estar con dos nombres (`due-01.mp4` y `ultimo.mp4`).
SUBIDOS = ROOT / "data" / "youtube_subidos.json"


def huella(ruta: Path) -> str:
    """La huella del archivo, leido de a pedazos.

    De a un mega y no de una: un reel pesa unos 13 MB hoy, pero un Short de
    tres minutos puede pesar diez veces eso y no hay por que tenerlo entero en
    memoria para sacarle una huella.
    """
    h = hashlib.sha1()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def _leer_subidos(registro: Optional[Path] = None) -> Dict:
    ruta = Path(registro or SUBIDOS)
    if not ruta.is_file():
        return {}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return datos if isinstance(datos, dict) else {}


def ya_subido(ruta: Path, registro: Optional[Path] = None) -> Dict:
    """Lo que se sepa de ese video si ya se subio, o {} si es la primera vez."""
    return _leer_subidos(registro).get(huella(ruta)) or {}


def anotar_subido(ruta: Path, video_id: str, titulo: str = "",
                  cuando: str = "", registro: Optional[Path] = None) -> Path:
    """Anota que ese archivo ya esta en YouTube.

    RELEE antes de escribir: el archivo lo puede haber tocado otra corrida en
    el medio -una subida tarda lo que tarda la conexion- y el que guarde ultimo
    con una copia vieja en la mano le borraria al otro lo que acaba de anotar.
    Lo que se perderia es justo lo que evita subir dos veces lo mismo.
    """
    from datetime import datetime
    ruta_r = Path(registro or SUBIDOS)
    datos = _leer_subidos(ruta_r)
    datos[huella(ruta)] = {"id": video_id, "titulo": titulo,
                           "archivo": Path(ruta).name,
                           "cuando": cuando or datetime.now().isoformat(timespec="seconds")}
    ruta_r.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta_r.with_suffix(".parcial")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(ruta_r)
    return ruta_r
