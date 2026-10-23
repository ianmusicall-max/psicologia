"""Hablar con Telegram: mandar texto, mandar el flyer con botones y recoger respuestas.

Es la capa de transporte y nada más. Quién decide qué se manda está en
`src/bot.py`; acá no hay ninguna regla del producto.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.telegram.org/bot%s/%s"
OFFSET = ROOT / "data" / "telegram_offset.json"


class TelegramError(RuntimeError):
    pass


def token() -> Optional[str]:
    return os.environ.get("TELEGRAM_TOKEN") or None


def chat() -> Optional[str]:
    return os.environ.get("TELEGRAM_CHAT_ID") or None


def configurado() -> bool:
    return bool(token() and chat())


def _llamar(metodo: str, archivo: Optional[Path] = None, campo: str = "photo",
            **datos) -> dict:
    t = token()
    if not t:
        raise TelegramError("Falta TELEGRAM_TOKEN en el .env")
    for k, v in list(datos.items()):
        if isinstance(v, (dict, list)):
            datos[k] = json.dumps(v)
    archivos = None
    if archivo is not None:
        archivos = {campo: open(archivo, "rb")}
    try:
        # Un video de decenas de megas tarda bastante mas que una foto.
        r = requests.post(API % (t, metodo), data=datos, files=archivos,
                          timeout=600 if campo == "video" else 60)
    finally:
        if archivos:
            archivos[campo].close()
    try:
        cuerpo = r.json()
    except ValueError:
        raise TelegramError("Telegram contestó algo que no es JSON: %s" % r.text[:200])
    if not cuerpo.get("ok"):
        raise TelegramError("Telegram dijo que no: %s" % cuerpo.get("description"))
    return cuerpo.get("result")


def _teclado(botones: Optional[List[List[Tuple[str, str]]]]):
    """De [[("Publicar", "publicar:aut-01")]] al formato de Telegram."""
    if not botones:
        return None
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in fila]
                                for fila in botones]}


# sendMessage no acepta más de 4096 caracteres y un mensaje más largo se
# RECHAZA entero: no se recorta. O sea que el informe de una semana, o la
# cuenta tema por tema con diecinueve temas, no llegarían nunca y el bot se
# vería mudo. Se parte acá, que es la capa que conoce el límite.
TOPE = 4000


def _trozos(texto: str, tope: int = TOPE) -> List[str]:
    """Parte por renglón, que es donde el corte no rompe una palabra ni una tabla."""
    if len(texto) <= tope:
        return [texto]
    trozos: List[str] = []
    actual = ""
    for linea in texto.split("\n"):
        # Un renglón más largo que el tope no debería existir, pero cortarlo a
        # lo bruto es mejor que perder el mensaje entero.
        while len(linea) > tope:
            if actual:
                trozos.append(actual)
                actual = ""
            trozos.append(linea[:tope])
            linea = linea[tope:]
        if actual and len(actual) + 1 + len(linea) > tope:
            trozos.append(actual)
            actual = linea
        else:
            actual = "%s\n%s" % (actual, linea) if actual else linea
    if actual:
        trozos.append(actual)
    return trozos


def enviar(texto: str, botones=None, destino: Optional[str] = None) -> dict:
    """El texto, partido si hace falta. Los botones van en el ÚLTIMO trozo: un
    teclado en el medio quedaría arriba de texto que todavía no se leyó."""
    partes = _trozos(texto or "")
    salida: dict = {}
    for i, parte in enumerate(partes):
        extra = {}
        teclado = _teclado(botones) if i == len(partes) - 1 else None
        if teclado:
            extra["reply_markup"] = teclado
        salida = _llamar("sendMessage", chat_id=destino or chat(), text=parte,
                         disable_web_page_preview=True, **extra)
    return salida


def enviar_foto(ruta: Path, pie: str = "", botones=None, destino: Optional[str] = None) -> dict:
    """El pie de una foto no puede pasar de 1024 caracteres: Telegram rechaza
    el mensaje entero, no lo recorta. Acá se recorta antes."""
    extra = {}
    teclado = _teclado(botones)
    if teclado:
        extra["reply_markup"] = teclado
    return _llamar("sendPhoto", archivo=Path(ruta), chat_id=destino or chat(),
                   caption=pie[:1024], **extra)


# Un bot no puede mandar archivos de mas de 50 MB. Telegram contesta con un
# error que no nombra el tamano, asi que conviene decirlo antes de subir medio
# video por una conexion lenta.
TOPE_ARCHIVO = 50 * 1024 * 1024


def enviar_video(ruta: Path, pie: str = "", destino: Optional[str] = None) -> dict:
    """Manda un mp4 al chat. Es como se mira un reel sin bajar nada."""
    ruta = Path(ruta)
    pesa = ruta.stat().st_size
    if pesa > TOPE_ARCHIVO:
        raise TelegramError(
            "el video pesa %.0f MB y un bot no puede mandar mas de %d"
            % (pesa / 1e6, TOPE_ARCHIVO // (1024 * 1024)))
    return _llamar("sendVideo", archivo=ruta, campo="video",
                   chat_id=destino or chat(), caption=pie[:1024],
                   supports_streaming=True)


def enviar_audio(ruta: Path, pie: str = "", destino: Optional[str] = None) -> dict:
    """Manda un audio al chat. Es como se comparan dos voces sin bajar nada.

    Va como `sendAudio` y no como `sendVoice`: una nota de voz de Telegram se
    reproduce a velocidad variable y se ve como un mensaje hablado, y lo que
    se quiere acá es escuchar un audio tal cual, con su nombre a la vista.
    """
    ruta = Path(ruta)
    pesa = ruta.stat().st_size
    if pesa > TOPE_ARCHIVO:
        raise TelegramError(
            "el audio pesa %.0f MB y un bot no puede mandar mas de %d"
            % (pesa / 1e6, TOPE_ARCHIVO // (1024 * 1024)))
    return _llamar("sendAudio", archivo=ruta, campo="audio",
                   chat_id=destino or chat(), caption=pie[:1024])


def responder_boton(callback_id: str, texto: str = "") -> None:
    """Le saca el relojito al botón. Sin esto, el teléfono se queda esperando."""
    _llamar("answerCallbackQuery", callback_query_id=callback_id, text=texto[:200])


# Telegram entrega los mensajes de UNA de dos maneras: o los pide el bot
# (getUpdates, que es lo que hace este) o los empuja a una URL (webhook). Las
# dos a la vez no se pueden, y si hay un webhook puesto, getUpdates contesta
# «Conflict» y el bot no recibe nada.
CONFLICTO = "can't use getupdates method while webhook is active"


def hay_conflicto_de_webhook(error: Exception) -> bool:
    return CONFLICTO in str(error).lower()


# Telegram no deja que un bot le escriba a alguien que nunca le hablo: hasta
# que la persona abre ESE bot y le manda algo, contesta «chat not found»,
# que se lee como si el chat id estuviera mal. Casi nunca lo esta.
SIN_CHAT = "chat not found"


def falta_el_empezar(error: Exception) -> bool:
    return SIN_CHAT in str(error).lower()


def quien_soy() -> dict:
    return _llamar("getMe") or {}


def webhook() -> dict:
    """A dónde está apuntando el webhook, si hay uno. {} si no hay ninguno."""
    info = _llamar("getWebhookInfo") or {}
    return info if info.get("url") else {}


def borrar_webhook() -> None:
    """Saca el webhook para que getUpdates vuelva a funcionar.

    No tira los mensajes pendientes: si el webhook estaba cortado, esos
    mensajes son lo único que quedó, y perderlos sería perder lo que alguien
    escribió mientras tanto.
    """
    _llamar("deleteWebhook", drop_pending_updates=False)


def _offset(ruta: Optional[Path] = None) -> int:
    ruta = Path(ruta or OFFSET)
    if not ruta.exists():
        return 0
    try:
        return int(json.loads(ruta.read_text(encoding="utf-8") or "{}").get("offset") or 0)
    except (json.JSONDecodeError, ValueError, TypeError):
        return 0


def _guardar_offset(valor: int, ruta: Optional[Path] = None) -> None:
    ruta = Path(ruta or OFFSET)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".parcial")
    tmp.write_text(json.dumps({"offset": valor}), encoding="utf-8")
    tmp.replace(ruta)


def recoger(espera: int = 25, ruta: Optional[Path] = None) -> List[dict]:
    """Lo que llegó desde la última vez.

    El offset se guarda en disco: si no, al arrancar de nuevo Telegram
    devolvería otra vez los mensajes de hace un rato y el bot contestaría
    cosas viejas. Se guarda ANTES de atender, porque atender puede fallar y
    un mensaje que reviente dos veces reventaría para siempre.
    """
    novedades = _llamar("getUpdates", offset=_offset(ruta), timeout=espera) or []
    if novedades:
        _guardar_offset(max(u["update_id"] for u in novedades) + 1, ruta)
    return novedades
