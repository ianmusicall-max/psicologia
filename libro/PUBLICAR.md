# Publicar el libro

Los pasos para sacar *Lo que nadie te explicó del amor* en papel y en ebook,
y lo que falta antes de apretar el botón.

Todo lo que sigue sale de un solo comando:

```sh
pip install -r requirements-libro.txt    # la primera vez
python3 scripts/libro_pdf.py
```

Tarda unos cinco segundos y deja cinco archivos en `libro/salida/`. Esa carpeta
no está versionada —medio mega por versión, y se regenera sola— así que si no
está, corré el comando.

---

## 1. Lo que queda armado

| Archivo | Para qué | Dónde va |
|---|---|---|
| `...-impresion.pdf` | el interior, **todo en negro** | se sube a la imprenta |
| `...-cubierta.pdf` | contratapa + lomo + tapa, en una hoja | se sube a la imprenta |
| `...-pantalla.pdf` | el mismo interior **con el acento en rojo** | para leer y para mandar |
| `...-portada.pdf` | la tapa sola | para el ebook y para mirar |
| `...epub` | el ebook | se sube a la tienda |

Hoy: **29 capítulos, 49.110 palabras, 195 páginas.**

### Por qué son dos PDF del interior y no uno

En impresión por demanda el color **no se cobra por página**: alcanza con que
una sola tenga un píxel que no sea gris para que el libro entero se facture
como libro a color, y eso multiplica varias veces el costo de cada ejemplar.
Por eso el de imprenta va en negro puro.

**A la imprenta va `-impresion.pdf`. Nunca el de pantalla.** Son idénticos
salvo el tinte, así que confundirlos no se nota mirándolos: se nota en el
precio por ejemplar.

La **cubierta sí conserva el rojo**, y no es un olvido: la tapa se imprime a
color siempre y no cambia lo que cuesta el ejemplar.

---

## 2. Las medidas, y de dónde salen

| | |
|---|---|
| Tamaño del libro | 6 × 9 pulgadas (15,24 × 22,86 cm) |
| Páginas | 195 |
| Papel | crema, tinta negra |
| **Lomo** | **12,38 mm** (195 × 0,0025 pulgadas por hoja) |
| **Hoja de la cubierta** | **323,5 × 234,9 mm** (12,7375 × 9,25 pulgadas) |
| Sangrado | 3,18 mm (0,125 pulgadas) en los cuatro bordes |

**El lomo no es una decisión de diseño: es el grosor del papel por la cantidad
de páginas.** Por eso el script lo calcula contando las páginas del PDF de
imprenta ya armado, y por eso **cada vez que cambie el texto hay que volver a
generar la cubierta**. Un capítulo más y el lomo cambia; con el lomo viejo, el
título de la tapa termina sobre el pliegue.

Si alguna vez se cambia a papel blanco, es `--papel blanco`: la hoja es más
fina (0,002252 pulgadas) y el lomo baja a 11,15 mm.

### Comprobarlo antes de imprimir

Amazon genera una plantilla con las medidas exactas para tu cantidad de
páginas (buscá «Cover Template Generator» en KDP). Bajala, abrila junto a
nuestra cubierta y comprobá que los pliegues caigan en el mismo lugar. Son dos
minutos y es lo único que separa una cubierta buena de una tirada perdida.

Para mirarla con las líneas de corte dibujadas:

```sh
python3 scripts/libro_pdf.py --guias
```

**Ese archivo no se sube**: las guías se imprimirían. Después hay que volver a
correr el comando sin `--guias`.

---

## 3. Lo que falta antes de publicar

Tres cosas, en orden de urgencia:

1. **Página de créditos con el ISBN.** Hoy el libro tiene portadilla y una
   página con título, autor y «PRIMERA EDICIÓN», pero no lleva ISBN, año,
   copyright ni lugar de edición. Amazon regala un ISBN propio al publicar
   (queda atado a Amazon); si se quiere uno libre para venderlo también en
   otro lado, en Perú lo da la Biblioteca Nacional.
2. **Bibliografía.** El libro cita más de cien estudios por nombre y apellido
   —Mikulincer, Gottman, Borkovec, Gollwitzer— y no tiene dónde buscarlos. Las
   fuentes están en el banco de frases (`frases/`), así que se puede armar sin
   escribir nada nuevo.
3. **Las historias.** Los capítulos razonan y citan, pero casi no narran. Era
   el punto 2 de tu propio plan y es lo que más cambiaría la lectura. No
   bloquea publicar.

