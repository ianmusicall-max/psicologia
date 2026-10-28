"""Los veintinueve pictogramas del libro, uno por capitulo.

Se dibujan con el lienzo de reportlab, no con una fuente de iconos: son diez
lineas cada uno y asi no hay que licenciar nada ni cargar un archivo mas.

**La regla que los vuelve una familia**: UN grosor de trazo, UN tamano, sin
relleno salvo los puntos. Si alguno llevara una linea mas gruesa o una
silueta maciza dejaria de ser el mismo sistema, que es exactamente lo que
pasaba cuando el libro tenia dos tipografias.

**Y la regla que los vuelve utiles**: dos capitulos no pueden compartir el
dibujo. Eso no se ve dibujandolos de a uno -separados se ven bien- sino
mirandolos juntos. En la primera tanda, autoestima y soledad eran el mismo
circulo con un punto, y habitos y duelo el mismo anillo abierto.
`scripts/hoja_pictogramas.py` los saca a una hoja justamente para eso.

Cada funcion recibe `(c, x, y, s)` y dibuja centrado en `(x, y)` dentro de un
cuadrado de lado `s`. El color y el grosor los pone quien llama.
"""
from __future__ import annotations

import math
from typing import Callable, Dict

# El grosor, relativo al tamano del dibujo. Fino a proposito: con el trazo
# grueso los miembros de una figura se funden y un aro de dos lineas se
# convierte en una mancha.
TRAZO = 0.065


# --------------------------------------------------------------------------
# Piezas que se repiten.
# --------------------------------------------------------------------------

def _curva(c, puntos):
    p = c.beginPath()
    for i, (px, py) in enumerate(puntos):
        p.moveTo(px, py) if i == 0 else p.lineTo(px, py)
    c.drawPath(p)


def _punto(c, x, y, r):
    c.circle(x, y, r, stroke=0, fill=1)


def _flecha(c, x, y, ang, largo):
    """La punta, calculada sobre la direccion en la que va el trazo.

    A ojo no sale: la primera version del ciclo dibujo las dos lineas sueltas
    y el conjunto se leyo como un anillo roto con un garabato al lado.
    """
    for giro in (math.radians(150), math.radians(-150)):
        _curva(c, [(x, y), (x + math.cos(ang + giro) * largo,
                            y + math.sin(ang + giro) * largo)])


# --------------------------------------------------------------------------
# Los veintinueve.
# --------------------------------------------------------------------------

def emociones(c, x, y, s):          # 1 · sube, baja y se va
    _curva(c, [(x - s / 2 + s * i / 60,
                y + math.sin(i / 60 * 4 * math.pi) * s * 0.2)
               for i in range(61)])


def ansiedad(c, x, y, s):           # 2 · da vueltas y no llega
    _curva(c, [(x + math.cos(i / 160 * 2.6 * 2 * math.pi) * s * 0.46 * (1 - i / 160),
                y + math.sin(i / 160 * 2.6 * 2 * math.pi) * s * 0.46 * (1 - i / 160))
               for i in range(161)])


def autoestima(c, x, y, s):         # 3 · el centro sostiene lo de afuera
    c.circle(x, y, s * 0.46)
    c.circle(x, y, s * 0.2)


def limites(c, x, y, s):            # 4 · dos lados y una raya
    c.circle(x - s * 0.3, y, s * 0.17)
    c.circle(x + s * 0.3, y, s * 0.17)
    _curva(c, [(x, y - s * 0.42), (x, y + s * 0.42)])


def apego(c, x, y, s):              # 5 · dos que se tocan
    c.circle(x - s * 0.22, y, s * 0.26)
    c.circle(x + s * 0.22, y, s * 0.26)


def habitos(c, x, y, s):            # 6 · vuelve a empezar
    r = s * 0.42
    c.arc(x - r, y - r, x + r, y + r, 20, 300)
    fin = math.radians(320)
    _flecha(c, x + math.cos(fin) * r, y + math.sin(fin) * r,
            fin + math.pi / 2, s * 0.18)


def duelo(c, x, y, s):              # 7 · afuera lo que ya no esta adentro
    c.circle(x, y, s * 0.4)
    _punto(c, x + s * 0.44, y + s * 0.34, s * 0.06)


def pensamientos(c, x, y, s):       # 8 · uno no es como los otros
    for i, dy in enumerate((0.26, 0, -0.26)):
        ancho = s * (0.44 if i != 1 else 0.26)
        _curva(c, [(x - ancho, y + s * dy), (x + ancho, y + s * dy)])


