#!/usr/bin/env python3
"""El bot de Telegram: te muestra la frase que toca y la publica si la aprobas.

    bot.py              escucha hasta que lo cortes con Control-C
    bot.py --una-vez    atiende lo que haya llegado y sale (para un programador)
    bot.py --saludar    manda el menu al chat y sale, para probar que llega

Necesita TELEGRAM_TOKEN y TELEGRAM_CHAT_ID en el .env.

El token se saca hablandole a @BotFather en Telegram («/newbot»). El chat id
sale de escribirle algo a TU bot y abrir
https://api.telegram.org/bot<TOKEN>/getUpdates: es el numero de "chat":{"id":...}.

Nada se publica solo: este script no decide nada, solo atiende lo que mandas.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import bot, config, telegram  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--una-vez", action="store_true", help="atender lo pendiente y salir")
    ap.add_argument("--saludar", action="store_true", help="mandar el menu y salir")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    faltan = [n for n, v in (("TELEGRAM_TOKEN", telegram.token()),
                             ("TELEGRAM_CHAT_ID", telegram.chat())) if not v]
    if faltan:
        # Nombrar solo lo que falta: decir las dos cuando sobra una manda a
        # buscar un problema que no existe.
        print("Falta %s en el .env." % " y ".join(faltan))
        if "TELEGRAM_CHAT_ID" in faltan:
            print("Lo saca solo: scripts/chat_id.py --guardar")
        return 2
    pagina = config.cargar()

    if args.saludar:
        bot.menu()
        print("Menu enviado.")
        return 0

    print("Escuchando. Escribile cualquier cosa al bot para que aparezca el menu.")
    while True:
        try:
            novedades = telegram.recoger(espera=0 if args.una_vez else 25)
        except telegram.TelegramError as e:
            if telegram.hay_conflicto_de_webhook(e):
                print("Este bot tiene un webhook puesto y por eso no recibe nada.")
                print("Borralo con: scripts/chat_id.py --borrar-webhook")
                return 1
            print("Telegram: %s" % e)
            if args.una_vez:
                return 1
            time.sleep(5)
            continue
        for u in novedades:
            try:
                bot.atender(u, pagina)
            except Exception as e:                # noqa: BLE001
                # Un mensaje que revienta no puede dejar al bot mudo para
                # los que vienen detras.
                print("Se cayo atendiendo %s: %s" % (u.get("update_id"), e))
        if args.una_vez:
            print("Atendidas %d novedades." % len(novedades))
            return 0


if __name__ == "__main__":
    sys.exit(main())
