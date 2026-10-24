#!/usr/bin/env python3
"""Da el permiso de YouTube UNA vez y lo guarda en el .env.

    python3 scripts/youtube_token.py

Abre el navegador, elegís la cuenta del canal, y el permiso queda escrito en
el .env como YT_REFRESH_TOKEN. No hay que copiar ni pegar ningún código: el
navegador se lo devuelve solo a este script.

Antes de correrlo hacen falta dos cosas en el .env, que salen de la consola de
Google (console.cloud.google.com):

    YT_CLIENT_ID=...
    YT_CLIENT_SECRET=...

Se piden como cliente de tipo **Aplicación de escritorio**. Ese tipo es el que
permite que la respuesta vuelva a 127.0.0.1 sin registrar ninguna dirección,
que es lo que hace que esto sea un comando y no un trámite.

NO PUBLICA NADA. Solo pide el permiso.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from src import entorno, youtube  # noqa: E402

# Cualquier puerto libre sirve: un cliente de escritorio acepta la vuelta a
# 127.0.0.1 en el puerto que sea. Se fija uno para que la dirección que se
# imprime sea siempre la misma, y si está ocupado se prueba el siguiente.
PUERTO = 8731
PUERTOS = 5

# Cuánto se espera a que vuelvas del navegador. Cinco minutos alcanzan para
# elegir la cuenta y pasar por la pantalla de «app sin verificar».
ESPERA = 300

GRACIAS = (b"<!doctype html><meta charset=utf-8>"
           b"<body style='font:16px -apple-system;padding:3em'>"
           b"<h2>Listo.</h2><p>Ya pod\xc3\xa9s cerrar esta pesta\xc3\xb1a y "
           b"volver a la terminal.</p>")

_LLEGO = {}


class _Vuelta(BaseHTTPRequestHandler):
    """Atiende la única visita que importa: la que trae el código."""

    def do_GET(self):  # noqa: N802  (lo nombra http.server)
        q = parse_qs(urlparse(self.path).query)
        if "code" in q or "error" in q:
            _LLEGO["codigo"] = (q.get("code") or [""])[0]
            _LLEGO["error"] = (q.get("error") or [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(GRACIAS)

    def log_message(self, *a):
        # Sin esto, el navegador ensucia la terminal con una línea por pedido
        # -el favicon incluido- justo cuando hay que leer una instrucción.
        pass


def servidor(puerto: int = PUERTO, cuantos: int = PUERTOS):
    """Levanta el que escucha la vuelta, probando puertos si están ocupados."""
    ultimo = None
    for p in range(puerto, puerto + cuantos):
        try:
            return HTTPServer(("127.0.0.1", p), _Vuelta)
        except OSError as e:
            ultimo = e
    raise youtube.YoutubeError("no pude escuchar en 127.0.0.1:%d-%d (%s)"
                               % (puerto, puerto + cuantos - 1, ultimo))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--espera", type=int, default=ESPERA)
    ap.add_argument("--sin-navegador", action="store_true",
                    help="no lo abre; imprime la direccion para pegarla")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    cliente = os.environ.get(youtube.CLIENTE)
    secreto = os.environ.get(youtube.SECRETO)
    if not cliente or not secreto:
        # CUAL falta, no «uno de los dos»: son dos pasos distintos en la
        # consola de Google, y con los dos nombres en el mensaje hay que ir a
        # mirar el .env para saber cual de los dos se escribio.
        print("Falta %s en el .env."
              % " y ".join(c for c in (youtube.CLIENTE, youtube.SECRETO)
                            if not os.environ.get(c)))
        print()
        print("Salen de console.cloud.google.com:")
        print("  1. Crea un proyecto (o usa uno que tengas).")
        print("  2. APIs y servicios -> Habilitar -> YouTube Data API v3.")
        print("  3. Credenciales -> Crear credenciales -> ID de cliente de")
        print("     OAuth -> tipo **Aplicacion de escritorio**.")
        print("  4. Pega el id y el secreto en el .env, uno por renglon.")
        print()
        print("Pegalos en el ARCHIVO, no en el chat: una clave que pasa por")
        print("una conversacion queda ahi para siempre.")
        return 1

    try:
        httpd = servidor()
    except youtube.YoutubeError as e:
        print(e)
        return 1
    redireccion = "http://127.0.0.1:%d" % httpd.server_address[1]
    enlace = youtube.enlace_de_permiso(cliente, redireccion)

    print("Abriendo el navegador para que des el permiso...")
    print()
    print("Dos cosas que vas a ver y son normales:")
    print("  - «Google no ha verificado esta aplicacion»: Configuracion")
    print("    avanzada -> Ir a (no verificado). Es TU app.")
    print("  - Te pide elegir cuenta: tiene que ser la del CANAL.")
    print()
    if args.sin_navegador or not webbrowser.open(enlace):
        print("Pega esto en el navegador:")
        print()
        print(enlace)
        print()

    # Una vuelta por pedido: el navegador manda el favicon aparte, y si se
    # atendiera un pedido solo el codigo podria quedar sin leer. Y el plazo se
    # mide por RELOJ y no por pedidos atendidos: un favicon que llega no
    # significa que hayas vuelto, y contarlo cortaria la espera de golpe.
    limite = time.time() + args.espera
    httpd.timeout = 5
    while "codigo" not in _LLEGO and "error" not in _LLEGO:
        httpd.handle_request()
        if time.time() > limite:
            print("No volviste en %d segundos." % args.espera)
            return 1
    httpd.server_close()

    if _LLEGO.get("error"):
        print("Google dijo: %s" % _LLEGO["error"])
        if _LLEGO["error"] == "access_denied":
            print("Es lo que pasa si apretaste Cancelar, o si la app esta en")
            print("modo Prueba y esa cuenta no esta en la lista de usuarios")
            print("de prueba.")
        return 1

    try:
        datos = youtube.canjear(_LLEGO["codigo"], cliente, secreto, redireccion)
    except youtube.YoutubeError as e:
        print("No pude cambiar el codigo por el permiso: %s" % e)
        return 1

    # El de refresco es el unico que se guarda. El de acceso dura una hora:
    # guardarlo seria dejar una credencial tirada que ademas no sirve.
    entorno.guardar({youtube.REFRESCO: datos["refresh_token"]})
    print("Listo. Guarde %s en el .env." % youtube.REFRESCO)
    print()
    print("Ya se puede subir:")
    print("  python3 scripts/publicar_youtube.py data/reels/<archivo>.mp4")
    print()
    print("Pide DOS permisos: subir videos y administrar el canal. El segundo")
    print("es solo para meter el video en la lista «%s»:" % youtube.PLAYLIST)
    print("subir no alcanza para eso.")
    print()
    print("Si la app quedo en modo «Prueba», este permiso se vence en 7 dias.")
    print("Para que no se venza: pantalla de consentimiento -> Publicar app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