def descanso(c, x, y, s):           # 9 · la linea que baja y se queda quieta
    p = c.beginPath()
    p.moveTo(x - s * 0.46, y + s * 0.3)
    p.curveTo(x - s * 0.1, y + s * 0.3, x - s * 0.1, y - s * 0.12,
              x + s * 0.46, y - s * 0.12)
    c.drawPath(p)
    _curva(c, [(x - s * 0.46, y - s * 0.38), (x + s * 0.46, y - s * 0.38)])


def sentido(c, x, y, s):            # 10 · un punto y una direccion
    _punto(c, x - s * 0.38, y - s * 0.3, s * 0.07)
    _curva(c, [(x - s * 0.3, y - s * 0.24), (x + s * 0.46, y + s * 0.4)])


def comunicacion(c, x, y, s):       # 11 · dos que se miran, con un hueco
    r, hueco = s * 0.34, s * 0.13
    c.arc(x - hueco - 2 * r, y - r, x - hueco, y + r, 110, 140)
    c.arc(x + hueco, y - r, x + hueco + 2 * r, y + r, 290, 140)


def reconexion(c, x, y, s):         # 12 · separados, y algo que los junta
    c.circle(x - s * 0.36, y, s * 0.16)
    c.circle(x + s * 0.36, y, s * 0.16)
    _curva(c, [(x - s * 0.18, y), (x + s * 0.18, y)])


def ruptura(c, x, y, s):            # 13 · la misma linea, separada
    _curva(c, [(x - s * 0.46, y - s * 0.12), (x - s * 0.08, y + s * 0.2)])
    _curva(c, [(x + s * 0.08, y - s * 0.2), (x + s * 0.46, y + s * 0.12)])


def elegir(c, x, y, s):             # 14 · un camino que se parte en dos
    _curva(c, [(x - s * 0.46, y - s * 0.3), (x - s * 0.06, y)])
    _curva(c, [(x - s * 0.06, y), (x + s * 0.42, y + s * 0.3)])
    _curva(c, [(x - s * 0.06, y), (x + s * 0.42, y - s * 0.26)])


def celos(c, x, y, s):              # 15 · dos, y alguien mirando
    c.circle(x - s * 0.26, y - s * 0.08, s * 0.24)
    c.circle(x + s * 0.06, y - s * 0.08, s * 0.24)
    _punto(c, x + s * 0.42, y + s * 0.34, s * 0.065)


def familia(c, x, y, s):            # 16 · lo que viene de antes
    for r in (0.2, 0.33, 0.46):
        c.arc(x - s * r, y - s * r, x + s * r, y + s * r, 200, 140)


def amistad(c, x, y, s):            # 17 · tres que se eligen
    puntos = [(x, y + s * 0.38), (x - s * 0.36, y - s * 0.26),
              (x + s * 0.36, y - s * 0.26)]
    for i in range(3):
        _curva(c, [puntos[i], puntos[(i + 1) % 3]])
    for px, py in puntos:
        _punto(c, px, py, s * 0.065)


def culpa(c, x, y, s):              # 18 · lo que se hizo y lo que se repara
    _curva(c, [(x - s * 0.44, y + s * 0.1), (x + s * 0.44, y + s * 0.1)])
    _curva(c, [(x - s * 0.16, y - s * 0.3), (x, y + s * 0.1),
               (x + s * 0.16, y - s * 0.3), (x - s * 0.16, y - s * 0.3)])
    _punto(c, x - s * 0.44, y + s * 0.1, s * 0.07)
    _punto(c, x + s * 0.44, y + s * 0.1, s * 0.07)


def intimidad(c, x, y, s):          # 19 · dos ritmos cerca
    for dy in (0.13, -0.13):
        _curva(c, [(x - s * 0.44 + s * 0.88 * i / 40,
                    y + s * dy + math.sin(i / 40 * 2 * math.pi) * s * 0.1)
                   for i in range(41)])


def perdon(c, x, y, s):             # 20 · el lazo que se suelta
    c.circle(x - s * 0.18, y, s * 0.26)
    _curva(c, [(x + s * 0.04, y + s * 0.12), (x + s * 0.46, y + s * 0.34)])


def soledad(c, x, y, s):            # 21 · un punto en mucho espacio
    c.circle(x, y, s * 0.46)
    _punto(c, x - s * 0.17, y - s * 0.12, s * 0.055)


