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

CON VARIAS PAGINAS hay que decir cual: `--pagina <id>` o `--pagina <parte del
nombre>`. Si no se dice y PSI_FB_PAGE_ID esta vacio, el script PARA y las
lista. No elige la primera: elegir sola es como se termina publicando en la
pagina equivocada, y un post en la pagina equivocada ya salio.

El token largo de usuario queda guardado como FB_USER_TOKEN, asi que cambiar
de pagina despues es correr esto de nuevo con otro `--pagina`, sin volver al
Explorador de Meta.

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

from src import config, entorno, facebook  # noqa: E402

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


def _sin_acentos(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn").lower()


def elegir_pagina(paginas: list, pedido: Optional[str], declarado: Optional[str]):
    """Cual de las paginas del usuario, o None si hay que preguntar.

    Devuelve (pagina, motivo). Con `pedido` busca por id exacto o por parte
    del nombre; sin pedido usa el id declarado en el .env; y si no hay ninguno
    de los dos, solo decide cuando hay UNA sola pagina.

    Nunca cae en «tomo la primera». Esa era la version anterior y dejo el .env
    apuntando a una pagina que no era, con el token correcto: el error no se
    ve hasta que el post sale publicado en otro lado.
    """
    if pedido:
        exacto = [p for p in paginas if p.get("id") == pedido]
        if exacto:
            return exacto[0], "coincide el id"
        clave = _sin_acentos(pedido)
        porNombre = [p for p in paginas if clave in _sin_acentos(p.get("name") or "")]
        if len(porNombre) == 1:
            return porNombre[0], "coincide el nombre"
        if len(porNombre) > 1:
            return None, "«%s» coincide con mas de una pagina" % pedido
        return None, "ninguna pagina coincide con «%s»" % pedido
    if declarado:
        exacto = [p for p in paginas if p.get("id") == declarado]
        if exacto:
            return exacto[0], "es la que ya estaba en el .env"
        return None, "la pagina %s del .env no esta entre las tuyas" % declarado
    if len(paginas) == 1:
        return paginas[0], "es la unica"
    return None, "tenes %d paginas y ninguna elegida" % len(paginas)


def _guardar(valores: dict) -> None:
    entorno.guardar(valores, ENV)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--guardar", action="store_true", help="escribir el resultado en el .env")
    ap.add_argument("--pagina", help="id de la pagina, o parte de su nombre")
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

    yo = facebook.identificar(token, app_id, app_secret)
    if "error" in yo:
        print("El token no sirve: %s" % yo["error"])
        return 1

    guardado = os.environ.get("FB_USER_TOKEN")
    if yo["tipo"] == "pagina" and guardado:
        # Ya se hizo la conversion antes: con el token de usuario guardado se
        # puede cambiar de pagina sin volver al Explorador de Meta.
        quien = facebook.identificar(guardado, app_id, app_secret)
        if quien.get("tipo") == "usuario":
            print("El .env ya tiene el token de una pagina; uso el de usuario guardado "
                  "(%s) para elegir." % quien.get("nombre"))
            token, yo = guardado, quien

    if yo["tipo"] == "pagina":
        # Es un token de PAGINA. Puede ya ser permanente, o no poder serlo.
        print("El token que tenes es de la PAGINA %s (id %s)." % (yo.get("nombre"), yo.get("id")))
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
    print("El token es del usuario %s (id %s)." % (yo.get("nombre"), yo.get("id")))
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

    print()
    for c in paginas:
        print("  %s (id %s): %s"
              % (c.get("name"), c.get("id"), _contar(_vencimiento(c["access_token"], app_id, app_secret))))

    elegida, motivo = elegir_pagina(paginas, args.pagina, pagina.fb_page_id)
    if elegida is None:
        print()
        print("NO elijo yo: %s." % motivo)
        print("Corre esto otra vez agregando cual, por id o por nombre:")
        print("  scripts/token_permanente.py --guardar --pagina %s" % (paginas[0].get("id")))
        if args.guardar:
            _guardar({"FB_USER_TOKEN": usuario_largo})
            print()
            print("Guarde el token de usuario largo como FB_USER_TOKEN, asi la proxima")
            print("corrida no tiene que volver al Explorador de Meta.")
        return 1
    print()
    print("Elegida: %s (%s)." % (elegida.get("name"), motivo))

    valores = {pagina.page_id_env: elegida["id"], pagina.token_env: elegida["access_token"],
               "FB_USER_TOKEN": usuario_largo}
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
