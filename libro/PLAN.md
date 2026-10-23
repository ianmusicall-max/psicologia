# Lo que nadie te explicó del amor

### Ideas para quererte, elegir mejor y entenderte con quien querés

El título lo eligió el usuario el 2026-10-23 sobre tres opciones. Cubre las dos
mitades del libro, quererte y vincularte, que es lo que la página promete, y
promete algo concreto, que es lo que un título de tapa tiene que hacer. Las
otras dos eran «Nadie te completa», más filoso y con el riesgo de sonar a
reproche justo a quien busca pareja, y «Hablarte bien», el más propio y el que
menos dice de qué trata.

Vive en `libro.TITULO`, no acá: de ahí lo toma el borrador cada vez que se
regenera.

## De qué va

Un libro sobre vínculos: cómo se quiere, por qué cuesta, qué sostiene a una
pareja y qué hacer cuando se termina. Divulgación con respaldo, escrita para
alguien que no estudió psicología y que no quiere que le hablen como a un
paciente.

Es el mismo tema que la página, y a propósito: los lectores del libro van a
salir de ahí, y lo que la página mide día a día dice qué capítulo le importa a
la gente.

## Los capítulos escritos

`libro/borrador.md` se regenera entero y no se edita a mano. Los capítulos de
verdad viven aparte, en `libro/capitulos/`, uno por archivo con el número del
capítulo adelante. El borrador es la materia prima ordenada -tesis, frases,
reflexiones y fuentes a la vista-; el capítulo es el texto que las une.

Cada capítulo usa TODAS las frases de su tema, en el orden que convenga, y las
cita como epígrafe antes de desarrollarlas. Eso no es decoración: es lo que
mantiene el libro y la página diciendo lo mismo, y lo que permite que un
lector que llegó por un post encuentre esa frase adentro.

Unas 1.500 palabras por capítulo. Veintinueve capítulos son unas 43.000
palabras de texto nuevo, que llevan el manuscrito de 27.000 a cerca de 70.000.

Escritos hasta ahora: del 1 al 8.

Una prueba (`TestLosCapitulosEscritos`) exige que cada capítulo escrito
cite TODAS las frases de su tema, que tenga el largo de un capítulo y que
su título sea el del tema. Es una promesa que se rompe sin que nada falle:
el capítulo se escribe una vez y las frases se siguen tocando.

## Cómo sale del banco

`scripts/armar_libro.py` escribe `borrador.md` entero desde `frases/`: cada
tema es un capítulo, su tesis abre, cada frase entra como epígrafe seguida de
su reflexión, y el principio y la fuente quedan a la vista para escribir
encima. Hoy son 29 capítulos, 243 frases y unas 27.200 palabras: el esqueleto,
no el libro.

**El borrador se regenera.** Lo que se escriba a mano va en otros archivos de
esta carpeta, nunca dentro de `borrador.md`, porque la próxima corrida lo pisa.

## El orden

Los capítulos están numerados por el orden en que se escribieron, no por el
orden del libro. Para el libro, el arco va de adentro hacia afuera y termina
donde el lector suele llegar:

1. **Tú** · amor propio (3), emociones (1), pensamientos (8), ansiedad (2)
2. **Cómo aprendiste a querer** · apego (5)
3. **Elegir** · elegir pareja (14)
4. **Sostener** · comunicación (11), límites (4), reconexión (12)
5. **Perder** · ruptura (13), duelo (7)
6. **Después** · hábitos (6), descanso (9), sentido (10)

Los capítulos del eje `nucleo` son el libro propiamente dicho. Los de `apoyo`
son la primera y la última parte: lo que hay que entender de uno mismo antes
de hablar de vínculos, y lo que queda después.

## Qué falta para que sea un libro

Un libro no es una colección de frases ordenadas, y conviene tenerlo escrito
antes de empezar a escribir:

1. **Cada capítulo necesita un hilo**, no ocho frases en fila. La tesis que ya
   está en cada archivo es ese hilo: el capítulo lo desarrolla y las frases son
   las paradas del camino.
2. **Faltan las historias.** Una frase convence en Facebook porque el lector
   pone su propio caso. En un libro hay que poner el caso. Dos o tres por
   capítulo, cambiados lo suficiente.
3. **Faltan los estudios contados.** La fuente hoy es una línea entre
   paréntesis. En el libro, los dos o tres estudios centrales de cada capítulo
   se cuentan: quién, cuántos, qué hicieron, qué salió. Eso es lo que lo separa
   de un libro de autoayuda.
4. **Falta decidir el largo.** A ocho frases por capítulo y unas 2.500 palabras
   cada uno son unas 35.000: un libro corto. Para 60.000 hacen falta unas
   quince frases por capítulo.

## Lo que ya está resuelto

- **La bibliografía se arma sola**, porque cada frase trajo su fuente desde el
  día uno. Es el trabajo que más duele dejar para el final.
- **La voz es la misma** en los veintinueve capítulos, porque las 243 frases
  pasan por la misma línea editorial.
- **No hay que pedirle permiso a nadie**: no se cita a autores famosos, se
  escribe. Por eso el libro puede publicarse sin derechos de terceros.
- **El capítulo más difícil ya está decidido.** La ruptura no promete que el
  otro vuelva, que es lo que vende el género, y dice en su propia voz por qué
  no. Eso define el libro entero: es el que no te miente.

## El camino más corto

Publicar primero. Cada frase que sale en la página se mide sola: lo que se
comparte y lo que se comenta dice qué capítulo le importa a la gente. A los
cuatro meses, con el banco entero publicado una vez, hay datos reales para
decidir qué capítulo abre el libro y cuál se recorta.
