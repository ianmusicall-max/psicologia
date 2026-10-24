"""El bot: qué botones hay y qué contesta cada uno.

La regla que no se toca: **nada se publica sin que aprietes Publicar**. Las
tareas del menú muestran, cuentan y comprueban; lo único que llega a Facebook
sale de ese botón, y hay dos pruebas que lo exigen: una manda texto suelto y
otra lee el AST de este archivo y cuenta los caminos que publican.

Tampoco le hace caso a nadie más: solo atiende el chat de TELEGRAM_CHAT_ID. El
nombre de un bot se puede encontrar, así que sin ese filtro cualquiera podría
publicar en la página.

**El menú sale de UNA tabla** (`TAREAS`), como el bot de salud: la etiqueta del
botón, cómo se nombra la tarea en una frase, qué contesta y si tarda, todo en
el mismo renglón. Repartido entre una lista de botones y un `if` largo, un
botón puede quedar sin tarea o una tarea sin botón, y las dos cosas se
descubren apretando. Hay una prueba que exige que los dos lados coincidan.

A diferencia del bot de salud, acá cada tarea corre DENTRO del bot y no en su
propia unidad de systemd. No es pereza: ese bot vive en un servidor y lanza
tandas que tardan media hora y cuestan plata, así que tienen que sobrevivir a
que el lector se reinicie. Acá no hay ninguna API paga y la tarea más lenta le
pregunta los números a Facebook post por post, que son segundos; el bot corre
en la misma computadora de quien está esperando la respuesta. Las que tardan
avisan antes de empezar, que es lo que esa separación compraba.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

from . import diario, diseno, facebook, frases, libro, medir, parrilla, telegram
from .config import Pagina

# Con menos de esto se avisa: escribir un capítulo nuevo lleva su tiempo y
# conviene enterarse antes de que el banco se termine, no el día que pasa.
AVISAR_DIAS = 7

# Lo que dice tiene que ser verdad, y desde que el turno de GitHub publica las
# frases cada hora esto decia justo lo contrario: que las frases no salían
# solas y que el video sí. Hoy es al revés, y el video es el único que
# pregunta (pedido del 2026-10-24).
BIENVENIDA = ("Soy el bot de la página. ¿Qué hago?\n\n"
              "Las frases salen solas, cada una en su hora de la parrilla. El "
              "video es el único que te pregunta: se arma, te llega acá y "
              "sale recién cuando aprietes Publicar.")


def _de_mi(update: dict) -> bool:
    """Si esto vino del chat del dueño. Un chat que no es, se ignora."""
    mensaje = update.get("message") or (update.get("callback_query") or {}).get("message") or {}
    quien = str(((mensaje.get("chat") or {}).get("id")) or "")
    return bool(quien) and quien == str(telegram.chat() or "")


def _enlace(post_id: str) -> str:
    return "https://www.facebook.com/%s" % post_id


def _y(cosas: list) -> str:
    """«las 08 y las 12», no «las 08, 12». Se lee en el teléfono."""
    if len(cosas) <= 1:
        return "".join(cosas)
    return "%s y %s" % (", ".join(cosas[:-1]), cosas[-1])


def _banco():
    temas = frases.leer()
    return temas, frases.publicadas()


def _estilo_de_ahora(pagina: Pagina, ya: dict, ahora: datetime) -> str:
    """El modelo que le toca a este turno, con la misma cuenta que el publicador
    de cada hora: las horas de HOY y el corrimiento por fecha."""
    desde = frases.primer_dia(ya) or ahora.date()
    horas = parrilla.horas_del_dia(pagina, desde, ahora.date())
    return diseno.estilo_de(pagina, ahora.date(), ahora.hour, horas)


# ---------------------------------------------------------------------------
# Las tareas del menú. Cada una recibe la página y devuelve el texto a
# contestar, o None si ya mandó lo suyo (las que mandan fotos).
# ---------------------------------------------------------------------------

def mostrar_siguiente(pagina: Pagina, ahora: Optional[datetime] = None) -> Optional[frases.Frase]:
    """Manda el flyer y el texto que saldría, con los botones de decidir."""
    ahora = ahora or datetime.now()
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
    estilo = _estilo_de_ahora(pagina, ya, ahora)
    ruta = diseno.dibujar(frase, tema, pagina, estilo=estilo)
    quedan = len(frases.todas(temas)) - len(ya)
    telegram.enviar_foto(ruta, "%s · capítulo %d, %s · modelo %s · quedan %d"
                         % (frase.id, tema.capitulo, tema.titulo, estilo, quedan))
    # El modelo viaja en el botón: lo que se publica es el flyer que viste, y
    # no el que le toque a la hora en que aprietes. Son 25 caracteres de los 64
    # que Telegram admite en un callback_data.
    telegram.enviar(frases.caption(frase, tema, pagina),
                    [[("Publicar", "publicar:%s:%s" % (frase.id, estilo))],
                     [("Saltar", "saltar:%s" % frase.id)]])
    return frase


def hoy(pagina: Pagina, ahora: Optional[datetime] = None) -> str:
    """Qué sale hoy: cada hora con su modelo y si ya salió. SOLO LEE.

    Es la pregunta que la rampa volvió difícil de contestar de memoria: la
    cantidad de posts cambia por etapa y el modelo se corre un lugar cada día,
    así que ni el usuario ni yo podemos saber de cabeza qué toca hoy.
    """
    ahora = ahora or datetime.now()
    dia = ahora.date()
    temas, ya = _banco()
    desde = frases.primer_dia(ya) or dia
    horas = parrilla.horas_del_dia(pagina, desde, dia)
    de_hoy = {fid: d for fid, d in ya.items()
              if d.get("dia") == dia.isoformat() and d.get("post_id")}
    salieron = {d.get("hora"): fid for fid, d in de_hoy.items() if d.get("hora") is not None}

    lineas = ["Hoy %s, día %d de la rampa: %d posts."
              % (dia.isoformat(), parrilla.dia_de_la_prueba(desde, dia), len(horas)), ""]
    for h in horas:
        if h in salieron:
            marca = "salió · %s" % salieron[h]
        elif h > ahora.hour:
            marca = "viene"
        else:
            marca = "no salió"
        lineas.append("%02d:00  %-9s %s" % (h, diseno.estilo_de(pagina, dia, h, horas), marca))

    atrasadas = [h for h in horas if h < ahora.hour and h not in salieron]
    if atrasadas:
        lineas += ["", "Ya pasaron %s y no salió nada. Si el programador horario "
                   "todavía no está puesto, las frases no salen solas: tocame «Ver la "
                   "que toca» y aprobá." % _y(["las %02d" % h for h in atrasadas])]
    sin_hora = len(de_hoy) - len(salieron)
    if sin_hora:
        lineas += ["", "Y %d que salieron hoy sin hora anotada." % sin_hora]

    quedan = len(frases.todas(temas)) - len(ya)
    lineas += ["", "Quedan %d frases sin publicar." % quedan]
    filas = parrilla.calendario(pagina, desde, quedan)
    if filas:
        ultimo = filas[-1]
        lineas.append("El banco alcanza para más de %d días." % len(filas)
                      if ultimo["quedan"] else
                      "El banco alcanza hasta el %s." % ultimo["dia"].isoformat())
    return "\n".join(lineas)


def estado(pagina: Optional[Pagina] = None) -> str:
    """Cuántas quedan, tema por tema. SOLO LEE."""
    temas, ya = _banco()
    lineas = []
    for t in temas:
        salieron = sum(1 for f in t.frases if f.id in ya)
        lineas.append("%-14s %d de %d%s" % (t.tema, salieron, len(t.frases),
                                            "  (tu tema)" if t.eje == "nucleo" else ""))
    total = len(frases.todas(temas))
    quedan = total - len(ya)
    lineas.append("")
    lineas.append("Quedan %d de %d." % (quedan, total))
    # Cuántos días aguanta, no cuántas frases: con la rampa el mismo número de
    # frases dura muy distinto, y lo que hace falta saber es cuándo escribir
    # más. Sin este aviso, que el banco se agote se descubre el día que el bot
    # dice que no quedan.
    dias = parrilla.calendario(pagina, frases.primer_dia(ya) or date.today(), quedan) \
        if pagina else []
    if dias:
        lineas.append("Alcanzan para %d días, hasta el %s."
                      % (len(dias), dias[-1]["dia"].isoformat()))
        if len(dias) <= AVISAR_DIAS:
            lineas.append("")
            lineas.append("Quedan menos de %d días de banco: es hora de escribir "
                          "más frases." % (AVISAR_DIAS + 1))
    return "\n".join(lineas)


def historial(pagina: Optional[Pagina] = None, cuantas: int = 10) -> str:
    """Las últimas que salieron. SOLO LEE."""
    ya = frases.publicadas()
    if not ya:
        return "Todavía no salió ninguna."
    ultimas = sorted(ya.items(), key=lambda kv: kv[1].get("dia") or "", reverse=True)[:cuantas]
    return "\n".join("%s  %s%s%s" % (d.get("dia"), fid,
                                     "  %s" % d["estilo"] if d.get("estilo") else "",
                                     "" if d.get("post_id") else "  (salteada)")
                     for fid, d in ultimas)


def informe(pagina: Pagina) -> str:
    """Qué rindió cada modelo, eje, tema y hora. SOLO LEE.

    El texto lo arma `medir.informe`, el mismo que imprime `scripts/medir.py`.
    """
    ya = frases.publicadas()
    return medir.informe(pagina, {k: v for k, v in ya.items() if v.get("post_id")})


def banco(pagina: Pagina) -> str:
    """Si el banco pasa la línea editorial entera. SOLO LEE.

    Hasta ahora un banco roto se descubría apretando «Ver la que toca», que se
    niega a mostrar nada: el mensaje llegaba cuando ya querías publicar.
    """
    temas = frases.leer()
    problemas = frases.revisar(temas, pagina)
    cuantas, cuantos = len(frases.todas(temas)), len(temas)
    if not problemas:
        return ("El banco está bien: %d frases en %d temas y ninguna rebotada.\n\n"
                "Se revisa lo mismo que antes de publicar: el largo, las palabras "
                "destacadas, la fuente, los cinco hashtags y la línea editorial."
                % (cuantas, cuantos))
    lineas = ["El banco tiene %d problemas, así que no voy a publicar hasta que "
              "estén arreglados." % len(problemas), ""]
    lineas += ["· %s" % p for p in problemas[:10]]
    if len(problemas) > 10:
        lineas.append("...y %d más." % (len(problemas) - 10))
    return "\n".join(lineas)


def permisos(pagina: Pagina) -> str:
    """Si la página está en condiciones de publicar. SOLO PREGUNTA.

    Es la respuesta a «¿sigue conectado?», que hasta ahora solo se podía
    averiguar con `revisar_token.py` y `revisar_instagram.py` en una terminal.
    Las dos preguntas van juntas porque el síntoma es el mismo -no sale nada- y
    la causa puede ser cualquiera de las dos.

    El token NUNCA se escribe en el chat: se dice de quién es y qué permisos
    tiene, que es lo que hace falta para saber qué arreglar.
    """
    if not (pagina.fb_page_id and pagina.fb_token):
        faltan = [n for n, v in ((pagina.page_id_env, pagina.fb_page_id),
                                 (pagina.token_env, pagina.fb_token)) if not v]
        return "Falta %s en el .env, así que no puedo publicar." % " y ".join(faltan)

    app_id, app_secret = os.environ.get("FB_APP_ID"), os.environ.get("FB_APP_SECRET")
    quien = facebook.identificar(pagina.fb_token, app_id, app_secret)
    if "error" in quien:
        return ("Facebook no acepta el token: %s\n\nSe renueva con "
                "scripts/token_permanente.py, y eso pide la computadora."
                % quien["error"])
    lineas = ["Facebook: %s, token de %s." % (quien.get("nombre") or "?",
                                              quien.get("tipo") or "tipo desconocido")]
    if quien.get("tipo") == "usuario":
        lineas.append("OJO: es un token de USUARIO y hace falta uno de PÁGINA. "
                      "Se convierte con scripts/token_permanente.py --guardar.")

    if not pagina.instagram:
        lineas += ["Instagram: apagado en config/pagina.yaml."]
        return "\n".join(lineas)

    from . import instagram
    cuenta = instagram.cuenta_vinculada(pagina)
    if "error" in cuenta:
        lineas.append("Instagram: no pude preguntar (%s)." % cuenta["error"])
        return "\n".join(lineas)
    if cuenta.get("id"):
        lineas.append("Instagram: @%s vinculado." % (cuenta.get("usuario") or "?"))
    else:
        lineas.append("Instagram: NINGUNA cuenta vinculada a la página. Se vincula "
                      "desde la configuración de la página en Facebook.")
    if not (app_id and app_secret):
        lineas.append("Permisos: no pude mirarlos, faltan FB_APP_ID y FB_APP_SECRET.")
        return "\n".join(lineas)
    scopes = instagram.scopes_del_token(pagina, app_id, app_secret)
    if scopes is None:
        # None y [] no son lo mismo: [] es «no tiene ninguno» y None es «no pude
        # averiguarlo», y confundirlos manda a regenerar un token que estaba bien.
        lineas.append("Permisos: no pude mirarlos, revisá FB_APP_ID y FB_APP_SECRET.")
        return "\n".join(lineas)
    faltantes = instagram.permisos_que_faltan(scopes)
    if faltantes:
        lineas.append("Permisos: FALTAN %s. Hay que generar el token otra vez con "
                      "esos tildados, y eso pide la computadora." % ", ".join(faltantes))
    else:
        lineas.append("Permisos: están los dos de Instagram.")
    return "\n".join(lineas)


def modelos(pagina: Pagina) -> str:
    """Los cuatro modelos con la misma frase, para mirarlos en el teléfono.

    Van a `diseno.MUESTRAS` y no a la carpeta de flyers: esa es la carpeta de
    la que sale lo que se publica.
    """
    temas, ya = _banco()
    todas = frases.todas(temas)
    frase = frases.siguiente(temas, ya) or (todas[0] if todas else None)
    if frase is None:
        return "No hay ninguna frase en el banco."
    tema = frases.tema_de(temas, frase)
    nombres = sorted(diseno.ESTILOS)
    for estilo in nombres:
        # escala 1 y no 2: es para mirar, y el de publicar pesa cuatro veces más.
        img = diseno.render(frase, tema, pagina, escala=1, estilo=estilo)
        ruta = diseno.guardar(img, Path(diseno.MUESTRAS) / ("%s-%s.jpg" % (estilo, frase.id)))
        telegram.enviar_foto(ruta, estilo)
    return ("Los %d modelos con la misma frase (%s). En la prueba sale uno "
            "distinto en cada post del día; cuál le toca a cada hora está en "
            "«Qué sale hoy»." % (len(nombres), frase.id))


def como_va_el_libro(pagina: Optional[Pagina] = None) -> str:
    """El manuscrito que crece solo con el banco. SOLO LEE: no reescribe el
    archivo, que es trabajo de `scripts/armar_libro.py` y va a un commit."""
    temas = frases.leer()
    texto = libro.borrador(temas)
    lineas = ["El libro: %d capítulos, %d frases, %d palabras."
              % (len(temas), len(frases.todas(temas)), len(texto.split()))]
    ruta = Path(libro.BORRADOR)
    guardado = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    if guardado == texto:
        lineas.append("El borrador versionado está al día con el banco.")
    else:
        lineas.append("El borrador versionado quedó viejo: hay que correr "
                      "scripts/armar_libro.py y subirlo.")
    nucleo = [t for t in temas if t.eje == "nucleo"]
    lineas.append("%d capítulos son de los temas de la página y %d de apoyo."
                  % (len(nucleo), len(temas) - len(nucleo)))
    return "\n".join(lineas)


def video(pagina: Optional[Pagina] = None) -> str:
    """Arma el reel del día y te lo manda para que lo apruebes.

    Es el MISMO camino que el turno de las 18 (`scripts/reel_del_dia.py`), no
    una copia: si cada uno hiciera lo suyo, el día que esto cambie se arregla
    uno y el otro se queda con la forma vieja.

    Se lanza aparte y no se espera: armar un reel tarda varios minutos y el
    bot tiene que seguir contestando. `start_new_session` lo desprende, así
    que cortar el bot no se lleva el video a medio armar.
    """
    import subprocess
    import sys

    ya = diario.ya_salio_hoy()
    if ya:
        donde = "\n".join("  %s: %s" % (c, d)
                          for c, d in (ya.get("salidas") or {}).items())
        # Un reel que armaste y no aprobaste tambien queda anotado, y decir
        # que «ya salió» seria mentir: no salió a ningún lado.
        cabeza = ("Hoy ya salió el video: %s" if ya.get("publicado", True)
                  else "Hoy ya armé un video y no salió: %s")
        return ((cabeza % (ya.get("titulo") or "?")) + "\n%s\n\nSi querés "
                "otro, se dispara desde Actions con «Armar otro aunque hoy ya "
                "haya salido»." % donde)
    if diario.corriendo():
        return "Ya hay uno armándose. Tarda unos minutos; te aviso cuando esté."

    guion = Path(__file__).resolve().parent.parent / "scripts" / "reel_del_dia.py"
    subprocess.Popen([sys.executable, str(guion)], cwd=str(guion.parent.parent),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return ("Voy a armar el video. Tarda unos minutos: te llega acá con dos "
            "botones y no sale a ningún lado hasta que aprietes Publicar.")


# clave: (etiqueta del botón, cómo se nombra en una frase, qué contesta, tarda)
# El orden es el del menú: primero la que se usa todos los días.
TAREAS = {
    "siguiente": ("Ver la que toca", "la que toca", mostrar_siguiente, False),
    "video": ("Armar el video", "el video del día", video, False),
    "hoy": ("Qué sale hoy", "la parrilla de hoy", hoy, False),
    "estado": ("Qué queda", "lo que queda", estado, False),
    "historial": ("Ya salieron", "las últimas que salieron", historial, False),
    "informe": ("Cómo venimos", "el informe", informe, True),
    "banco": ("Revisar el banco", "la revisión del banco", banco, False),
    "permisos": ("¿Puedo publicar?", "la comprobación de los permisos", permisos, True),
    "modelos": ("Ver los 4 modelos", "los cuatro modelos", modelos, True),
    "libro": ("Cómo va el libro", "el libro", como_va_el_libro, False),
}

# Lo que escrito a secas abre el menú. Sin acentos también, que en el teléfono
# es fácil que no salgan. Cualquier otra cosa también lo abre: un mensaje de
# texto nunca hace nada más que eso.
PALABRAS = ("menu", "menú", "ayuda", "hola", "opciones", "que hago", "start")


def menu() -> None:
    """Los botones, armados de la tabla: un botón por tarea y ninguno de más."""
    filas = [[(etiqueta, clave)] for clave, (etiqueta, _, _, _) in TAREAS.items()]
    telegram.enviar(BIENVENIDA, filas)


def correr(clave: str, pagina: Pagina) -> None:
    """Llama una tarea y contesta lo que devuelve."""
    tarea = TAREAS.get(clave)
    if tarea is None:
        menu()
        return
    _, nombre, funcion, tarda = tarea
    if tarda:
        telegram.enviar("Voy con %s. Dame un minuto." % nombre)
    try:
        salida = funcion(pagina)
    except Exception as e:                       # noqa: BLE001
        # Una tarea que revienta no puede dejar al bot mudo: sin esto, el
        # teléfono se queda sin respuesta y no hay ningún log que mirar.
        telegram.enviar("No pude con %s: %s" % (nombre, e))
        return
    # Solo se contesta TEXTO: las tareas que mandan fotos devuelven su propio
    # resumen, y `mostrar_siguiente` devuelve la frase que ofreció -le sirve a
    # quien la llame desde Python-, que mandada al chat imprimiría el objeto.
    if isinstance(salida, str) and salida:
        telegram.enviar(salida)


def _como_publica(pagina: Pagina, hora: Optional[int] = None) -> Callable:
    """Facebook solo, o Facebook e Instagram si a esa hora le toca.

    La hora importa desde que a Instagram van dos de los ocho posts: sin
    mirarla, el botón publicaría en Instagram una frase que el turno de esa
    hora no habría publicado ahí.
    """
    if pagina.instagram_en(datetime.now().hour if hora is None else hora):
        from . import instagram
        return instagram.publicar_las_dos
    return facebook.publicar


def publicar(pagina: Pagina, frase_id: str, publicar_fn: Optional[Callable] = None,
             ahora: Optional[datetime] = None, estilo: Optional[str] = None) -> Optional[str]:
    """Publica esa frase. Es el ÚNICO camino del bot hacia Facebook.

    `publicar_fn` se resuelve acá y no en la firma: un
    `publicar_fn=facebook.publicar` por defecto se evalúa al importar, así que
    queda atado a esa función para siempre y cambiar `facebook.publicar`
    después no cambia nada. Es el mismo error que el de las rutas clavadas.
    """
    ahora = ahora or datetime.now()
    publicar_fn = publicar_fn or _como_publica(pagina, ahora.hour)
    temas, ya = _banco()
    if frase_id in ya:
        telegram.enviar("%s ya había salido el %s." % (frase_id, ya[frase_id]["dia"]))
        return None
    frase = frases.por_id(temas, frase_id)
    if frase is None:
        telegram.enviar("No encuentro la frase %s." % frase_id)
        return None
    tema = frases.tema_de(temas, frase)
    estilo = estilo or _estilo_de_ahora(pagina, ya, ahora)
    # Se vuelve a dibujar en vez de reusar el archivo que dejó
    # `mostrar_siguiente`: el dibujo es determinista y tarda un segundo, y así
    # el flyer que sale es siempre el del modelo que se anota. Reusando el
    # archivo, dos pulsaciones de «Ver la que toca» en horas distintas dejan en
    # disco el flyer de la segunda, y apretar el Publicar de la primera subiría
    # un modelo y anotaría otro.
    ruta = diseno.dibujar(frase, tema, pagina, estilo=estilo)
    try:
        salida = publicar_fn(pagina, frases.caption(frase, tema, pagina), ruta)
    except Exception as e:                       # noqa: BLE001
        telegram.enviar("No se pudo publicar %s: %s" % (frase_id, e))
        return None
    if isinstance(salida, dict):
        post_id, en_ig, fallo_ig = (salida.get("post_id") or "", salida.get("instagram") or "",
                                    salida.get("error_instagram") or "")
    else:
        post_id, en_ig, fallo_ig = str(salida), "", ""
    # Los mismos datos que anota el publicador de cada hora, y no es un
    # detalle: `medir.por` saltea los renglones a los que les falta el campo,
    # así que un post publicado desde el teléfono no aparecía en NINGUNA tabla
    # del informe. Mientras el programador horario no esté puesto, el teléfono
    # es el único camino: el informe de la primera semana habría salido vacío.
    frases.anotar_publicada(frase.id, ahora.date(), post_id, pagina.nombre, extra={
        "hora": ahora.hour, "tema": tema.tema, "eje": tema.eje,
        "estilo": estilo, "instagram": en_ig,
    })
    aviso = "Publicada: %s" % _enlace(post_id)
    if en_ig:
        aviso += "\nTambién en Instagram."
    elif fallo_ig:
        # Facebook ya salió: esto se avisa, no se trata como turno fallido.
        aviso += "\nEn Instagram NO salió: %s" % fallo_ig
    telegram.enviar(aviso)
    return post_id


def aprobar_el_reel(arg: str) -> None:
    """Anota tu respuesta al reel. NO publica, y eso es a propósito.

    El que publica es el que armó el reel -el turno de las 18 en GitHub, o el
    proceso que largó el botón del menú-, porque es el único que tiene el mp4.
    Este bot puede estar en otra máquina, así que lo único que hace es dejar
    la respuesta donde el que espera la lee (`diario.anotar_decision`).

    Hace falta porque Telegram entrega cada botón UNA sola vez: si el bot está
    corriendo, el callback se lo lleva él y el que espera no lo ve nunca.
    """
    respuesta, _, llave = (arg or "").partition(":")
    if not llave or respuesta not in ("ok", "no"):
        telegram.enviar("Ese botón no lo entiendo.")
        return
    diario.anotar_decision(llave, respuesta)
    telegram.enviar("Aprobado. Lo publica el que armó el reel: los enlaces te "
                    "llegan acá en un rato."
                    if respuesta == "ok" else
                    "Descartado: el reel no sale a ningún lado. Queda guardado.")


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


def atender(update: dict, pagina: Pagina, publicar_fn: Optional[Callable] = None) -> None:
    """Un mensaje o un botón. Lo que no reconoce, muestra el menú."""
    if not _de_mi(update):
        return
    boton = update.get("callback_query")
    if boton:
        dato = boton.get("data") or ""
        telegram.responder_boton(boton.get("id") or "")
        accion, _, arg = dato.partition(":")
        if accion == "publicar":
            frase_id, _, estilo = arg.partition(":")
            publicar(pagina, frase_id, publicar_fn, estilo=estilo or None)
        elif accion == "reel":
            aprobar_el_reel(arg)
        elif accion == "saltar":
            saltar(arg)
            mostrar_siguiente(pagina)
        else:
            correr(accion, pagina)
        return
    # Un mensaje de texto NUNCA publica. Si nombra una tarea, la corre; si no,
    # abre el menú, que es lo que pasaba antes con cualquier texto.
    palabra = (update.get("message") or {}).get("text") or ""
    clave = palabra.strip().lower().lstrip("/")
    if clave in TAREAS:
        correr(clave, pagina)
        return
    menu()
