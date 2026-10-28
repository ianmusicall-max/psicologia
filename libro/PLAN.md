# Lo que nadie te explicó del amor

### Ideas para quererte, elegir mejor y entenderte con quien quieres

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

Escritos: **los veintinueve**, terminados el 2026-10-28. Son 49.083 palabras
de texto nuevo, entre 1.406 y 1.945 por capítulo.

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

1. **Tú** · amor propio (3), emociones (1), pensamientos (8), ansiedad (2),
   culpa y vergüenza (18), miedo (29)
2. **Cómo aprendiste a querer** · apego (5), familia (16)
3. **Elegir** · expectativas (27), elegir pareja (14)
4. **Sostener** · comunicación (11), discutir (22), límites (4), convivencia
   (26), dinero (25), intimidad (19), celos (15), confianza (23),
   reconexión (12)
5. **Perder** · ruptura (13), duelo (7), perdón (20)
6. **Después** · hábitos (6), cambio (28), descanso (9), soledad (21),
   amistad (17), comparación y redes (24), sentido (10)

Los catorce capítulos nuevos se ubicaron ahí por tema y no por medición: el
orden definitivo lo decide el usuario, y el camino más corto de abajo dice con
qué datos conviene decidirlo. Lo que el arco sí respeta es que miedo cierre la
primera parte y sentido la última, y que los tres de **Perder** queden juntos.

Los capítulos del eje `nucleo` son el libro propiamente dicho. Los de `apoyo`
son la primera y la última parte: lo que hay que entender de uno mismo antes
de hablar de vínculos, y lo que queda después.

## Lo que se resolvió al escribirlos

De las cuatro cosas que esta sección listaba como pendientes antes de empezar,
tres están hechas en los veintinueve capítulos:

1. **El hilo.** Cada capítulo desarrolla la tesis de su archivo y las frases son
   las paradas del camino, cada una como epígrafe de su apartado.
2. **Los estudios contados.** La fuente dejó de ser una línea entre paréntesis:
   se cuenta quién lo hizo, con cuánta gente y qué salió. Es lo que separa esto
   de un libro de autoayuda, y es lo que más trabajo llevó.
3. **El largo.** Quedó decidido por los hechos: 49.083 palabras, unas 1.700 por
   capítulo. No son las 60.000 que esta sección imaginaba, y la cuenta de cómo
   llegar sigue siendo la misma: más frases por capítulo, no más vueltas sobre
   las mismas.

## Qué falta

1. **Las historias.** Es el punto 2 de la lista vieja y es el único que no se
   hizo. Una frase convence en Facebook porque el lector pone su propio caso;
   en un libro hay que poner el caso. Dos o tres por capítulo, cambiados lo
   suficiente. Hoy los capítulos razonan y citan, pero casi no narran.
2. **Una lectura seguida.** Se escribieron por tema y en tandas, así que hay
   repeticiones entre capítulos vecinos (los componentes de la disculpa, el
   sesgo de memoria de Ross y Sicoly, las intenciones de implementación
   aparecen dos veces cada uno). Algunas sirven como refuerzo y otras sobran:
   eso se decide leyendo el libro de corrido, no capítulo por capítulo.
3. **La introducción y el cierre.** El capítulo 29 termina con un párrafo que
   cierra el libro, pero no hay una entrada que explique de qué va ni cómo
   leerlo.
4. **La bibliografía.** Se arma sola desde las fuentes de las frases, y todavía
   no se armó. Es el trabajo que más duele dejar para el final y el único que
   no lo duele acá, porque cada frase trajo su fuente desde el día uno.

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
