#!/usr/bin/env python3
"""Averigua tu TELEGRAM_CHAT_ID, que es el numero al que el bot te escribe.

    chat_id.py              lo muestra
    chat_id.py --guardar    ademas lo escribe en el .env

Antes de correrlo, escribile CUALQUIER COSA a tu bot desde Telegram: el chat
id solo aparece cuando hay al menos un mensaje tuyo esperando.

Necesita TELEGRAM_TOKEN en el .env. SOLO LEE; lo unico que escribe es el .env.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import entorno, telegram  # noqa: E402


def chats_de(novedades) -> dict:
    """{chat_id: como llamarlo} de todo lo que llego, sin repetir."""
    encontrados = {}
    for u in novedades or []:
        mensaje = (u.get("message") or u.get("edited_message")
                   or (u.get("callback_query") or {}).get("message") or {})
        chat = mensaje.get("chat") or {}
        if not chat.get("id"):
            continue
        nombre = " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x)
        encontrados[str(chat["id"])] = (nombre or chat.get("title")
                                        or chat.get("username") or chat.get("type") or "")
    return encontrados


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--guardar", action="store_true", help="escribirlo en el .env")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    if not telegram.token():
        print("Falta TELEGRAM_TOKEN en el .env. Te lo da @BotFather en Telegram.")
        return 2

    try:
        quien = telegram._llamar("getMe") or {}
        # Sin offset: no consume nada, asi que se puede correr las veces que haga falta.
        novedades = telegram._llamar("getUpdates", timeout=0) or []
    except telegram.TelegramError as e:
        print("Telegram: %s" % e)
        return 1

    print("El bot es @%s." % quien.get("username"))
    chats = chats_de(novedades)
    if not chats:
        print()
        print("Todavia no me escribiste. Abri Telegram, buscá @%s, apretá Empezar y"
              % quien.get("username"))
        print("mandale cualquier cosa. Despues corre esto de nuevo.")
        return 1

    for cid, nombre in chats.items():
        print("  %s  %s" % (cid, nombre))
    if len(chats) > 1:
        print()
        print("Hay mas de un chat. Elegi el tuyo y ponelo a mano en TELEGRAM_CHAT_ID.")
        return 1

    cid = list(chats)[0]
    if args.guardar:
        entorno.guardar({"TELEGRAM_CHAT_ID": cid})
        print()
        print("Guardado. Ya podes correr: scripts/bot.py")
    else:
        print()
        print("TELEGRAM_CHAT_ID=%s" % cid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
