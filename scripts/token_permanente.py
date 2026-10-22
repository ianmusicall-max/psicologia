#!/usr/bin/env python3
"""Convierte el token en uno de pagina que no vence, y dice que poner en el .env.

    token_permanente.py              muestra que haria y que token saldria
    token_permanente.py --guardar    ademas lo escribe en el .env

Un token de pagina NO vence cuando se deriva de un token de usuario LARGO. El
camino es ese y no otro:

    token corto de usuario
      -> /oauth/access_token (fb_exchange_token)   = token largo de usuario
      -> /me/accounts                              = un token por pagina, sin vencimiento

Por eso, si lo que tenes es un token de PAGINA corto, este script no puede
hacerlo permanente: hay que volver al Explorador de Meta, pedir el token del
USUARIO (no el de la pagina) y correr esto con ese.

Necesita FB_APP_ID y FB_APP_SECRET en el .env: el intercambio lo firma la app.

SOLO LEE Y CAMBIA EL .env. No publica nada.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
import requests  # noqa: E402

from src import config  # noqa: E402

GRAPH = "https://graph.facebook.com/v21.0"
ENV = ROOT / ".env"
NECESARIOS = ("pages_manage_posts", "pages_read_engagement")


def _pedir(camino: str, **params) -> dict:
    try:
        r = requests.get("%s/%s" % (GRAPH, camino), params=params, timeout=30)
    except requests.RequestException as e:
        return {"error": {"message": "no se pudo llegar a Facebook: %s" % e}}
    try:
        return r.json()
    except ValueError:
        return {"error": {"message": "respuesta que no es JSON: %s" % r.text[:200]}}


def _vencimiento(token: str, app_id: str, app_secret: str) -> Optional[int]:
    """Los segundos que le quedan, 0 si no vence, None si no se pudo saber."""
    info = _pedir("debug_token", input_token=token,
                  access_token="%s|%s" % (app_id, app_secret)).get("data") or {}
    if not info:
        return None
    vence = info.get("expires_at")
    return 0 if vence in (0, None) else int(vence)


def _contar(vence: Optional[int]) -> str:
    if vence is None:
        return "no se pudo averiguar el vencimiento"
    if vence == 0:
        return "NO VENCE"
    cuando = datetime.fromtimestamp(vence, timezone.utc)
    return "vence el %s (%d dias)" % (cuando.date().isoformat(),
                                      (cuando - datetime.now(timezone.utc)).days)


def _guardar(valores: dict) -> None:
    """Reescribe esas claves del .env dejando el resto como estaba."""
    lineas = ENV.read_text(encoding="utf-8").split("\n") if ENV.exists() else []
    for clave, valor in valores.items():
        puesto = False
        for i, l in enumerate(lineas):
            if l.split("=", 1)[0].strip() == clave:
                lineas[i] = "%s=%s" % (clave, valor)
                puesto = True
                break
        if not puesto:
            lineas.append("%s=%s" % (clave, valor))
    tmp = ENV.with_suffix(".parcial")
    tmp.write_text("\n".join(lineas), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(ENV)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--guardar", action="store_true", help="escribir el resultado en el .env")
    args = ap.parse_args(argv)

    load_dotenv(ENV)
    pagina = config.cargar()
    token = pagina.fb_token
    app_id, app_secret = os.environ.get("FB_APP_ID"), os.environ.get("FB_APP_SECRET")
    if not token:
        print("Falta %s en el .env." % pagina.token_env)
        return 2
    if not (app_id and app_secret):
        print("Faltan FB_APP_ID y FB_APP_SECRET en el .env: el intercambio lo firma la app.")
        return 2

    yo = _pedir("me", fields="id,name,category", access_token=token)
    if "error" in yo:
        print("El token no sirve: %s" % yo["error"].get("message"))
        return 1

    if "category" in yo:
        # Es un token de PAGINA. Puede ya ser permanente, o no poder serlo.
        print("El token que tenes es de la PAGINA %s (id %s)." % (yo.get("name"), yo.get("id")))
        estado = _vencimiento(token, app_id, app_secret)
        print("Hoy %s." % _contar(estado))
        if estado == 0:
            print()
            print("Ya es permanente: no hay nada que convertir.")
            if pagina.fb_page_id != yo.get("id"):
                print("Pero %s dice %s y la pagina es %s: corregilo."
                      % (pagina.page_id_env, pagina.fb_page_id, yo.get("id")))
                if args.guardar:
                    _guardar({pagina.page_id_env: yo.get("id")})
                    print("Corregido en el .env.")
            return 0
        print()
        print("Para que no venza hace falta el token del USUARIO, no el de la pagina:")
        print("  1. Explorador de la API Graph, elegi tu app y 'Usuario' (no la pagina).")
        print("  2. Permisos: %s, pages_show_list." % ", ".join(NECESARIOS))
        print("  3. Pone ESE token en %s y corre esto de nuevo." % pagina.token_env)
        return 1

    # Es un token de usuario: este es el camino que da el token permanente.
    print("El token es del usuario %s (id %s)." % (yo.get("name"), yo.get("id")))
    largo = _pedir("oauth/access_token", grant_type="fb_exchange_token",
                   client_id=app_id, client_secret=app_secret, fb_exchange_token=token)
    if "error" in largo or not largo.get("access_token"):
        print("No se pudo alargar: %s" % (largo.get("error", {}).get("message") or largo))
        return 1
    usuario_largo = largo["access_token"]
    print("Token de usuario largo listo: %s." % _contar(_vencimiento(usuario_largo, app_id, app_secret)))

    cuentas = _pedir("me/accounts", fields="id,name,access_token", access_token=usuario_largo)
    paginas = cuentas.get("data") or []
    if not paginas:
        print("Ese usuario no administra ninguna pagina, o falta pages_show_list.")
        return 1

    elegida = None
    print()
    for c in paginas:
        estado = _vencimiento(c["access_token"], app_id, app_secret)
        print("  %s (id %s): %s" % (c.get("name"), c.get("id"), _contar(estado)))
        if c.get("id") == pagina.fb_page_id:
            elegida = c
    if elegida is None:
        elegida = paginas[0]
        print()
        print("Ninguna coincide con %s=%s, asi que tomo la primera: %s."
              % (pagina.page_id_env, pagina.fb_page_id, elegida.get("name")))

    valores = {pagina.page_id_env: elegida["id"], pagina.token_env: elegida["access_token"]}
    print()
    print("Esto es lo que va en el .env:")
    print("%s=%s" % (pagina.page_id_env, elegida["id"]))
    print("%s=%s" % (pagina.token_env, elegida["access_token"]))
    if args.guardar:
        _guardar(valores)
        print()
        print("Guardado. Comprobalo con scripts/revisar_token.py")
    else:
        print()
        print("Con --guardar lo escribo yo en el .env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