def discutir(c, x, y, s):           # 22 · dos que empujan de frente
    _curva(c, [(x - s * 0.46, y + s * 0.12), (x - s * 0.06, y + s * 0.12)])
    _flecha(c, x - s * 0.06, y + s * 0.12, 0, s * 0.16)
    _curva(c, [(x + s * 0.46, y - s * 0.12), (x + s * 0.06, y - s * 0.12)])
    _flecha(c, x + s * 0.06, y - s * 0.12, math.pi, s * 0.16)


def confianza(c, x, y, s):          # 23 · se hace de repeticiones
    r = s * 0.44
    for i in range(10):
        c.arc(x - r, y - r, x + r, y + r, i * 36, 22)


def redes(c, x, y, s):              # 24 · muchos, y uno que sos vos
    for fila in range(3):
        for col in range(3):
            px = x + (col - 1) * s * 0.33
            py = y + (fila - 1) * s * 0.33
            if fila == 1 and col == 1:
                _punto(c, px, py, s * 0.075)
            else:
                c.circle(px, py, s * 0.075)


def dinero(c, x, y, s):             # 25 · lo que se junta
    for i, dy in enumerate((-0.26, 0, 0.26)):
        c.ellipse(x - s * 0.34, y + s * dy - s * 0.1,
                  x + s * 0.34, y + s * dy + s * 0.1)


def hogar(c, x, y, s):              # 26 · el techo y el piso
    _curva(c, [(x - s * 0.44, y + s * 0.06), (x, y + s * 0.42),
               (x + s * 0.44, y + s * 0.06)])
    _curva(c, [(x - s * 0.32, y - s * 0.34), (x + s * 0.32, y - s * 0.34)])


def expectativas(c, x, y, s):       # 27 · lo que esperabas y lo que paso
    c.saveState()
    c.setDash(2.2, 2.2)
    _curva(c, [(x - s * 0.44, y - s * 0.3), (x + s * 0.44, y + s * 0.38)])
    c.restoreState()
    _curva(c, [(x - s * 0.44, y - s * 0.3), (x + s * 0.44, y - s * 0.06)])


def cambio(c, x, y, s):             # 28 · de a un escalon
    pasos = [(-0.46, -0.34), (-0.16, -0.34), (-0.16, -0.04),
             (0.14, -0.04), (0.14, 0.26), (0.46, 0.26)]
    _curva(c, [(x + a * s, y + b * s) for a, b in pasos])


def miedo(c, x, y, s):              # 29 · se mueve igual
    _curva(c, [(x - s * 0.46, y), (x + s * 0.12, y)])
    _flecha(c, x + s * 0.12, y, 0, s * 0.17)
    _curva(c, [(x + s * 0.34, y - s * 0.4), (x + s * 0.34, y + s * 0.4)])


DIBUJOS: Dict[int, Callable] = {
    1: emociones, 2: ansiedad, 3: autoestima, 4: limites, 5: apego,
    6: habitos, 7: duelo, 8: pensamientos, 9: descanso, 10: sentido,
    11: comunicacion, 12: reconexion, 13: ruptura, 14: elegir, 15: celos,
    16: familia, 17: amistad, 18: culpa, 19: intimidad, 20: perdon,
    21: soledad, 22: discutir, 23: confianza, 24: redes, 25: dinero,
    26: hogar, 27: expectativas, 28: cambio, 29: miedo,
}


def dibujar(c, capitulo: int, x: float, y: float, s: float, color,
            trazo: float = 0) -> bool:
    """Dibuja el pictograma del capitulo. Devuelve False si no tiene.

    `trazo` fija el grosor en puntos en vez de calcularlo con el tamano. Hace
    falta para la trama de las paginas en blanco: ahi los dibujos van de 26 a
    120 mm, y con el grosor proporcional los grandes salen con una linea de
    casi 8 mm y la pagina se lee como un monton de burbujas en vez de como un
    dibujo.

    No levanta error cuando falta: un capitulo sin dibujo es una apertura sin
    dibujo, y el libro sale igual. Quedarse sin libro porque falta un icono
    seria el peor cambio posible.
    """
    dibujo = DIBUJOS.get(int(capitulo))
    if dibujo is None:
        return False
    c.saveState()
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(trazo or TRAZO * s)
    c.setLineCap(1)
    c.setLineJoin(1)
    dibujo(c, x, y, s)
    c.restoreState()
    return True
