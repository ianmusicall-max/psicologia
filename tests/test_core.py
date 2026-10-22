"""Las pruebas del banco, la línea editorial, la rotación, el flyer, el libro y la publicación.

    python3 -m unittest tests.test_core
"""
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

from src import config, diseno, facebook, frases, libro

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
    base = dict(tema="prueba", capitulo=99, titulo="Un capítulo de prueba",
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

    def test_diez_capitulos_sin_repetir(self):
        self.assertEqual([t.capitulo for t in TEMAS], list(range(1, 11)))

    def test_pasa_entero_la_linea_editorial(self):
        self.assertEqual(frases.revisar(TEMAS), [])

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

    def test_el_duelo_es_el_unico_tema_sensible(self):
        self.assertEqual([t.tema for t in TEMAS if t.sensible], ["duelo"])

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

    def test_rota_por_tema(self):
        orden = self._publicar_todo(TEMAS)
        primeros = [f.tema for f in orden[:len(TEMAS)]]
        self.assertEqual(len(set(primeros)), len(TEMAS))
        self.assertEqual(primeros, [t.tema for t in TEMAS])

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
        ya = {"emo-01": {"dia": "2026-11-01", "post_id": "p", "pagina": "x"}}
        self.assertEqual(frases.siguiente(TEMAS, ya).tema, "ansiedad")

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
            self.assertEqual(hs[:2], ["#psicología", "#saludmental"])

    def test_un_hashtag_del_tema_no_repite_uno_fijo(self):
        t = tema(hashtags=["psicologia", "dos", "tres"])
        hs = frases.hashtags(t, PAGINA)
        self.assertEqual(len(hs), 4)
        self.assertEqual(hs.count("#psicología") + hs.count("#psicologia"), 1)

    def test_el_duelo_lleva_el_pie_y_los_demas_no(self):
        for t in TEMAS:
            c = frases.caption(t.frases[0], t, PAGINA)
            self.assertEqual(PAGINA.pie_sensible in c, t.tema == "duelo", t.tema)

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


class TestLosScripts(unittest.TestCase):

    def test_solo_frase_del_dia_publica(self):
        # Cualquier otro script que llame a `publicar` es un post saliendo sin
        # que nadie lo haya pedido. Se mira el AST y no el texto: los docstrings
        # nombran la palabra para explicar que NO lo hacen.
        publican = sorted(p.name for p in (ROOT / "scripts").glob("*.py") if _llama_a(p, {"publicar"}))
        self.assertEqual(publican, ["frase_del_dia.py"])

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
