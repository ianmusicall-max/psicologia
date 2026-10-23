"""El borrador del libro, armado del banco de frases.

Cada tema es un capítulo: su tesis abre, cada frase va como epígrafe seguida
de su reflexión, y el principio y la fuente quedan como notas. El manuscrito
crece solo a medida que crece el banco; lo que se escriba a mano va en otro
archivo, no en este, porque este se regenera.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .frases import Tema, todas

ROOT = Path(__file__).resolve().parent.parent
# El archivo versionado. Está acá y no en el script porque ahora lo miran dos:
# el que lo reescribe y el botón del bot que dice si quedó viejo.
BORRADOR = ROOT / "libro" / "borrador.md"

AVISO = ("<!-- Generado por scripts/armar_libro.py a partir de frases/. No editar a mano: "
         "se vuelve a escribir entero. -->")


# El título lo eligió el usuario el 2026-10-23, sobre tres opciones. Cubre las
# dos mitades del libro -quererte y vincularte-, que es lo que la página
# promete, y promete algo concreto, que es lo que un título de tapa tiene que
# hacer. Las otras dos eran «Nadie te completa», más filoso y con el riesgo de
# sonar a reproche a quien busca pareja, y «Hablarte bien», el más propio y el
# que menos dice de qué trata.
TITULO = "Lo que nadie te explicó del amor"
SUBTITULO = "Ideas para quererte, elegir mejor y entenderte con quien querés"


def borrador(temas: Iterable[Tema], titulo: str = TITULO,
             subtitulo: str = SUBTITULO) -> str:
    temas = sorted(temas, key=lambda t: t.capitulo)
    n = len(todas(temas))
    out: List[str] = [AVISO, "", "# %s" % titulo, "", "### %s" % subtitulo, "",
                      "*Borrador armado del banco de frases: %d capítulos, %d frases.*" % (len(temas), n),
                      "", "## Índice", ""]
    for t in temas:
        out.append("%d. %s (%d frases)" % (t.capitulo, t.titulo, len(t.frases)))
    out.append("")
    for t in temas:
        out += ["", "## Capítulo %d · %s" % (t.capitulo, t.titulo), "", t.tesis, ""]
        for f in t.frases:
            out += ["", "> %s" % f.texto, "", f.reflexion, "",
                    "*Principio:* %s  " % f.principio,
                    "*Fuente:* %s" % f.fuente, ""]
    fuentes = sorted({f.fuente for f in todas(temas)}, key=str.lower)
    out += ["", "## Fuentes citadas", ""]
    out += ["- %s" % x for x in fuentes]
    out.append("")
    return "\n".join(out)
