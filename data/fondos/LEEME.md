# Los videos de fondo del reel

**Los archivos de video van en esta misma carpeta** (`data/fondos/`), sueltos,
sin subcarpetas.

    data/fondos/
      LEEME.md      <- este archivo
      clip-01.mp4   <- tus videos, aca
      clip-02.mp4
      ...

## Lo importante: no alcanza con tenerlos en la Mac

El reel **no se arma en tu computadora, se arma en los servidores de GitHub**,
y esa maquina es nueva cada vez: solo tiene lo que esta subido al repositorio.
Un video que esta en tu Mac y no se subio, para el reel no existe.

Asi que: copiarlos a esta carpeta, y despues subirlos.

    git add data/fondos
    git commit -m "Clips de fondo para los reels"
    git push

Esta carpeta es la unica de `data/` que se versiona a proposito (ver el
`.gitignore`). Son unos megas cada uno, no cambian nunca, y es lo unico que
hace que el reel salga sobre paisajes y no sobre el papel de la marca.

## Que clips sirven

- **Verticales.** El reel es 1080x1920. Uno horizontal entra igual pero se
  recorta por los costados y se pierde medio encuadre.
- **De 900 px de ancho para arriba.** Mas chico se ve pixelado al agrandarlo.
- **mp4, mov, m4v, webm o mkv.**
- **Cinco a quince segundos** cada uno. El reel va cortando entre clips cada
  pocos segundos; uno largo se usa por tramos igual.
- **Sin texto, sin logos y sin gente hablando a camara**: encima va el texto
  del reel y compiten.
- **Movimiento lento.** Una rama con viento, agua, nubes. Un dron sobre una
  cascada le gana la atencion a la frase, que es justo al reves de lo que se
  busca.

Con **ocho o diez** ya no se repiten de un reel a otro.

El video se oscurece y se dessatura al armarlo, asi que uno muy claro o muy
saturado queda mejor de lo que parece al mirarlo suelto.

## La otra forma: que se bajen solos

Si no queres juntarlos a mano, `scripts/fondos.py` los baja de Pexels. Necesita
una clave gratuita (https://www.pexels.com/api/) cargada como secreto del
repositorio con el nombre `PEXELS_API_KEY`, y a partir de ahi el flujo del reel
los baja solo la primera vez y los reusa.

Las dos formas conviven: lo que haya en esta carpeta se usa, y lo que se baje
se suma.
