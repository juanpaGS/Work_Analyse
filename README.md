# Work_Analyse

Asistente personal de búsqueda de prácticas y empleo junior.

## Qué hay

| Ruta | Qué hace |
|---|---|
| `perfil.json` | Tu perfil: habilidades, áreas, niveles y ubicaciones con sus pesos. Edítalo para cambiar qué ofertas se seleccionan. |
| `agente/buscar.py` | Descarga ofertas de fuentes públicas (Remotive, Jobicy, Arbeitnow, Himalayas y tablones Greenhouse de empresas), las puntúa contra el perfil y escribe `docs/data/ofertas.json`. Solo librería estándar de Python. |
| `docs/` | App web instalable (PWA) que muestra las ofertas, con filtros y seguimiento (guardada / solicitada / descartada, guardado en el propio dispositivo). |
| `.github/workflows/buscar.yml` | Ejecuta el buscador cada día y guarda los resultados. Solo se activa cuando está en la rama `main`. |
| `cv/` | Ignorado por git (contiene datos personales). |

## La app

Interfaz instalable en el móvil, con todo guardado en tu dispositivo:

- **Filtros**: dónde (León / remoto), tipo (prácticas / junior), área, encaje mínimo, sin avisos, con remuneración y orden.
- **Ofertas que casi encajan**: se pueden mostrar, con el motivo por el que no cumplen el filtro estricto (presencial fuera de León, piden experiencia, sin nivel junior, otro idioma).
- **Mi perfil**: tecnologías que dominas, editables. Puedes pegar el texto de tu CV y se detectan en tu navegador, sin enviarlo a ningún sitio.
- **Qué te falta**: en cada oferta, qué tecnologías ya dominas y cuáles no, y un resumen de las más pedidas que aún no tienes.

## Prueba rápida en tu PC

Necesitas Python 3.10 o superior (en Windows: python.org, marcando "Add to PATH"; en WSL/Linux ya suele venir) y Git.

```bash
git clone https://github.com/juanpaGS/Work_Analyse.git
cd Work_Analyse
python3 agente/buscar.py --fuentes          # qué fuentes hay y cuáles están activas
python3 agente/buscar.py --sin adzuna       # búsqueda solo con fuentes sin clave
python3 agente/buscar.py                    # búsqueda con todas las fuentes activas
python3 -m http.server -d docs 8000         # abre http://localhost:8000 en el navegador
```

En Windows sin WSL usa `python` o `py` en lugar de `python3`. La búsqueda tarda 1-2 minutos y escribe `docs/data/ofertas.json`.

Opciones: `--sin FUENTE` (repetible), `--solo FUENTE`, `--salida ARCHIVO` (no toca los datos de la app).

### Activar Adzuna (opcional)

1. Copia `.env.ejemplo` como `.env` y rellena `ADZUNA_APP_ID` y `ADZUNA_APP_KEY`. El archivo `.env` está en `.gitignore` y nunca se sube.
2. Comprueba con `python3 agente/buscar.py --fuentes`: `adzuna` debe salir como `activa`.

## Fuentes e independencia

Ninguna fuente es imprescindible: cada una es opcional y, si falla o no hay clave, el buscador sigue con las demás.

- **Sin clave** (siempre activas): Remotive, Jobicy, Arbeitnow, Himalayas y tablones de empresas en Greenhouse y Lever. Para añadir empresas, edita `tablones_greenhouse` / `tablones_lever` en `perfil.json`.
- **Con clave** (opcional, recomendada): Adzuna, con los secretos `ADZUNA_APP_ID` y `ADZUNA_APP_KEY` del repositorio. Sin ellos se omite. Se puede apagar a mano con `"fuentes_desactivadas": ["adzuna"]`.

## Ubicación

Solo León o remoto. Las ofertas presenciales en otras ciudades se descartan; para verlas, pon `"acepta_otras_ciudades": true` en `perfil.json`.

## Límites actuales

- No se consultan LinkedIn, InfoJobs, Indeed ni Tecnoempleo: sus condiciones o su `robots.txt` no permiten el acceso automático.
- La puntuación y la revisión de requisitos (años de experiencia, titulación, idiomas, certificaciones) son por palabras clave, no por IA: pueden fallar, así que la app muestra los avisos para que los compruebes.
- Solo pasan ofertas de prácticas o junior, o las que dicen expresamente que admiten estudiantes.
- Aún no hay notificaciones push.