---

## 4. Tapa blanda, paso a paso

En `kdp.amazon.com`, **Create → Paperback**.

1. **Idioma español**, título, subtítulo y autor exactamente como figuran en
   la tapa. El subtítulo es *Ideas para quererte, elegir mejor y entenderte
   con quien quieres*.
2. **Descripción**: el texto de la contratapa sirve tal cual. Está en
   `scripts/libro_pdf.py`, en `CONTRATAPA`.
3. **Palabras clave y categorías**: siete palabras clave y dos categorías. Las
   que corresponden son autoayuda, relaciones y psicología popular.
4. **ISBN**: «Assign me a free KDP ISBN» si no conseguiste uno propio.
5. **Print options**: Black & white interior, **Cream paper**, 6 × 9 in,
   **Bleed: No bleed**, acabado mate o brillante (el mate le va mejor a una
   tapa blanca).
6. **Manuscript**: subí `...-impresion.pdf`.
7. **Cover → Upload a cover you already have**: subí `...-cubierta.pdf`.
8. **Launch Previewer.** Mirá el libro entero página por página, sobre todo:
   los capítulos abren siempre en página impar, el lomo, y que la cubierta no
   tenga ninguna advertencia de tamaño.
9. **Precio.** La calculadora de KDP te muestra el costo de impresión y la
   regalía antes de confirmar. Leelo ahí: cambia con el tiempo y con el país,
   así que cualquier número que te diga yo va a estar viejo.
10. **Publish.** Tarda entre un día y tres en aparecer.

### Dos trámites que no se saltean

- **La entrevista tributaria** (tax interview). Sin eso no te pagan. Perú no
  tiene tratado tributario con Estados Unidos, así que se aplica la retención
  por defecto sobre las ventas allá; el porcentaje te lo dice la propia
  entrevista antes de terminarla.
- **Los datos de cobro**: cuenta bancaria y dirección. Conviene tenerlos antes
  de empezar, porque el formulario no se guarda a medias.

### Pedí un ejemplar de prueba

Antes de promocionarlo, en el panel del libro: **Request a proof copy**. Se
paga el costo de impresión y el envío. Un flyer mal encuadrado se arregla en
un minuto; dos mil ejemplares con el lomo corrido, no.

---

## 5. El ebook

Es una publicación aparte en KDP (**Create → eBook**), con el mismo título y
autor. Ahí Amazon los enlaza solos.

- **Manuscrito**: `...epub`.
- **Tapa**: `...-portada.pdf`. Si la tienda pide imagen y no PDF:
  `pdftoppm -png -r 300 ...-portada.pdf tapa` y subí el PNG.
- En el ebook **el color no cuesta nada**, así que el acento rojo se queda.
- El EPUB no tiene páginas fijas: el lector elige el cuerpo, y por eso no
  tiene número de página ni lomo. Es correcto que se vea distinto del PDF.

El mismo EPUB sirve para Google Play Libros, Apple Books y Kobo sin tocar
nada.

---

## 6. Lo que no hay que hacer

- Subir `-pantalla.pdf` a la imprenta. Imprime igual y cobra el libro entero a
  color.
- Subir la cubierta generada con `--guias`.
- Cambiar un capítulo y no volver a generar la cubierta. El lomo cambia con la
  cantidad de páginas.
- Editar el PDF a mano. El texto sale de `libro/capitulos/*.md` y cualquier
  arreglo hecho sobre el PDF se pierde en la próxima corrida.

---

## 7. Si algo sale raro

| Síntoma | Dónde mirar |
|---|---|
| KDP dice que la cubierta no mide bien | cambió la cantidad de páginas: volvé a correr el script |
| El previsualizador marca fuentes sin incrustar | las fuentes no están en la máquina y salió en Times; instalá `fonts-crosextra-caladea` y `fonts-crosextra-carlito` |
| Un título empieza a la mitad de la hoja | lo cuida `TestComoCaeElTextoEnLaPagina` en las pruebas |
| El texto de la contratapa no entra | el script se niega a armarla y dice cuántos milímetros sobran: hay que acortar `CONTRATAPA` |

Las pruebas del libro y de la cubierta:

```sh
python3 -m unittest tests.test_core.TestLaCubiertaQueVaALaImprenta \
                    tests.test_core.TestElLibroParaImprimirYParaPantalla \
                    tests.test_core.TestComoCaeElTextoEnLaPagina
```
