"""El bot: qué botones hay y qué hace cada uno.

La regla que no se toca: **nada se publica sin que aprietes Publicar**. El bot
muestra, cuenta y recuerda; lo único que llega a Facebook sale del botón, y
hay una prueba que lo exige mandándole texto suelto.

Tampoco le hace caso a nadie más: solo atiende el chat de TELEGRAM_CHAT_ID. El
nombre de un bot se puede encontrar, así que sin ese filtro cualquiera podría
publicar en la página.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable, Optional

from . import diseno, facebook, frases, telegram
from .config import Pagina

MENU = [[("Ver la que toca", "siguiente")],
        [("Qué queda", "estado"), ("Ya salieron", "historial")]]

BIENVENIDA = ("Soy el bot de la página.\n\n"
              "Te muestro la frase que toca con su flyer y la publico cuando aprietas "
              "Publicar. Nada sale sin ese botón.")


def _de_mi(update: dict) -> bool:
    """Si esto vino del chat del dueño. Un chat que no es, se ignora."""
    mensaje = update.get("message") or (update.get("callback_query") or {}).get("message") or {}
    quien = str(((mensaje.get("chat") or {}).get("id")) or "")
    return bool(quien) and quien == str(telegram.chat() or "")


def _enlace(post_id: str) -> str:
    return "https://www.facebook.com/%s" % post_id


def menu() -> None:
    telegram.enviar(BIENVENIDA, MENU)


def _banco():
    temas = frases.leer()
    return temas, frases.publicadas()


def mostrar_siguiente(pagina: Pagina) -> Optional[frases.Frase]:
    """Manda el flyer y el texto que saldría, con los botones de decidir."""
    temas, ya = _banco()
    problemas = frases.revisar(temas, pagina)
    if problemas:
        telegram.enviar("El banco tiene %d problemas y no voy a publicar hasta que estén "
                        "arreglados. El primero:\n\n%s" % (len(problemas), problemas[0]))
        return None
    frase = frases.siguiente(temas, ya)
    if frase is None:
        telegram.enviar("Ya salieron las %d frases del banco. Toca escribir más."
                        % len(frases.todas(temas)))
        return None
    tema = frases.tema_de(temas, frase)
    ruta = diseno.dibujar(frase, tema, pagina)
    quedan = len(frases.todas(temas)) - len(ya)
    telegram.enviar_foto(ruta, "%s · capítulo %d, %s · quedan %d"
                         % (frase.id, tema.capitulo, tema.titulo, quedan))
    telegram.enviar(frases.caption(frase, tema, pagina),
                    [[("Publicar", "publicar:%s" % frase.id)],
                     [("Saltar", "saltar:%s" % frase.id)]])
    return frase


def publicar(pagina: Pagina, frase_id: str, publicar_fn: Optional[Callable] = None,
             hoy: Optional[date] = None) -> Optional[str]:
    """Publica esa frase. Es el ÚNICO camino del bot hacia Facebook.

    `publicar_fn` se resuelve acá y no en la firma: un
    `publicar_fn=facebook.publicar` por defecto se evalúa al importar, así que
    queda atado a esa función para siempre y cambiar `facebook.publicar`
    después no cambia nada. Es el mismo error que el de las rutas clavadas.
    """
    publicar_fn = publicar_fn or facebook.publicar
    temas, ya = _banco()
    if frase_id in ya:
        telegram.enviar("%s ya había salido el %s." % (frase_id, ya[frase_id]["dia"]))
        return None
    frase = frases.por_id(temas, frase_id)
    if frase is None:
        telegram.enviar("No encuentro la frase %s." % frase_id)
        return None
    tema = frases.tema_de(temas, frase)
    ruta = Path(diseno.FLYERS) / ("%s.jpg" % frase.id)
    if not ruta.exists():
        ruta = diseno.dibujar(frase, tema, pagina)
    try:
        post_id = publicar_fn(pagina, frases.caption(frase, tema, pagina), ruta)
    except Exception as e:                       # noqa: BLE001
        telegram.enviar("No se pudo publicar %s: %s" % (frase_id, e))
        return None
    frases.anotar_publicada(frase.id, hoy or date.today(), post_id, pagina.nombre)
    telegram.enviar("Publicada: %s" % _enlace(post_id))
    return post_id


def saltar(frase_id: str, hoy: Optional[date] = None) -> None:
    """La descarta sin publicarla: queda anotada para que no vuelva a tocar.

    Se anota en el mismo archivo que las publicadas, con el post vacío. Si se
    guardara aparte habría dos listas que consultar y `siguiente` miraría solo
    una, que es como una frase descartada volvería a ofrecerse sola.
    """
    temas, ya = _banco()
    if frases.por_id(temas, frase_id) is None:
        telegram.enviar("No encuentro la frase %s." % frase_id)
        return
    frases.anotar_publicada(frase_id, hoy or date.today(), "", "saltada")
    telegram.enviar("Salteada: %s no va a volver a tocar." % frase_id)


def estado() -> None:
    temas, ya = _banco()
    lineas = []
    for t in temas:
        salieron = sum(1 for f in t.frases if f.id in ya)
        lineas.append("%-14s %d de %d%s" % (t.tema, salieron, len(t.frases),
                                            "  (tu tema)" if t.eje == "nucleo" else ""))
    total = len(frases.todas(temas))
    lineas.append("")
    lineas.append("Quedan %d de %d." % (total - len(ya), total))
    telegram.enviar("\n".join(lineas))


def historial(cuantas: int = 10) -> None:
    ya = frases.publicadas()
    if not ya:
        telegram.enviar("Todavía no salió ninguna.")
        return
    ultimas = sorted(ya.items(), key=lambda kv: kv[1].get("dia") or "", reverse=True)[:cuantas]
    lineas = ["%s  %s%s" % (d.get("dia"), fid, "" if d.get("post_id") else "  (salteada)")
              for fid, d in ultimas]
    telegram.enviar("\n".join(lineas))


def atender(update: dict, pagina: Pagina, publicar_fn: Optional[Callable] = None) -> None:
    """Un mensaje o un botón. Lo que no reconoce, muestra el menú."""
    if not _de_mi(update):
        return
    boton = update.get("callback_query")
    if boton:
        dato = boton.get("data") or ""
        telegram.responder_boton(boton.get("id") or "")
        accion, _, arg = dato.partition(":")
        if accion == "siguiente":
            mostrar_siguiente(pagina)
        elif accion == "publicar":
            publicar(pagina, arg, publicar_fn)
        elif accion == "saltar":
            saltar(arg)
            mostrar_siguiente(pagina)
        elif accion == "estado":
            estado()
        elif accion == "historial":
            historial()
        else:
            menu()
        return
    # Un mensaje de texto nunca publica: abre el menú y nada más.
    menu()
