"""El borrador del libro, armado del banco de frases.

Cada tema es un capítulo: su tesis abre, cada frase va como epígrafe seguida
de su reflexión, y el principio y la fuente quedan como notas. El manuscrito
crece solo a medida que crece el banco; lo que se escriba a mano va en otro
archivo, no en este, porque este se regenera.
"""
from __future__ import annotations

from typing import Iterable, List

from .frases import Tema, todas

AVISO = ("<!-- Generado por scripts/armar_libro.py a partir de frases/. No editar a mano: "
         "se vuelve a escribir entero. -->")


def borrador(temas: Iterable[Tema], titulo: str = "Frases para pensar") -> str:
    temas = sorted(temas, key=lambda t: t.capitulo)
    n = len(todas(temas))
    out: List[str] = [AVISO, "", "# %s" % titulo, "",
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
