"""Las pruebas del banco, la línea editorial, la rotación, el flyer, el libro y la publicación.

    python3 -m unittest tests.test_core
"""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

from src import bot, config, diseno, entorno, facebook, frases, instagram, libro, medir, parrilla, telegram

ROOT = Path(__file__).resolve().parent.parent
TEMAS = frases.leer()
PAGINA = config.cargar()


def una(**kw) -> frases.Frase:
    base = dict(id="pru-01", texto="Una frase de prueba que dice algo con sentido y termina bien.",
                principio="Un principio.", fuente="Alguien (2020).",
                reflexion="Una reflexión que explica la frase con calma, le da contexto y la deja "
                          "lista para el caption y para el capítulo del libro.",
                tema="emociones", destacar=[], sensible=None)
    base.update(kw)
    return frases.Frase(**base)


def tema(**kw) -> frases.Tema:
    base = dict(tema="prueba", capitulo=99, titulo="Un capítulo de prueba", eje="apoyo",
                tesis="Una tesis lo bastante larga como para contar como tesis de un capítulo del libro.",
                hashtags=["uno", "dos", "tres"], sensible=False, frases=[])
    base.update(kw)
    return frases.Tema(**base)


# ---------------------------------------------------------------------------
# La línea editorial.
# ---------------------------------------------------------------------------

class TestLaLineaEditorial(unittest.TestCase):

    def test_una_frase_bien_escrita_pasa(self):
        self.assertEqual(frases.validar(una()), [])

    def test_etiquetar_a_una_persona_rebota(self):
        self.assertTrue(frases.politica("Tu ex es un narcisista y tu madre es tóxica."))
        self.assertTrue(frases.politica("No es un trastorno, es cansancio."))

    def test_pseudociencia_rebota(self):
        self.assertTrue(frases.politica("Cuida tu energía: el universo te escucha."))
        self.assertTrue(frases.politica("Aprende a manifestar lo que quieres."))

    def test_positividad_toxica_rebota(self):
        self.assertTrue(frases.politica("Todo pasa por algo."))
        self.assertTrue(frases.politica("Solo piensa positivo y verás."))

    def test_una_promesa_rebota(self):
        self.assertTrue(frases.politica("Esto cura la ansiedad para siempre."))
        self.assertTrue(frases.politica("Sanar es posible en 7 días."))

    def test_la_verguenza_rebota(self):
        self.assertTrue(frases.politica("No hay excusas: si no cambias es porque eres débil."))

    def test_la_crisis_no_va_en_un_flyer(self):
        self.assertTrue(frases.politica("Hablar del suicidio salva vidas."))

    def test_una_raya_es_una_cita(self):
        self.assertTrue(frases.politica("Sé tú mismo. — Oscar Wilde"))
        self.assertTrue(frases.politica("Como dice un amigo, todo se arregla."))

    def test_dijo_a_secas_no_es_una_cita(self):
        # «alguien te lo dijo primero» es una frase del banco, no una atribución.
        self.assertEqual(frases.politica("Lo que te dices, alguien te lo dijo primero."), [])

    def test_compara_sin_acentos_ni_mayusculas(self):
        self.assertTrue(frases.politica("GENTE TOXICA"))
        self.assertTrue(frases.politica("Energía, decía ella."))

    def test_mira_la_palabra_entera(self):
        # "loca" no se lleva puesto a "colocar", ni "cura" a "curarse" ni a "procurar".
        self.assertEqual(frases.politica("Hay que colocar las cosas en su lugar y procurar calma."), [])
        self.assertEqual(frases.politica("La exigencia sana quiere hacerlo bien."), [])

    def test_el_largo_tiene_piso_y_techo(self):
        self.assertTrue(any("eslogan" in p for p in frases.validar(una(texto="Respira."))))
        larga = ("Una frase larguísima que no entra en el flyer y que sigue y sigue sin parar "
                 "porque alguien se olvidó de que esto se lee en un teléfono y no en un libro, "
                 "y entonces se pasa del tope que fija el validador.")
        self.assertTrue(any("no entra" in p for p in frases.validar(una(texto=larga))))

    def test_termina_en_punto(self):
        self.assertTrue(any("terminar" in p for p in frases.validar(una(texto="Una frase que no termina en nada y queda abierta"))))
        self.assertEqual(frases.validar(una(texto="¿Y si la pregunta fuera otra, una que te mueva de lugar?")), [])

    def test_la_palabra_destacada_tiene_que_estar(self):
        self.assertTrue(any("destacar" in p for p in frases.validar(una(destacar=["ausente"]))))
        self.assertEqual(frases.validar(una(destacar=["sentido"])), [])

    def test_la_reflexion_tambien_se_audita(self):
        f = una(reflexion="Una reflexión que promete que esto cura la ansiedad y la elimina "
                          "para siempre si piensas positivo todos los días sin falta.")
        self.assertTrue(any(p.startswith("reflexión") for p in frases.validar(f)))

    def test_sin_fuente_no_hay_frase(self):
        self.assertTrue(any("fuente" in p for p in frases.validar(una(fuente=""))))
        self.assertTrue(any("principio" in p for p in frases.validar(una(principio=" "))))

    def test_las_comillas_rectas_rebotan(self):
        self.assertTrue(any("comillas" in p for p in frases.validar(una(texto='Decir "no" también es cuidar.'))))


# ---------------------------------------------------------------------------
# El banco de verdad.
# ---------------------------------------------------------------------------

class TestElBanco(unittest.TestCase):

    def test_los_capitulos_van_de_uno_en_uno_sin_repetir(self):
        self.assertEqual([t.capitulo for t in TEMAS], list(range(1, len(TEMAS) + 1)))

    def test_el_nucleo_cubre_los_pilares_de_la_pagina(self):
        # La descripción de la página promete amor propio, recuperar a la
        # pareja, la ex pareja, encontrar a alguien y comunicación. Estos son
        # los temas que contestan eso, y son los que la cuota publica más.
        nucleo = sorted(t.tema for t in TEMAS if t.eje == "nucleo")
        for pilar in ("autoestima", "reconexion", "ruptura", "elegir", "comunicacion"):
            self.assertIn(pilar, nucleo)
        # Y son mayoría: la cuota pide dos de cada tres posts del núcleo, así
        # que si el apoyo creciera más que el núcleo, dejaría de alcanzar.
        self.assertGreaterEqual(len(nucleo), len(TEMAS) - len(nucleo))

    def test_un_eje_que_no_existe_rebota(self):
        self.assertTrue(any("eje" in x for x in frases.validar_tema(tema(eje="central"))))

    def test_pasa_entero_la_linea_editorial(self):
        self.assertEqual(frases.revisar(TEMAS, PAGINA), [])

    def test_un_tema_que_repite_un_hashtag_fijo_rebota(self):
        # Dejaría el post con cuatro etiquetas en vez de cinco, en silencio.
        malo = tema(hashtags=["relaciones", "dos", "tres"])
        self.assertTrue(any("fijos" in x for x in frases.revisar([malo], PAGINA)))

    def test_al_menos_ocho_frases_por_tema(self):
        for t in TEMAS:
            self.assertGreaterEqual(len(t.frases), 8, t.tema)

    def test_los_ids_llevan_el_prefijo_de_su_tema(self):
        # Tres letras del tema y dos dígitos, en orden: es lo que hace legible
        # data/publicadas.json sin abrir el banco.
        for t in TEMAS:
            for i, f in enumerate(t.frases, 1):
                self.assertEqual(f.id, "%s-%02d" % (t.tema[:3], i))

    def test_cada_frase_destaca_algo(self):
        # Sin palabra destacada el flyer sale todo en tinta y se pierde la marca.
        for f in frases.todas(TEMAS):
            self.assertTrue(f.destacar, f.id)

    SENSIBLES = ["duelo", "intimidad", "ruptura"]

    def test_los_temas_sensibles_son_los_que_tocan_fondo(self):
        # Duelo y ruptura por el dolor; intimidad porque habla de sexualidad
        # y conviene que el caption recuerde que esto no reemplaza terapia.
        self.assertEqual(sorted(t.tema for t in TEMAS if t.sensible), self.SENSIBLES)

    def test_la_revision_detecta_un_id_repetido(self):
        t = tema(frases=[una(id="pru-01"), una(id="pru-01")])
        self.assertTrue(any("repetido" in p for p in frases.revisar([t])))


# ---------------------------------------------------------------------------
# Cuál toca.
# ---------------------------------------------------------------------------

