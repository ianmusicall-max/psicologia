#!/usr/bin/env python3
"""Dice qué es el token que hay en el .env, sin publicar nada.

    revisar_token.py

Contesta las cuatro cosas que no se pueden saber mirando el token:

  1. si es un token de PÁGINA o de usuario,
  2. de qué página es, y si ese id coincide con PSI_FB_PAGE_ID,
  3. qué permisos trae,
  4. cuándo vence.

Un id de app y un id de página se ven iguales -dieciséis dígitos- y usar uno
por el otro hace que publicar falle con un error que no dice cuál de los dos
está mal. Esto lo separa.

SOLO LEE: no hay ni una llamada que publique.

Los permisos se preguntan con `debug_token`, que necesita FB_APP_ID y
FB_APP_SECRET en el .env. Con un token de página, `/me/permissions` NO sirve:
devuelve «(#100) nonexisting field», porque /me con un token de página ES la
página y una página no tiene ese campo. Sin las credenciales de la app el
script hace igual lo demás.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
import os  # noqa: E402
import requests  # noqa: E402

from src import config  # noqa: E402

GRAPH = "https://graph.facebook.com/v21.0"
# Lo que hace falta para que `frase_del_dia.py --publicar` funcione.
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


def main() -> int:
    load_dotenv(ROOT / ".env")
    pagina = config.cargar()
    token = pagina.fb_token
    if not token:
        print("No hay %s en el .env." % pagina.token_env)
        return 2

    yo = _pedir("me", fields="id,name,category", access_token=token)
    if "error" in yo:
        print("El token no sirve: %s" % yo["error"].get("message"))
        return 1

    es_pagina = "category" in yo
    print("El token es de %s: %s (id %s)"
          % ("una PÁGINA" if es_pagina else "un USUARIO", yo.get("name"), yo.get("id")))

    declarado = pagina.fb_page_id
    if es_pagina:
        if declarado == yo.get("id"):
            print("%s coincide con la página del token." % pagina.page_id_env)
        else:
            print("OJO: %s dice %s y el token es de la página %s. Publicar va a fallar."
                  % (pagina.page_id_env, declarado, yo.get("id")))
            print("     Si ese número es el id de la APP y no el de la página, hay que cambiarlo.")
    else:
        print("Con un token de usuario no se puede publicar como la página.")
        cuentas = _pedir("me/accounts", fields="id,name", access_token=token)
        for c in (cuentas.get("data") or []):
            print("  página a la que llega: %s (id %s)" % (c.get("name"), c.get("id")))
        if not (cuentas.get("data") or []):
            print("  y no lista ninguna página: revisá los permisos o el usuario.")
        print("El token de PÁGINA se saca del Explorador de Meta eligiendo la página,")
        print("o con GET /me/accounts, que devuelve uno por página.")

    app_id, app_secret = os.environ.get("FB_APP_ID"), os.environ.get("FB_APP_SECRET")
    if not (app_id and app_secret):
        print()
        print("Sin FB_APP_ID y FB_APP_SECRET en el .env no puedo ver permisos ni vencimiento.")
        return 0 if es_pagina else 1

    info = _pedir("debug_token", input_token=token,
                  access_token="%s|%s" % (app_id, app_secret)).get("data") or {}
    if not info:
        print("No pude leer debug_token: revisá FB_APP_ID y FB_APP_SECRET.")
        return 1

    vence = info.get("expires_at")
    if vence in (0, None):
        print("No vence.")
    else:
        cuando = datetime.fromtimestamp(vence, timezone.utc)
        dias = (cuando - datetime.now(timezone.utc)).days
        print("Vence el %s (%d días)." % (cuando.date().isoformat(), dias))

    scopes = info.get("scopes") or []
    print("Permisos: %s" % (", ".join(scopes) or "ninguno"))
    faltan = [p for p in NECESARIOS if p not in scopes]
    if faltan:
        print("FALTA para publicar: %s" % ", ".join(faltan))
        print("Se arregla generando el token de nuevo con esos permisos tildados.")
        return 1
    print("Tiene lo que hace falta para publicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
