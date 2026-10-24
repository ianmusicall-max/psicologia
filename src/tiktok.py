"""TikTok: deja el reel del dia en tus BORRADORES.

No publica. Y no es una limitacion del codigo: TikTok no deja publicar en
publico hasta que la app pasa su auditoria, y mientras tanto todo lo que suba
una app sin auditar queda en privado -hay un error con nombre propio para
eso, `unaudited_client_can_only_post_to_private_accounts`-. Pedir esa
auditoria son semanas de tramite, con video de demostracion, y las guias
coinciden en que rechazan las apps que manejan la cuenta del propio dueño,
que es exactamente esta.

Asi que el camino es el otro que TikTok ofrece: el video viaja a tu bandeja,
te llega la notificacion y vos terminas de publicarlo en la app. Lo eligio el
usuario el 2026-10-24 sabiendo eso.

**La ventaja que no tiene repostear desde Instagram**: este mp4 lo armamos
nosotros, asi que no lleva la marca de agua de otra red, que es lo que TikTok
penaliza.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

import requests

ROOT = Path(__file__).resolve().parent.parent

API = "https://open.tiktokapis.com/v2"
AUTORIZAR = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN = "%s/oauth/token/" % API

# Subir a la bandeja. El de publicar derecho (`/post/publish/video/init/`) es
# el que pide la auditoria, y a proposito no esta escrito en este archivo:
# que no se pueda llamar por error es parte del diseño.
INICIAR = "%s/post/publish/inbox/video/init/" % API
ESTADO = "%s/post/publish/status/fetch/" % API

# Alcanza para dejar el video en la bandeja. `video.publish` -el de publicar
# en el perfil- es el que necesita la auditoria.
PERMISO = "video.upload"

CLAVE, SECRETO, REFRESCO = "TT_CLIENT_KEY", "TT_CLIENT_SECRET", "TT_REFRESH_TOKEN"

# Lo que TikTok admite en una sola pieza. Un reel nuestro pesa unos 13 MB, asi
# que entra entero y no hay que partirlo; el tope existe para que el dia que
# alguien suba un video largo el error diga que pasa y no reviente adentro.
PIEZA_MAXIMA = 64 * 1024 * 1024

ESPERA = 300

# Los errores que no se explican solos, traducidos. Mismo criterio que en
# YouTube: el texto de TikTok habla de otra cosa.
PISTAS = {
    "unaudited_client_can_only_post_to_private_accounts":
        "esta app no paso la auditoria de TikTok, asi que solo puede dejar el "
        "video en tus borradores. Si este error aparece es que algo pidio "
        "publicar en el perfil en vez de subir a la bandeja.",
    "access_token_invalid":
        "el permiso de TikTok vencio. Corre scripts/tiktok_token.py y "
        "actualiza TT_REFRESH_TOKEN.",
    "scope_not_authorized":
        "al permiso le falta video.upload. Hay que darlo de nuevo con ese "
        "tildado.",
    "rate_limit_exceeded":
        "TikTok admite seis pedidos por minuto. Esperá un minuto.",
    "spam_risk_too_many_posts":
        "TikTok corto por cantidad de subidas del dia. Mañana vuelve solo.",
}


class TiktokError(RuntimeError):
    pass


def _pista(texto: str) -> str:
    for clave, pista in PISTAS.items():
        if clave in (texto or ""):
            return "%s (%s)" % (texto, pista)
    return texto or "TikTok no dijo por que"


def faltan() -> list:
    """Cuales de los tres secretos no estan. Nombrar solo el que falta."""
    return [n for n in (CLAVE, SECRETO, REFRESCO) if not os.environ.get(n)]


def configurado() -> bool:
    return not faltan()


def _error_de(datos: Dict) -> str:
    err = (datos or {}).get("error") or {}
    # TikTok contesta 200 con error.code == "ok" cuando sale bien.
    codigo = err.get("code") or ""
    if codigo and codigo != "ok":
        return _pista("%s: %s" % (codigo, err.get("message") or ""))
    return ""


def _como_json(r) -> Dict:
    try:
        return r.json()
    except ValueError:
        raise TiktokError("TikTok contesto algo que no es JSON: %s" % r.text[:200])


def acceso() -> str:
    """Un token de acceso a partir del de refresco. Devuelve el token y nada mas."""
    falta = faltan()
    if falta:
        raise TiktokError("falta %s en el entorno" % " y ".join(falta))
    try:
        r = requests.post(TOKEN, timeout=30,
                          headers={"Content-Type": "application/x-www-form-urlencoded"},
                          data={"client_key": os.environ[CLAVE],
                                "client_secret": os.environ[SECRETO],
                                "grant_type": "refresh_token",
                                "refresh_token": os.environ[REFRESCO]})
    except requests.RequestException as e:
        raise TiktokError("no pude hablar con TikTok: %s" % e)
    datos = _como_json(r)
    if r.status_code >= 400 or datos.get("error"):
        raise TiktokError(_pista(str(datos.get("error_description")
                                     or datos.get("error") or r.text[:200])))
    token = datos.get("access_token")
    if not token:
        raise TiktokError("TikTok no devolvio el token de acceso")
    return token


def _api(camino: str, token: str, cuerpo: Dict, espera: int = 60) -> Dict:
    try:
        r = requests.post(camino, timeout=espera,
                          headers={"Authorization": "Bearer %s" % token,
                                   "Content-Type": "application/json; charset=UTF-8"},
                          data=json.dumps(cuerpo).encode("utf-8"))
    except requests.RequestException as e:
        raise TiktokError("no pude hablar con TikTok: %s" % e)
    datos = _como_json(r)
    malo = _error_de(datos)
    if r.status_code >= 400 or malo:
        raise TiktokError(malo or _pista(r.text[:200]))
    return datos


def subir_a_borradores(video: Path, token: str = "") -> str:
    """Deja el mp4 en tu bandeja de TikTok. Devuelve el `publish_id`.

    En UNA sola pieza: un reel pesa unos 13 MB y partirlo seria maquinaria
    para un problema que no tenemos.

    La direccion de subida se usa EXACTAMENTE como la devuelve TikTok. Su
    propia documentacion se contradice sobre el camino -un ejemplo dice
    `/video/` y otro `/upload/`- asi que armarla a mano es apostar a cual de
    los dos esta al dia.
    """
    video = Path(video)
    if not video.is_file():
        raise TiktokError("no encuentro el video %s" % video)
    pesa = video.stat().st_size
    if pesa > PIEZA_MAXIMA:
        raise TiktokError("el video pesa %.0f MB y en una sola pieza entran %d"
                          % (pesa / 1e6, PIEZA_MAXIMA // (1024 * 1024)))
    token = token or acceso()
    datos = (_api(INICIAR, token,
                  {"source_info": {"source": "FILE_UPLOAD", "video_size": pesa,
                                   "chunk_size": pesa, "total_chunk_count": 1}})
             .get("data") or {})
    publish_id, url = datos.get("publish_id"), datos.get("upload_url")
    if not (publish_id and url):
        raise TiktokError("TikTok no devolvio donde subir el video")
    try:
        with open(video, "rb") as f:
            r = requests.put(url, data=f, timeout=600,
                             headers={"Content-Type": "video/mp4",
                                      "Content-Length": str(pesa),
                                      "Content-Range": "bytes 0-%d/%d" % (pesa - 1, pesa)})
    except requests.RequestException as e:
        raise TiktokError("no se pudo subir el video: %s" % e)
    if r.status_code >= 400:
        raise TiktokError("TikTok rechazo el video (%d): %s"
                          % (r.status_code, r.text[:300]))
    return str(publish_id)


def como_quedo(publish_id: str, token: str = "") -> Dict:
    """Que dice TikTok de esa subida. SOLO LEE."""
    token = token or acceso()
    return (_api(ESTADO, token, {"publish_id": publish_id}).get("data") or {})


def enlace_de_permiso(clave: str, redireccion: str, desafio: str,
                      estado: str = "") -> str:
    """La direccion que se abre en el navegador para dar el permiso una vez.

    `code_challenge` es PKCE y TikTok lo EXIGE para las apps de escritorio,
    que son las unicas a las que les acepta 127.0.0.1 como retorno. Las de
    tipo web piden https, o sea un servidor.
    """
    from urllib.parse import urlencode
    return "%s?%s" % (AUTORIZAR, urlencode({
        "client_key": clave, "scope": PERMISO, "response_type": "code",
        "redirect_uri": redireccion, "state": estado or "psicologia",
        "code_challenge": desafio, "code_challenge_method": "S256"}))


def canjear(codigo: str, clave: str, secreto: str, redireccion: str,
            verificador: str) -> Dict:
    """Cambia el codigo de una vez por el token de refresco, que es el que dura."""
    try:
        r = requests.post(TOKEN, timeout=30,
                          headers={"Content-Type": "application/x-www-form-urlencoded"},
                          data={"client_key": clave, "client_secret": secreto,
                                "code": codigo, "grant_type": "authorization_code",
                                "redirect_uri": redireccion,
                                "code_verifier": verificador})
    except requests.RequestException as e:
        raise TiktokError("no pude hablar con TikTok: %s" % e)
    datos = _como_json(r)
    if r.status_code >= 400 or datos.get("error"):
        raise TiktokError(_pista(str(datos.get("error_description")
                                     or datos.get("error") or r.text[:200])))
    if not datos.get("refresh_token"):
        raise TiktokError("TikTok no devolvio el token de refresco")
    return datos


def pkce() -> tuple:
    """(verificador, desafio). El verificador se guarda; el desafio viaja."""
    import hashlib
    import secrets
    verificador = secrets.token_urlsafe(64)[:128]
    # TikTok pide el desafio en HEXADECIMAL, no en base64url como casi todos
    # los demas. Mandarlo en base64 da un error que habla del codigo y no del
    # desafio, que es de los que cuestan una tarde.
    return verificador, hashlib.sha256(verificador.encode("ascii")).hexdigest()