class TestLaSiguiente(unittest.TestCase):

    def _publicar_todo(self, temas):
        ya, orden, dia = {}, [], date(2026, 11, 1)
        while True:
            f = frases.siguiente(temas, ya)
            if f is None:
                return orden
            ya[f.id] = {"dia": dia.isoformat(), "post_id": "p", "pagina": "x"}
            orden.append(f)
            dia = date.fromordinal(dia.toordinal() + 1)

    def test_dos_de_cada_tres_son_del_nucleo(self):
        # La cuota: la página publica sobre todo lo que su descripción promete.
        orden = self._publicar_todo(TEMAS)
        eje_de = {t.tema: t.eje for t in TEMAS}
        for corte in (15, 30, 60):
            nucleo = sum(1 for f in orden[:corte] if eje_de[f.tema] == "nucleo")
            self.assertEqual(nucleo, round(corte * 2 / 3), corte)

    def test_el_nucleo_sale_intercalado_y_no_todo_junto(self):
        # Cumplir la cuota turno a turno y no contando al final es lo que evita
        # un mes de pareja seguido de un mes de lo demás.
        orden = self._publicar_todo(TEMAS)
        eje_de = {t.tema: t.eje for t in TEMAS}
        ejes = [eje_de[f.tema] for f in orden[:60]]
        self.assertNotIn(["nucleo"] * 3, [ejes[i:i + 3] for i in range(len(ejes) - 2)])
        self.assertNotIn(["apoyo"] * 2, [ejes[i:i + 2] for i in range(len(ejes) - 1)])

    def test_la_cuota_es_una_preferencia_y_no_un_filtro(self):
        # Sin frases del núcleo pendientes sale una de apoyo igual: perder un
        # día de publicación sería mucho peor que romper la proporción.
        ya = {f.id: {"dia": "2026-11-01", "post_id": "p", "pagina": "x"}
              for t in TEMAS if t.eje == "nucleo" for f in t.frases}
        f = frases.siguiente(TEMAS, ya)
        self.assertIsNotNone(f)
        self.assertEqual(frases.tema_de(TEMAS, f).eje, "apoyo")

    def test_rota_por_tema(self):
        # Dentro de cada eje, el tema que hace más que no sale va primero.
        orden = self._publicar_todo(TEMAS)
        nucleo = [f.tema for f in orden if frases.tema_de(TEMAS, f).eje == "nucleo"]
        self.assertEqual(len(set(nucleo[:7])), 7)

    def test_no_repite_hasta_agotar_el_banco(self):
        orden = self._publicar_todo(TEMAS)
        self.assertEqual(len(orden), len(frases.todas(TEMAS)))
        self.assertEqual(len({f.id for f in orden}), len(orden))

    def test_dos_dias_seguidos_nunca_son_del_mismo_tema(self):
        orden = self._publicar_todo(TEMAS)
        for a, b in zip(orden, orden[1:]):
            if b is orden[-1]:
                break  # al final queda un solo tema con frases y no hay con qué alternar
            self.assertNotEqual(a.tema, b.tema, (a.id, b.id))

    def test_es_determinista(self):
        ya = {"emo-01": {"dia": "2026-11-01", "post_id": "p", "pagina": "x"}}
        self.assertEqual(frases.siguiente(TEMAS, ya).id, frases.siguiente(TEMAS, ya).id)

    def test_el_tema_que_acaba_de_salir_va_al_final(self):
        # Salió uno de apoyo, así que ahora toca núcleo, y dentro del núcleo el
        # de capítulo más bajo que nunca salió.
        ya = {"emo-01": {"dia": "2026-11-01", "post_id": "p", "pagina": "x"}}
        self.assertEqual(frases.siguiente(TEMAS, ya).tema, "autoestima")

    def test_anotar_relee_antes_de_escribir(self):
        # Si entre leer y escribir alguien anotó otra cosa, no se le pisa.
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "publicadas.json"
            frases.anotar_publicada("emo-01", date(2026, 11, 1), "p1", "x", ruta)
            otro = frases.publicadas(ruta)
            otro["ape-01"] = {"dia": "2026-11-02", "post_id": "p2", "pagina": "x"}
            ruta.write_text(json.dumps(otro), encoding="utf-8")
            frases.anotar_publicada("due-01", date(2026, 11, 3), "p3", "x", ruta)
            self.assertEqual(set(frases.publicadas(ruta)), {"emo-01", "ape-01", "due-01"})
            self.assertFalse(list(Path(d).glob("*.parcial")))

    def test_un_json_roto_no_tumba_la_lectura(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "publicadas.json"
            ruta.write_text("{no es json", encoding="utf-8")
            self.assertEqual(frases.publicadas(ruta), {})


# ---------------------------------------------------------------------------
# El caption.
# ---------------------------------------------------------------------------

class TestElCaption(unittest.TestCase):

    def test_cinco_hashtags_y_los_dos_primeros_fijos(self):
        for t in TEMAS:
            hs = frases.hashtags(t, PAGINA)
            self.assertEqual(len(hs), 5, t.tema)
            self.assertEqual(hs[:2], ["#psicología", "#relaciones"])

    def test_un_hashtag_del_tema_no_repite_uno_fijo(self):
        t = tema(hashtags=["psicologia", "dos", "tres"])
        hs = frases.hashtags(t, PAGINA)
        self.assertEqual(len(hs), 4)
        self.assertEqual(hs.count("#psicología") + hs.count("#psicologia"), 1)

    def test_solo_los_temas_sensibles_llevan_el_pie(self):
        sensibles = {t.tema for t in TEMAS if t.sensible}
        for t in TEMAS:
            c = frases.caption(t.frases[0], t, PAGINA)
            self.assertEqual(PAGINA.pie_sensible in c, t.tema in sensibles, t.tema)

    def test_una_frase_puede_pedir_el_pie_sola(self):
        t = tema(sensible=False)
        self.assertIn(PAGINA.pie_sensible, frases.caption(una(sensible=True), t, PAGINA))
        t = tema(sensible=True)
        self.assertNotIn(PAGINA.pie_sensible, frases.caption(una(sensible=False), t, PAGINA))

    def test_el_caption_empieza_con_la_frase_y_termina_con_los_hashtags(self):
        f = TEMAS[0].frases[0]
        c = frases.caption(f, TEMAS[0], PAGINA)
        self.assertTrue(c.startswith(f.texto))
        self.assertTrue(c.rstrip().endswith("#sentir"))


# ---------------------------------------------------------------------------
# El flyer.
# ---------------------------------------------------------------------------

def _acento(img, pagina):
    """Cuántos píxeles tienen el color de acento."""
    r, g, b = tuple(int(pagina.color("acento", "#B5654A")[i:i + 2], 16) for i in (1, 3, 5))
    n = 0
    for px in img.getdata():
        if abs(px[0] - r) < 8 and abs(px[1] - g) < 8 and abs(px[2] - b) < 8:
            n += 1
    return n


class TestElFlyer(unittest.TestCase):

    def test_mide_1080x1350_y_el_doble_al_publicar(self):
        f, t = TEMAS[0].frases[0], TEMAS[0]
        self.assertEqual(diseno.render(f, t, PAGINA, escala=1).size, (1080, 1350))
        self.assertEqual(diseno.render(f, t, PAGINA, escala=2).size, (2160, 2700))

    def test_todas_las_del_banco_entran(self):
        for t in TEMAS:
            for f in t.frases:
                diseno.render(f, t, PAGINA, escala=1)

    def test_el_texto_mas_largo_que_admite_el_validador_entra(self):
        # 180 caracteres de palabras largas: el peor caso para el ancho.
        palabra = "electroencefalografista"
        texto = (" ".join([palabra] * 8))[:frases.MAXIMO - 1] + "."
        self.assertEqual(len(texto), frases.MAXIMO)
        diseno.render(una(texto=texto), tema(), PAGINA, escala=1)

    def test_una_frase_corta_sale_mas_grande_que_una_larga(self):
        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        corta = "Respira y mira qué pasa.".split()
        larga = ("Pensar en el futuro para prevenirlo y en el pasado para corregirlo son dos "
                 "formas de no estar en el único lugar donde puedes hacer algo.").split()
        ancho, alto = diseno.W - 2 * diseno.MARGEN, diseno.ZONA_ALTO
        t1, _ = diseno.reparto(draw, corta, ancho, alto, diseno.cuerpo_maximo(" ".join(corta)))
        t2, _ = diseno.reparto(draw, larga, ancho, alto, diseno.cuerpo_maximo(" ".join(larga)))
        self.assertGreater(t1, t2)

    def test_no_dibuja_si_no_entra(self):
        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        with self.assertRaises(ValueError):
            diseno.reparto(draw, "una frase cualquiera".split(), ancho=900, alto=10, tam_max=60)

    def test_la_palabra_destacada_sale_en_el_acento(self):
        f = una(texto="Una palabra va en color y el resto en tinta, para que se vea.", destacar=["color"])
        con = _acento(diseno.render(f, tema(), PAGINA, escala=1), PAGINA)
        sin = _acento(diseno.render(una(texto=f.texto, destacar=[]), tema(), PAGINA, escala=1), PAGINA)
        # Sin destacar queda el acento de la raya y del rótulo del capítulo; con, bastante más.
        self.assertGreater(con, sin * 2)

    def test_una_secuencia_de_dos_palabras_se_destaca_entera(self):
        f = una(texto="La preocupación te hace pagar dos veces y cobra siempre.", destacar=["dos veces"])
        self.assertEqual(frases.destacadas(f), [False] * 5 + [True, True] + [False] * 3)

    def test_guardar_escribe_aparte_y_no_deja_parcial(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = diseno.dibujar(TEMAS[0].frases[0], TEMAS[0], PAGINA, Path(d), escala=1)
            self.assertTrue(ruta.exists())
            self.assertEqual(ruta.suffix, ".jpg")
            self.assertFalse(list(Path(d).glob("*.parcial")))
            self.assertEqual(Image.open(ruta).size, (1080, 1350))


# ---------------------------------------------------------------------------
# El libro.
# ---------------------------------------------------------------------------

def _luminancia(hex_color):
    def canal(v):
        v = v / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = diseno._rgb(hex_color)
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def _contraste(uno, otro):
    a, b = sorted((_luminancia(uno), _luminancia(otro)), reverse=True)
    return (a + 0.05) / (b + 0.05)


class TestLosEstilos(unittest.TestCase):
    """Cuatro repartos del mismo flyer. Lo que cambia es la forma, nunca lo
    que dice. Fueron once; el usuario eligió estos y los otros siete se
    borraron, porque un renderer sin camino envejece sin que nadie lo note."""

    def test_son_los_cuatro_que_eligio_el_usuario(self):
        self.assertEqual(sorted(diseno.ESTILOS), ["ficha", "marcador", "marco", "regla"])
        self.assertEqual(diseno.POR_DEFECTO, "regla")

    def test_todos_dibujan_el_peor_caso_del_validador(self):
        # 180 caracteres de palabras largas: el máximo que deja pasar el
        # validador, y el que más apretado deja cualquier reparto.
        palabra = "electroencefalografista"
        texto = (" ".join([palabra] * 8))[:frases.MAXIMO - 1] + "."
        for estilo in diseno.ESTILOS:
            diseno.render(una(texto=texto), tema(), PAGINA, escala=1, estilo=estilo)

    def test_todos_dibujan_una_frase_de_cada_tema(self):
        for estilo in diseno.ESTILOS:
            for t in TEMAS:
                diseno.render(t.frases[0], t, PAGINA, escala=1, estilo=estilo)

    def test_el_estilo_lo_manda_la_config(self):
        pagina = config.cargar()
        pagina.estilo = "marco"
        con_config = diseno.render(TEMAS[0].frases[0], TEMAS[0], pagina, escala=1)
        aparte = diseno.render(TEMAS[0].frases[0], TEMAS[0], pagina, escala=1, estilo="marco")
        self.assertEqual(list(con_config.getdata()), list(aparte.getdata()))

    def test_un_estilo_que_no_existe_falla_y_dice_cuales_hay(self):
        with self.assertRaises(ValueError) as ctx:
            diseno.render(TEMAS[0].frases[0], TEMAS[0], PAGINA, escala=1, estilo="neon")
        self.assertIn("marco", str(ctx.exception))

    def test_en_todos_el_texto_se_lee(self):
        for estilo in diseno.ESTILOS:
            c = diseno._colores(PAGINA, estilo)
            self.assertGreaterEqual(_contraste(c["tinta"], c["fondo"]), 7.0, estilo)
            self.assertGreaterEqual(_contraste(c["acento"], c["fondo"]), 3.5, estilo)

    def test_ninguno_lleva_fondo_oscuro(self):
        # Lo pidió el usuario y por eso es una prueba y no un comentario: se
        # dibuja cada estilo y se mira el fondo de verdad, no la tabla.
        for estilo in diseno.ESTILOS:
            img = diseno.render(TEMAS[4].frases[2], TEMAS[4], PAGINA, escala=1, estilo=estilo)
            for punto in ((20, 20), (diseno.W - 20, diseno.H - 20), (diseno.W // 2, 20)):
                color = "#%02x%02x%02x" % img.getpixel(punto)
                self.assertGreater(_luminancia(color), 0.5, (estilo, punto, color))

    def test_el_resaltador_deja_el_texto_legible(self):
        # La palabra marcada no cambia de color: queda tinta sobre la mancha,
        # así que lo que hay que mirar es el contraste contra la mancha.
        c = diseno._colores(PAGINA, "marcador")
        mancha = diseno._mezclar(c["fondo"], c["acento"], 0.34)
        self.assertGreaterEqual(_contraste(c["tinta"], mancha), 7.0)

    def test_las_rayas_de_la_ficha_no_tachan_el_encabezado(self):
        # El bucle que busca la primera raya termina POR DEBAJO del tope, así
        # que sin el paso de vuelta la raya cae sobre el nombre de la página.
        img = diseno.render(TEMAS[4].frases[2], TEMAS[4], PAGINA, escala=1, estilo="ficha")
        raya = diseno._rgb(diseno._mezclar(PAGINA.color("fondo", "#F3EFE6"),
                                           PAGINA.color("suave", "#8C8F93"), 0.38))
        for y in range(diseno.ARRIBA - 14, diseno.ARRIBA + 40):
            fila = [img.getpixel((x, y)) for x in range(diseno.W - 200, diseno.W - 120)]
            self.assertFalse(all(abs(p[0] - raya[0]) < 6 and abs(p[1] - raya[1]) < 6
                                 for p in fila), y)


class TestElLibro(unittest.TestCase):

    def test_el_borrador_versionado_esta_al_dia(self):
        # Después de tocar una frase hay que correr scripts/armar_libro.py.
        actual = (ROOT / "libro" / "borrador.md").read_text(encoding="utf-8")
        self.assertEqual(actual, libro.borrador(TEMAS))

    def test_cada_frase_esta_en_el_borrador_con_su_reflexion(self):
        texto = libro.borrador(TEMAS)
        for f in frases.todas(TEMAS):
            self.assertIn("> " + f.texto, texto)
            self.assertIn(f.reflexion, texto)
            self.assertIn(f.fuente, texto)

    def test_los_capitulos_van_en_orden(self):
        texto = libro.borrador(TEMAS)
        posiciones = [texto.index("## Capítulo %d ·" % t.capitulo) for t in TEMAS]
        self.assertEqual(posiciones, sorted(posiciones))


# ---------------------------------------------------------------------------
# Publicar.
# ---------------------------------------------------------------------------

class _Respuesta:
    def __init__(self, status, datos):
        self.status_code, self._datos, self.text = status, datos, json.dumps(datos)

    def json(self):
        return self._datos


class TestIdentificarElToken(unittest.TestCase):
    """Saber si un token es de usuario o de página, que es lo que decide todo
    lo demás: solo el de usuario se puede convertir en uno permanente."""

    def _respuesta(self, datos, status=200):
        return mock.patch.object(facebook.requests, "get", return_value=_Respuesta(status, datos))

    def test_un_token_de_usuario_no_se_lee_como_roto(self):
        # La primera versión preguntaba `fields=id,name,category` y daba por
        # roto cualquier token que no trajera `category`. Un usuario no tiene
        # ese campo, así que la API devolvía «(#100) Tried accessing
        # nonexisting field» y el token válido se descartaba.
        with self._respuesta({"id": "9", "name": "David", "metadata": {"type": "user"}}):
            yo = facebook.identificar("tok")
        self.assertNotIn("error", yo)
        self.assertEqual(yo["tipo"], "usuario")
        self.assertEqual(yo["nombre"], "David")

    def test_no_le_pide_a_la_api_un_campo_que_el_objeto_puede_no_tener(self):
        with self._respuesta({"id": "9", "name": "David", "metadata": {"type": "user"}}) as get:
            facebook.identificar("tok")
        campos = get.call_args[1]["params"]
        self.assertNotIn("category", campos.get("fields", ""))
        self.assertEqual(campos.get("metadata"), 1)

    def test_reconoce_un_token_de_pagina(self):
        with self._respuesta({"id": "7", "name": "Mi página", "metadata": {"type": "page"}}):
            self.assertEqual(facebook.identificar("tok")["tipo"], "pagina")

    def test_sin_metadata_cae_a_debug_token(self):
        respuestas = [_Respuesta(200, {"id": "9", "name": "David"}),
                      _Respuesta(200, {"data": {"type": "USER"}})]
        with mock.patch.object(facebook.requests, "get", side_effect=respuestas):
            self.assertEqual(facebook.identificar("tok", "app", "secreto")["tipo"], "usuario")

    def test_un_token_de_verdad_roto_si_da_error(self):
        with self._respuesta({"error": {"message": "Session has expired"}}, status=400):
            self.assertIn("expired", facebook.identificar("tok")["error"])


class TestPublicar(unittest.TestCase):

    def _pagina(self, **env):
        p = config.Pagina(nombre="X", page_id_env="T_ID", token_env="T_TOKEN")
        return p, mock.patch.dict("os.environ", env, clear=False)

    def test_sin_credenciales_no_llama_a_facebook(self):
        p, env = self._pagina(T_ID="", T_TOKEN="")
        with env, mock.patch.object(facebook.requests, "post") as post:
            with self.assertRaises(facebook.FacebookError):
                facebook.publicar(p, "hola", Path(__file__))
            post.assert_not_called()

    def test_manda_el_caption_y_la_foto_a_photos(self):
        p, env = self._pagina(T_ID="123", T_TOKEN="tok")
        with env, mock.patch.object(facebook.requests, "post",
                                    return_value=_Respuesta(200, {"id": "1", "post_id": "123_9"})) as post:
            self.assertEqual(facebook.publicar(p, "el caption", Path(__file__)), "123_9")
        url = post.call_args[0][0]
        self.assertTrue(url.endswith("/123/photos"), url)
        self.assertEqual(post.call_args[1]["data"]["message"], "el caption")
        self.assertEqual(post.call_args[1]["data"]["access_token"], "tok")
        self.assertIn("source", post.call_args[1]["files"])

    def test_un_error_de_meta_levanta_con_su_texto(self):
        p, env = self._pagina(T_ID="123", T_TOKEN="tok")
        with env, mock.patch.object(facebook.requests, "post",
                                    return_value=_Respuesta(400, {"error": {"message": "(#200) permiso"}})):
            with self.assertRaises(facebook.FacebookError) as ctx:
                facebook.publicar(p, "x", Path(__file__))
        self.assertIn("(#200)", str(ctx.exception))


# ---------------------------------------------------------------------------
# Los scripts.
# ---------------------------------------------------------------------------

def _llama_a(ruta: Path, nombres) -> bool:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            fn = nodo.func
            nombre = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if nombre in nombres:
                return True
    return False


class _Bot:
    """Caja para mirar qué mandó el bot a Telegram sin tocar la red."""

    def __init__(self, chat="55"):
        self.textos, self.fotos, self.botones, self.acuses = [], [], [], []
        self.chat = chat

    def __enter__(self):
        self._p = [
            mock.patch.object(telegram, "chat", return_value=self.chat),
            mock.patch.object(telegram, "enviar", side_effect=self._enviar),
            mock.patch.object(telegram, "enviar_foto", side_effect=self._foto),
            mock.patch.object(telegram, "responder_boton", side_effect=self.acuses.append),
        ]
        for p in self._p:
            p.start()
        return self

    def __exit__(self, *a):
        for p in self._p:
            p.stop()

    def _enviar(self, texto, botones=None, destino=None):
        self.textos.append(texto)
        self.botones.append(botones)
        return {}

    def _foto(self, ruta, pie="", botones=None, destino=None):
        self.fotos.append((Path(ruta), pie))
        return {}

    @property
    def todo(self):
        return "\n".join(self.textos)

    def datos_de_botones(self):
        return [d for fila in self.botones if fila for linea in fila for _, d in linea]


def _update(texto=None, data=None, chat="55"):
    if data is not None:
        return {"update_id": 1,
                "callback_query": {"id": "cb", "data": data, "message": {"chat": {"id": chat}}}}
    return {"update_id": 1, "message": {"text": texto, "chat": {"id": chat}}}


class TestElBot(unittest.TestCase):
    """El bot muestra y publica con el botón. La regla que no se toca: nada
    llega a Facebook sin que lo aprieten."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        for modulo, campo, valor in ((frases, "PUBLICADAS", d / "publicadas.json"),
                                     (diseno, "FLYERS", d / "flyers")):
            p = mock.patch.object(modulo, campo, valor)
            p.start()
            self.addCleanup(p.stop)
        # Si esto no aislara de verdad, las pruebas escribirían en los datos
        # reales; pasó, y el síntoma fue otra prueba fallando por un archivo
        # que no era suyo.
        self.assertEqual(frases.publicadas(), {})
        # Para las pruebas del camino de Facebook, una página SIN Instagram:
        # si tomaran el valor de la config, cambiarlo las rompería aunque el
        # camino que prueban siga igual.
        self.solo_fb = config.cargar()
        self.solo_fb.instagram = False

    def test_un_mensaje_de_texto_no_publica_nunca(self):
        with _Bot() as b, mock.patch.object(facebook, "publicar",
                                            side_effect=AssertionError("publicó")):
            bot.atender(_update(texto="publica todo ya"), PAGINA)
        self.assertIn("Publicar", b.todo)          # es el menú, que lo explica
        self.assertEqual(frases.publicadas(), {})

    def test_el_chat_de_otro_se_ignora(self):
        # El nombre de un bot se puede encontrar; sin este filtro, cualquiera
        # publicaría en la página.
        with _Bot(chat="55") as b, mock.patch.object(facebook, "publicar",
                                                     side_effect=AssertionError("publicó")):
            bot.atender(_update(data="publicar:aut-01", chat="99"), PAGINA)
        self.assertEqual(b.textos, [])
        self.assertEqual(b.acuses, [])

    def test_ver_la_que_toca_manda_el_flyer_y_el_texto(self):
        with _Bot() as b:
            bot.atender(_update(data="siguiente"), PAGINA)
        self.assertEqual(len(b.fotos), 1)
        ruta, pie = b.fotos[0]
        self.assertTrue(ruta.exists())
        self.assertIn("aut-01", pie)
        self.assertIn("Hablarte mal", b.todo)      # el caption que saldría
        self.assertIn("publicar:aut-01", b.datos_de_botones())

    def test_con_instagram_prendido_el_bot_publica_en_las_dos(self):
        pagina = config.cargar()
        pagina.instagram = True
        with _Bot() as b, mock.patch.object(instagram, "publicar_las_dos",
                                            return_value={"post_id": "105_1", "instagram": "ig1",
                                                          "error_instagram": ""}) as fn:
            bot.atender(_update(data="publicar:aut-01"), pagina)
        fn.assert_called_once()
        self.assertIn("Instagram", b.todo)
        self.assertIn("aut-01", frases.publicadas())

    def test_si_instagram_falla_el_bot_igual_anota_la_frase(self):
        pagina = config.cargar()
        pagina.instagram = True
        with _Bot() as b, mock.patch.object(instagram, "publicar_las_dos",
                                            return_value={"post_id": "105_1", "instagram": "",
                                                          "error_instagram": "sin permiso"}):
            bot.atender(_update(data="publicar:aut-01"), pagina)
        self.assertIn("aut-01", frases.publicadas())
        self.assertIn("NO salió", b.todo)

    def test_el_boton_publicar_es_el_unico_que_publica(self):
        with _Bot() as b, mock.patch.object(facebook, "publicar", return_value="105_1") as fb:
            bot.atender(_update(data="publicar:aut-01"), self.solo_fb)
        fb.assert_called_once()
        self.assertEqual(fb.call_args[0][1], frases.caption(
            frases.por_id(TEMAS, "aut-01"), TEMAS[2], PAGINA))
        self.assertIn("aut-01", frases.publicadas())
        self.assertIn("facebook.com/105_1", b.todo)

    def test_no_publica_dos_veces_la_misma(self):
        with _Bot(), mock.patch.object(facebook, "publicar", return_value="105_1"):
            bot.atender(_update(data="publicar:aut-01"), self.solo_fb)
        with _Bot() as b, mock.patch.object(facebook, "publicar",
                                            side_effect=AssertionError("publicó de nuevo")):
            bot.atender(_update(data="publicar:aut-01"), self.solo_fb)
        self.assertIn("ya había salido", b.todo)

    def test_si_facebook_falla_no_la_anota_como_publicada(self):
        # Anotarla igual la perdería: no salió y no volvería a tocar.
        with _Bot() as b, mock.patch.object(facebook, "publicar",
                                            side_effect=facebook.FacebookError("(#200) permiso")):
            bot.atender(_update(data="publicar:aut-01"), self.solo_fb)
        self.assertEqual(frases.publicadas(), {})
        self.assertIn("(#200)", b.todo)

    def test_saltar_la_descarta_y_ofrece_la_siguiente(self):
        with _Bot() as b, mock.patch.object(facebook, "publicar",
                                            side_effect=AssertionError("publicó")):
            bot.atender(_update(data="saltar:aut-01"), PAGINA)
        self.assertIn("aut-01", frases.publicadas())
        self.assertEqual(frases.publicadas()["aut-01"]["post_id"], "")
        self.assertNotIn("publicar:aut-01", b.datos_de_botones())

    def test_el_boton_siempre_recibe_su_acuse(self):
        # Sin esto el teléfono se queda con el relojito girando.
        with _Bot() as b:
            bot.atender(_update(data="estado"), PAGINA)
        self.assertEqual(len(b.acuses), 1)

    def test_que_queda_cuenta_por_tema(self):
        # El total se calcula, no se escribe: si se fijara acá, cada frase
        # nueva rompería la prueba sin que nada esté mal.
        n = len(frases.todas(TEMAS))
        with _Bot() as b:
            bot.atender(_update(data="estado"), PAGINA)
        self.assertIn("Quedan %d de %d" % (n, n), b.todo)
        self.assertIn("autoestima", b.todo)

    def test_un_banco_roto_frena_la_publicacion(self):
        roto = [tema(frases=[una(texto="Esto cura la ansiedad para siempre.")])]
        with _Bot() as b, mock.patch.object(frases, "leer", return_value=roto):
            bot.atender(_update(data="siguiente"), PAGINA)
        self.assertEqual(b.fotos, [])
        self.assertIn("problemas", b.todo)


def _chat_id():
    import importlib.util
    spec = importlib.util.spec_from_file_location("cid", ROOT / "scripts" / "chat_id.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestElEnv(unittest.TestCase):

    def test_pone_una_clave_nueva_sin_tocar_las_otras(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / ".env"
            ruta.write_text("# un comentario\nPSI_FB_PAGE_ID=7\n", encoding="utf-8")
            entorno.guardar({"TELEGRAM_CHAT_ID": "55"}, ruta)
            texto = ruta.read_text(encoding="utf-8")
            self.assertIn("# un comentario", texto)
            self.assertIn("PSI_FB_PAGE_ID=7", texto)
            self.assertIn("TELEGRAM_CHAT_ID=55", texto)

    def test_reemplaza_una_que_ya_estaba_sin_duplicarla(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / ".env"
            ruta.write_text("PSI_FB_PAGE_ID=7\nPSI_FB_PAGE_TOKEN=viejo\n", encoding="utf-8")
            entorno.guardar({"PSI_FB_PAGE_TOKEN": "nuevo"}, ruta)
            texto = ruta.read_text(encoding="utf-8")
            self.assertIn("PSI_FB_PAGE_TOKEN=nuevo", texto)
            self.assertNotIn("viejo", texto)
            self.assertEqual(texto.count("PSI_FB_PAGE_TOKEN"), 1)

    def test_queda_en_600_porque_son_credenciales(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = entorno.guardar({"X": "1"}, Path(d) / ".env")
            self.assertEqual(ruta.stat().st_mode & 0o777, 0o600)

    def test_no_deja_un_parcial(self):
        with tempfile.TemporaryDirectory() as d:
            entorno.guardar({"X": "1"}, Path(d) / ".env")
            self.assertFalse(list(Path(d).glob("*.parcial")))


class TestElChatId(unittest.TestCase):

    def setUp(self):
        self.chats_de = _chat_id().chats_de

    def test_lo_saca_de_un_mensaje(self):
        novedades = [{"message": {"chat": {"id": 55, "first_name": "José", "last_name": "Del Carpio"}}}]
        self.assertEqual(self.chats_de(novedades), {"55": "José Del Carpio"})

    def test_tambien_de_un_boton_o_de_un_mensaje_editado(self):
        # Si solo mirara "message", alguien que apretó un botón y nada más
        # quedaría sin chat id y el script diría que no le escribió nunca.
        self.assertEqual(self.chats_de([{"callback_query": {"message": {"chat": {"id": 7}}}}]), {"7": ""})
        self.assertEqual(self.chats_de([{"edited_message": {"chat": {"id": 8}}}]), {"8": ""})

    def test_no_repite_el_mismo_chat(self):
        novedades = [{"message": {"chat": {"id": 55, "first_name": "José"}}}] * 3
        self.assertEqual(len(self.chats_de(novedades)), 1)

    def test_sin_novedades_no_inventa_ninguno(self):
        self.assertEqual(self.chats_de([]), {})
        self.assertEqual(self.chats_de([{"update_id": 1}]), {})


class TestElWebhook(unittest.TestCase):
    """Telegram entrega los mensajes de una de dos maneras y no de las dos: o
    el bot los pide (getUpdates) o los empuja a una URL (webhook). Con un
    webhook puesto, el bot no recibe nada y el error no lo dice en castellano."""

    def test_reconoce_el_conflicto(self):
        e = telegram.TelegramError("Telegram dijo que no: Conflict: can't use getUpdates "
                                   "method while webhook is active; use deleteWebhook first")
        self.assertTrue(telegram.hay_conflicto_de_webhook(e))

    def test_no_confunde_cualquier_otro_error(self):
        self.assertFalse(telegram.hay_conflicto_de_webhook(
            telegram.TelegramError("Unauthorized")))

    def test_sin_webhook_devuelve_vacio(self):
        with mock.patch.object(telegram, "_llamar", return_value={"url": ""}):
            self.assertEqual(telegram.webhook(), {})

    def test_con_webhook_dice_a_donde_apunta(self):
        with mock.patch.object(telegram, "_llamar",
                               return_value={"url": "https://x.com/hook", "pending_update_count": 3}):
            self.assertEqual(telegram.webhook()["url"], "https://x.com/hook")

    def test_borrarlo_no_tira_los_mensajes_pendientes(self):
        # Si el webhook estaba cortado, esos mensajes son lo único que quedó.
        with mock.patch.object(telegram, "_llamar", return_value={}) as llamar:
            telegram.borrar_webhook()
        self.assertEqual(llamar.call_args[0][0], "deleteWebhook")
        self.assertFalse(llamar.call_args[1]["drop_pending_updates"])

    def test_el_script_explica_el_conflicto_en_vez_de_repetir_el_error(self):
        cid = _chat_id()
        llamadas = {"getMe": {"username": "bot"},
                    "getWebhookInfo": {"url": "https://x.com/hook"}}

        def falso(metodo, **kw):
            if metodo == "getUpdates":
                raise telegram.TelegramError("Conflict: can't use getUpdates method "
                                             "while webhook is active")
            return llamadas[metodo]

        with mock.patch.object(telegram, "_llamar", side_effect=falso), \
                mock.patch.object(telegram, "token", return_value="t"), \
                mock.patch("builtins.print") as imprimir:
            self.assertEqual(cid.main([]), 1)
        dicho = " ".join(str(c[0][0]) for c in imprimir.call_args_list if c[0])
        self.assertIn("WEBHOOK", dicho)
        self.assertIn("https://x.com/hook", dicho)
        self.assertIn("--borrar-webhook", dicho)


class TestFaltaElEmpezar(unittest.TestCase):
    """«chat not found» casi nunca es un chat id mal puesto: es que la persona
    nunca abrió ESE bot. Un bot no puede empezar una conversación."""

    def test_lo_reconoce(self):
        self.assertTrue(telegram.falta_el_empezar(
            telegram.TelegramError("Telegram dijo que no: Bad Request: chat not found")))

    def test_no_confunde_otro_error(self):
        self.assertFalse(telegram.falta_el_empezar(telegram.TelegramError("Unauthorized")))

    def test_el_script_lo_explica_en_vez_de_repetir_el_error(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("bt", ROOT / "scripts" / "bot.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with mock.patch.object(telegram, "configurado", return_value=True), \
                mock.patch.object(telegram, "token", return_value="t"), \
                mock.patch.object(telegram, "chat", return_value="55"), \
                mock.patch.object(telegram, "quien_soy", return_value={"username": "psibot"}), \
                mock.patch.object(bot, "menu",
                                  side_effect=telegram.TelegramError("Bad Request: chat not found")), \
                mock.patch("builtins.print") as imprimir:
            self.assertEqual(mod.main(["--saludar"]), 1)
        dicho = " ".join(str(c[0][0]) for c in imprimir.call_args_list if c[0])
        self.assertIn("@psibot", dicho)
        self.assertIn("EN TELEGRAM", dicho)


class TestLosCaminosPorDefecto(unittest.TestCase):
    """Un `ruta: Path = CONSTANTE` en la firma se evalúa al importar, así que
    queda clavado y cambiar la constante no cambia nada: lo que corre sigue
    siendo el camino viejo. Es un error que no se ve, porque las pruebas que
    pasan la ruta a mano nunca ejercitan el valor por defecto."""

    def test_instagram_llama_a_facebook_por_el_modulo(self):
        # Un `from .facebook import subir_foto` ata el nombre a la función que
        # había al importar, así que parchear `facebook.subir_foto` no cambia
        # lo que corre. Pasó, y el síntoma fue una prueba saliendo a la red.
        import ast
        arbol = ast.parse((ROOT / "src" / "instagram.py").read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module == "facebook":
                traidos = {a.name for a in nodo.names}
                self.assertFalse(traidos - {"GRAPH", "FacebookError"}, traidos)

    def test_ninguna_firma_clava_una_ruta_ni_una_funcion(self):
        # Vale igual para una función de otro módulo puesta por defecto: el
        # bot tenía `publicar_fn=facebook.publicar` y quedaba atado a esa
        # función desde el import.
        import inspect
        for modulo in (frases, diseno, bot, telegram, facebook, libro, entorno):
            for nombre, fn in vars(modulo).items():
                if not inspect.isfunction(fn) or fn.__module__ != modulo.__name__:
                    continue
                try:
                    firma = inspect.signature(fn)
                except (TypeError, ValueError):
                    continue
                for param, valor in firma.parameters.items():
                    clavado = isinstance(valor.default, Path) or (
                        callable(valor.default)
                        and getattr(valor.default, "__module__", "").startswith("src."))
                    if clavado:
                        self.fail("%s.%s tiene %s=%r clavado en la firma, así que parchear "
                                  "el original no cambia nada"
                                  % (modulo.__name__, nombre, param, valor.default))

    def test_cambiar_la_constante_cambia_donde_escribe(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "publicadas.json"
            with mock.patch.object(frases, "PUBLICADAS", ruta):
                frases.anotar_publicada("aut-01", date(2026, 11, 1), "1", "x")
                self.assertEqual(list(frases.publicadas()), ["aut-01"])
            self.assertTrue(ruta.exists())


class TestElOffsetDeTelegram(unittest.TestCase):

    def test_se_guarda_antes_de_atender(self):
        # Si se guardara después, un mensaje que revienta volvería a llegar
        # para siempre y el bot no atendería nada más.
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "offset.json"
            with mock.patch.object(telegram, "_llamar",
                                   return_value=[{"update_id": 7}, {"update_id": 9}]):
                telegram.recoger(espera=0, ruta=ruta)
            self.assertEqual(telegram._offset(ruta), 10)

    def test_sin_novedades_no_lo_mueve(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "offset.json"
            telegram._guardar_offset(4, ruta)
            with mock.patch.object(telegram, "_llamar", return_value=[]):
                telegram.recoger(espera=0, ruta=ruta)
            self.assertEqual(telegram._offset(ruta), 4)

    def test_un_archivo_roto_no_lo_tumba(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "offset.json"
            ruta.write_text("{roto", encoding="utf-8")
            self.assertEqual(telegram._offset(ruta), 0)

    def test_el_pie_de_una_foto_se_recorta_a_1024(self):
        # Telegram rechaza el mensaje entero si el pie se pasa, no lo recorta.
        with mock.patch.object(telegram, "_llamar", return_value={}) as llamar, \
                mock.patch.object(telegram, "chat", return_value="55"):
            telegram.enviar_foto(Path(__file__), "x" * 2000)
        self.assertEqual(len(llamar.call_args[1]["caption"]), 1024)


def _token_permanente():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tp", ROOT / "scripts" / "token_permanente.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestElegirLaPagina(unittest.TestCase):
    """Con varias páginas, cuál. Elegir sola es como se publica en la
    página equivocada, y eso ya pasó una vez."""

    PAGINAS = [{"id": "1348366165029009", "name": "Luis Del Carpio Merino"},
               {"id": "105045932147427", "name": "Josdelcarpio"},
               {"id": "108520517695384", "name": "Ian de Travesía"}]

    def setUp(self):
        self.elegir = _token_permanente().elegir_pagina

    def test_con_varias_y_sin_decir_cual_no_elige(self):
        elegida, motivo = self.elegir(self.PAGINAS, None, None)
        self.assertIsNone(elegida)
        self.assertIn("3", motivo)

    def test_elige_por_id(self):
        elegida, _ = self.elegir(self.PAGINAS, "105045932147427", None)
        self.assertEqual(elegida["name"], "Josdelcarpio")

    def test_elige_por_parte_del_nombre_sin_acentos(self):
        elegida, _ = self.elegir(self.PAGINAS, "travesia", None)
        self.assertEqual(elegida["id"], "108520517695384")

    def test_un_nombre_ambiguo_no_elige(self):
        elegida, motivo = self.elegir(self.PAGINAS, "carpio", None)
        self.assertIsNone(elegida)
        self.assertIn("mas de una", motivo)

    def test_usa_el_id_del_env_cuando_no_se_pide_otra(self):
        elegida, _ = self.elegir(self.PAGINAS, None, "108520517695384")
        self.assertEqual(elegida["name"], "Ian de Travesía")

    def test_un_id_del_env_que_no_existe_no_elige(self):
        elegida, motivo = self.elegir(self.PAGINAS, None, "999")
        self.assertIsNone(elegida)
        self.assertIn("999", motivo)

    def test_con_una_sola_pagina_no_pregunta(self):
        elegida, _ = self.elegir(self.PAGINAS[:1], None, None)
        self.assertEqual(elegida["id"], "1348366165029009")

    def test_lo_pedido_le_gana_al_env(self):
        elegida, _ = self.elegir(self.PAGINAS, "Josdelcarpio", "1348366165029009")
        self.assertEqual(elegida["id"], "105045932147427")


class TestInstagram(unittest.TestCase):
    """Solo averigua si la cuenta está en condiciones. Nada de esto publica."""

    def _pagina(self):
        p = config.Pagina(nombre="X", page_id_env="T_ID", token_env="T_TOKEN")
        return p, mock.patch.dict("os.environ", {"T_ID": "105", "T_TOKEN": "tok"})

    def test_lee_la_cuenta_vinculada_preguntando_por_la_pagina(self):
        # Se pregunta por la PÁGINA: el vínculo lo declara ella, y preguntar
        # al revés necesita un id que todavía no se tiene.
        p, env = self._pagina()
        respuesta = {"name": "Josdelcarpio",
                     "instagram_business_account": {"id": "77", "username": "jos"}}
        with env, mock.patch.object(facebook.requests, "get",
                                    return_value=_Respuesta(200, respuesta)) as get:
            cuenta = instagram.cuenta_vinculada(p)
        self.assertTrue(get.call_args[0][0].endswith("/105"))
        self.assertEqual(cuenta["id"], "77")
        self.assertEqual(cuenta["usuario"], "jos")

    def test_sin_cuenta_vinculada_no_inventa_una(self):
        p, env = self._pagina()
        with env, mock.patch.object(facebook.requests, "get",
                                    return_value=_Respuesta(200, {"name": "Josdelcarpio"})):
            self.assertEqual(instagram.cuenta_vinculada(p)["id"], "")

    def test_dice_cuales_permisos_faltan(self):
        self.assertEqual(instagram.permisos_que_faltan(["pages_manage_posts"]),
                         ["instagram_basic", "instagram_content_publish"])
        self.assertEqual(instagram.permisos_que_faltan(
            ["instagram_basic", "instagram_content_publish", "pages_manage_posts"]), [])

    def test_no_poder_preguntar_no_es_lo_mismo_que_no_tener(self):
        # [] es «no tiene ninguno» y None es «no pude averiguarlo». Confundirlos
        # manda a regenerar un token que estaba bien.
        p, env = self._pagina()
        with env, mock.patch.object(facebook.requests, "get",
                                    return_value=_Respuesta(400, {"error": {"message": "x"}})):
            self.assertIsNone(instagram.scopes_del_token(p, "app", "secreto"))
        with env, mock.patch.object(facebook.requests, "get",
                                    return_value=_Respuesta(200, {"data": {"scopes": []}})):
            self.assertEqual(instagram.scopes_del_token(p, "app", "secreto"), [])

    def test_la_url_publica_sale_de_la_foto_mas_grande(self):
        # Se elige por ancho y no por posición: si Meta cambia el orden, lo
        # que saldría en Instagram es una miniatura, y eso se vería recién ahí.
        p, env = self._pagina()
        imagenes = {"images": [{"width": 320, "source": "chica.jpg"},
                               {"width": 2048, "source": "grande.jpg"},
                               {"width": 1080, "source": "media.jpg"}]}
        with env, mock.patch.object(facebook.requests, "get",
                                    return_value=_Respuesta(200, imagenes)):
            self.assertEqual(facebook.url_de_la_foto(p, "7"), "grande.jpg")

    def test_subir_foto_devuelve_los_dos_ids(self):
        # El del post sirve para los comentarios; el de la foto, para pedirle
        # a Meta la dirección pública que necesita Instagram.
        p, env = self._pagina()
        with env, mock.patch.object(facebook.requests, "post",
                                    return_value=_Respuesta(200, {"id": "9", "post_id": "105_1"})):
            salida = facebook.subir_foto(p, "hola", Path(__file__))
        self.assertEqual(salida, {"post_id": "105_1", "foto_id": "9"})

    def test_espera_a_que_instagram_termine_de_procesar(self):
        p, env = self._pagina()
        estados = [_Respuesta(200, {"status_code": "IN_PROGRESS"}),
                   _Respuesta(200, {"status_code": "FINISHED"})]
        with env, mock.patch.object(facebook.requests, "get", side_effect=estados), \
                mock.patch.object(instagram.requests, "post",
                                  side_effect=[_Respuesta(200, {"id": "cont"}),
                                               _Respuesta(200, {"id": "ig1"})]) as post:
            ig = instagram.publicar(p, "texto", "http://x/foto.jpg", cuenta="77", paso=0)
        self.assertEqual(ig, "ig1")
        self.assertTrue(post.call_args_list[0][0][0].endswith("/77/media"))
        self.assertTrue(post.call_args_list[1][0][0].endswith("/77/media_publish"))

    def test_si_instagram_rechaza_la_imagen_no_publica(self):
        p, env = self._pagina()
        with env, mock.patch.object(facebook.requests, "get",
                                    return_value=_Respuesta(200, {"status_code": "ERROR",
                                                                  "status": "mala proporción"})), \
                mock.patch.object(instagram.requests, "post",
                                  return_value=_Respuesta(200, {"id": "cont"})) as post:
            with self.assertRaises(instagram.InstagramError):
                instagram.publicar(p, "t", "http://x/f.jpg", cuenta="77", paso=0)
        self.assertEqual(len(post.call_args_list), 1)   # no llegó a media_publish

    def test_si_instagram_falla_el_post_de_facebook_igual_cuenta(self):
        # Facebook ya salió. Levantar la excepción dejaría la frase sin anotar
        # y mañana se ofrecería de nuevo, ya publicada.
        p, env = self._pagina()
        with env, mock.patch.object(facebook, "subir_foto",
                                    return_value={"post_id": "105_1", "foto_id": "9"}), \
                mock.patch.object(facebook, "url_de_la_foto",
                                  side_effect=facebook.FacebookError("(#100) nada")):
            salida = instagram.publicar_las_dos(p, "texto", Path(__file__))
        self.assertEqual(salida["post_id"], "105_1")
        self.assertEqual(salida["instagram"], "")
        self.assertIn("(#100)", salida["error_instagram"])

    def test_el_flyer_entra_en_la_proporcion_que_instagram_acepta(self):
        # 1080x1350 es 4:5, el más alto que Instagram admite. El día que
        # cambie el lienzo, Instagram rechaza el contenedor con un error que
        # no dice que el problema es la proporción.
        proporcion = diseno.W / diseno.H
        self.assertGreaterEqual(round(proporcion, 4), instagram.PROPORCION_MINIMA)
        self.assertLessEqual(proporcion, instagram.PROPORCION_MAXIMA)

    def test_el_comprobador_no_pide_un_servidor(self):
        # Pedía PUBLIC_BASE_URL de cuando no existía el camino de la foto de
        # Facebook, y lo siguió pidiendo después: decía que faltaba algo que
        # ya estaba resuelto, con la cuenta vinculada y los permisos puestos.
        texto = (ROOT / "scripts" / "revisar_instagram.py").read_text(encoding="utf-8")
        self.assertNotIn('environ.get("PUBLIC_BASE_URL")', texto)

    def test_la_pagina_publica_en_las_dos(self):
        # Comprobado contra Meta el 2026-10-23: @jos.delcarpio vinculada y los
        # dos permisos presentes.
        self.assertTrue(config.cargar().instagram)

    def test_el_comprobador_no_publica(self):
        # Mismo criterio que con Facebook: se lee el AST y se exige que no
        # llame a nada que escriba.
        self.assertFalse(_llama_a(ROOT / "scripts" / "revisar_instagram.py",
                                  {"publicar", "post"}))


def _turno():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pt", ROOT / "scripts" / "publicar_turno.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestLaPrueba(unittest.TestCase):
    """Ocho por día durante una semana, rotando el estilo, para poder
    comparar después."""

    HORAS = [8, 10, 12, 14, 16, 18, 20, 22]

    def _dia(self, i=0):
        return date.fromordinal(date(2026, 10, 24).toordinal() + i)

    def test_los_posts_de_un_dia_llevan_estilos_distintos(self):
        # Lo pidió el usuario: variar dentro del día.
        dia = self._dia()
        del_dia = [diseno.estilo_del_turno(dia, h, self.HORAS) for h in self.HORAS]
        self.assertEqual(len(set(del_dia)), len(diseno.ESTILOS))
        self.assertEqual(del_dia[:4], del_dia[4:])

    def test_sale_de_la_fecha_y_la_hora_y_no_de_cuantos_se_publicaron(self):
        # Volver a dibujar el mismo post da el mismo estilo -el flyer aprobado
        # es el que sale- y un día salteado no corre la rueda.
        dia = self._dia()
        uno = diseno.estilo_del_turno(dia, 12, self.HORAS)
        self.assertEqual(uno, diseno.estilo_del_turno(dia, 12, self.HORAS))

    def test_el_reparto_se_corre_cada_dia(self):
        # Sin esto, las 8 llevarían siempre el mismo estilo y no habría forma
        # de separar el estilo de la hora.
        a_las_ocho = [diseno.estilo_del_turno(self._dia(i), 8, self.HORAS) for i in range(4)]
        self.assertEqual(len(set(a_las_ocho)), len(diseno.ESTILOS))

    def test_en_una_semana_cada_estilo_sale_igual_y_en_todas_las_horas(self):
        cuantos, horas_de = {}, {}
        for i in range(7):
            for h in self.HORAS:
                e = diseno.estilo_del_turno(self._dia(i), h, self.HORAS)
                cuantos[e] = cuantos.get(e, 0) + 1
                horas_de.setdefault(e, set()).add(h)
        self.assertEqual(set(cuantos.values()), {14})
        for e, hs in horas_de.items():
            self.assertEqual(len(hs), len(self.HORAS), e)

    def test_el_registro_guarda_con_que_salio_el_post(self):
        # Sin esto no se puede comparar nada: el post ya salió y Facebook no
        # sabe con qué diseño se dibujó.
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "publicadas.json"
            frases.anotar_publicada("aut-01", date(2026, 11, 1), "105_1", "X", ruta,
                                    extra={"hora": 8, "tema": "autoestima", "eje": "nucleo",
                                           "estilo": "ficha", "instagram": "ig1"})
            guardado = frases.publicadas(ruta)["aut-01"]
        self.assertEqual(guardado["estilo"], "ficha")
        self.assertEqual(guardado["hora"], 8)
        self.assertEqual(guardado["post_id"], "105_1")

    def test_fuera_de_hora_no_publica(self):
        mod = _turno()
        with mock.patch.object(facebook, "publicar", side_effect=AssertionError("publicó")), \
                mock.patch("builtins.print"):
            self.assertEqual(mod.main(["--ahora", "2026-10-23T09"]), 0)

    def test_en_la_misma_hora_no_publica_dos_veces(self):
        # Un reintento, el reloj que se atrasa o dos programadores encendidos
        # publicarían dos frases.
        mod = _turno()
        ya = {"aut-01": {"dia": "2026-10-23", "hora": 8, "post_id": "1"}}
        self.assertTrue(mod.ya_salio_en_esta_hora(ya, datetime(2026, 10, 23, 8)))
        self.assertFalse(mod.ya_salio_en_esta_hora(ya, datetime(2026, 10, 23, 10)))
        self.assertFalse(mod.ya_salio_en_esta_hora(ya, datetime(2026, 10, 24, 8)))

    def test_ocho_horas_y_ninguna_pegada(self):
        p = config.cargar()
        self.assertEqual(len(p.horas), 8)
        self.assertEqual(sorted(p.horas), p.horas)
        for a, b in zip(p.horas, p.horas[1:]):
            self.assertGreaterEqual(b - a, 2, (a, b))


class TestLaRampa(unittest.TestCase):
    """4 posts 3 días, 5 posts 4 días, 6 posts 5 días, y 8 de ahí en adelante."""

    def setUp(self):
        self.p = config.cargar()
        self.desde = date(2026, 10, 24)

    def _dia(self, n):
        return date.fromordinal(self.desde.toordinal() + n - 1)

    def test_la_rampa_es_la_que_se_pidio(self):
        esperado = ([4] * 3) + ([5] * 4) + ([6] * 5) + ([8] * 4)
        salen = [parrilla.posts_del_dia(self.p, self.desde, self._dia(n))
                 for n in range(1, len(esperado) + 1)]
        self.assertEqual(salen, esperado)

    def test_las_horas_se_reparten_a_lo_largo_del_dia(self):
        # Con cuatro posts, las primeras cuatro de la parrilla los dejarían
        # todos antes del mediodía y la tarde vacía.
        horas = parrilla.horas_del_dia(self.p, self.desde, self._dia(1))
        self.assertEqual(len(horas), 4)
        self.assertGreaterEqual(max(horas), 20)
        for a, b in zip(horas, horas[1:]):
            self.assertGreaterEqual(b - a, 2)

    def test_cada_post_del_dia_lleva_un_diseno_distinto(self):
        # Lo pidió el usuario, y la rampa lo rompía: contando el lugar sobre
        # las ocho horas, un día de cuatro posts usaba posiciones pares y
        # salían solo DOS estilos.
        for n in (1, 4, 8, 13):
            dia = self._dia(n)
            horas = parrilla.horas_del_dia(self.p, self.desde, dia)
            estilos = [diseno.estilo_del_turno(dia, h, horas) for h in horas]
            self.assertEqual(len(set(estilos)), min(len(horas), len(diseno.ESTILOS)),
                             (n, estilos))

    def test_el_primer_dia_sale_del_primer_post_publicado(self):
        # Así la rampa empieza sola y no hay una fecha escrita a mano que
        # alguien tenga que acordarse de cambiar.
        ya = {"a": {"dia": "2026-11-03", "post_id": "1"},
              "b": {"dia": "2026-10-30", "post_id": "2"},
              "c": {"dia": "2026-10-28", "post_id": ""}}
        self.assertEqual(frases.primer_dia(ya), date(2026, 10, 30))
        self.assertIsNone(frases.primer_dia({}))

    def test_el_calendario_dice_cuando_se_acaba_el_banco(self):
        filas = parrilla.calendario(self.p, self.desde, 113)
        self.assertEqual(sum(f["posts"] for f in filas), 113)
        self.assertEqual(filas[-1]["quedan"], 0)
        self.assertEqual(filas[-1]["numero"], 19)

    def test_el_ultimo_dia_solo_saca_las_que_quedan(self):
        filas = parrilla.calendario(self.p, self.desde, 10)
        self.assertEqual([f["posts"] for f in filas], [4, 4, 2])


class TestLaMedicion(unittest.TestCase):

    FILAS = [{"estilo": "regla", "tema": "apego", "reacciones": 10},
             {"estilo": "regla", "tema": "apego", "reacciones": 12},
             {"estilo": "regla", "tema": "duelo", "reacciones": 200},
             {"estilo": "ficha", "tema": "apego", "reacciones": 20},
             {"estilo": "ficha", "tema": "duelo", "reacciones": 22}]

    def test_usa_la_mediana_y_no_el_promedio(self):
        # El 200 es un post que se compartió de más. Con promedio, «regla»
        # ganaría 74 a 21 por un solo caso.
        por_estilo = dict((e, m) for e, _, m in medir.por(self.FILAS, "estilo"))
        self.assertEqual(por_estilo["regla"], 12)
        self.assertEqual(por_estilo["ficha"], 21)

    def test_dice_cuantos_posts_tiene_cada_grupo(self):
        self.assertEqual(dict((e, n) for e, n, _ in medir.por(self.FILAS, "estilo")),
                         {"regla": 3, "ficha": 2})

    def test_avisa_cuando_el_grupo_es_chico(self):
        self.assertFalse(medir.alcanza(2))
        self.assertTrue(medir.alcanza(medir.MINIMO))

    def test_cuenta_los_dias_y_no_solo_los_posts(self):
        # El número de días sigue sirviendo: dice si un grupo vio días buenos
        # y malos o se concentró en pocos.
        filas = [{"estilo": "regla", "dia": "2026-10-24", "reacciones": 5},
                 {"estilo": "regla", "dia": "2026-10-24", "reacciones": 7},
                 {"estilo": "regla", "dia": "2026-10-28", "reacciones": 6},
                 {"estilo": "ficha", "dia": "2026-10-25", "reacciones": 9}]
        self.assertEqual(medir.dias_por(filas, "estilo"), {"regla": 2, "ficha": 1})
        self.assertEqual(dict((e, n) for e, n, _ in medir.por(filas, "estilo")),
                         {"regla": 3, "ficha": 1})

    def test_una_frase_salteada_no_se_mide(self):
        # No salió, así que no tiene números: contarla como cero hundiría la
        # mediana de su grupo.
        publicadas = {"aut-01": {"dia": "2026-11-01", "post_id": "", "estilo": "regla"},
                      "lim-01": {"dia": "2026-11-02", "post_id": "1", "estilo": "regla"}}
        filas = medir.juntar(PAGINA, publicadas, pedir_fb=lambda p, i: {"reacciones": 5})
        self.assertEqual([f["id"] for f in filas], ["lim-01"])

    def test_solo_pide_instagram_cuando_el_post_salio_ahi(self):
        publicadas = {"aut-01": {"dia": "2026-11-01", "post_id": "1", "instagram": ""},
                      "lim-01": {"dia": "2026-11-02", "post_id": "2", "instagram": "ig9"}}
        pedidos = []
        medir.juntar(PAGINA, publicadas, pedir_fb=lambda p, i: {"reacciones": 1},
                     pedir_ig=lambda p, i: pedidos.append(i) or {"me_gusta": 3})
        self.assertEqual(pedidos, ["ig9"])


class TestLosScripts(unittest.TestCase):

    def test_los_tres_caminos_que_publican_son_estos_y_no_mas(self):
        # Son tres, y conviene tenerlos contados porque uno cambió la postura
        # del proyecto:
        #   frase_del_dia.py --publicar   lo corre una persona
        #   el botón Publicar del bot     vive en src/bot.py, con sus pruebas
        #   publicar_turno.py             SIN APROBACIÓN, a la hora que toca
        # El tercero entró para la prueba de ocho por día: ocho aprobaciones
        # diarias en el teléfono no son un sistema que alguien use. Cualquier
        # script nuevo que publique tiene que venir a cambiar esta lista y a
        # leer por qué. Se mira el AST y no el texto: varios docstrings nombran
        # la palabra para explicar que NO lo hacen.
        publican = sorted(p.name for p in (ROOT / "scripts").glob("*.py") if _llama_a(p, {"publicar"}))
        self.assertEqual(publican, ["frase_del_dia.py", "publicar_turno.py"])

    def test_frase_del_dia_sin_banderas_no_dibuja_ni_publica(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("fdd", ROOT / "scripts" / "frase_del_dia.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with mock.patch.object(diseno, "dibujar", side_effect=AssertionError("dibujó")), \
                mock.patch.object(facebook, "publicar", side_effect=AssertionError("publicó")), \
                mock.patch("builtins.print"):
            self.assertEqual(mod.main([]), 0)
            self.assertEqual(mod.main(["--id", "due-03"]), 0)


if __name__ == "__main__":
    unittest.main()
