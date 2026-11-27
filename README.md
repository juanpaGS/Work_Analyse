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

## Uso local

```bash
python3 agente/buscar.py            # actualiza docs/data/ofertas.json
python3 -m http.server -d docs 8000 # abre http://localhost:8000
```

## Fuentes e independencia

Ninguna fuente es imprescindible: cada una es opcional y, si falla o no hay clave, el buscador sigue con las demás.

- **Sin clave** (siempre activas): Remotive, Jobicy, Arbeitnow, Himalayas y tablones de empresas en Greenhouse y Lever. Para añadir empresas, edita `tablones_greenhouse` / `tablones_lever` en `perfil.json`.
- **Con clave** (opcional): Adzuna, con los secretos `ADZUNA_APP_ID` y `ADZUNA_APP_KEY` del repositorio. Sin ellos se omite. Se puede apagar a mano con `"fuentes_desactivadas": ["adzuna"]`.

## Ubicación

Solo León o remoto. Las ofertas presenciales en otras ciudades se descartan; para verlas, pon `"acepta_otras_ciudades": true` en `perfil.json`.

## Límites actuales

- No se consultan LinkedIn, InfoJobs, Indeed ni Tecnoempleo: sus condiciones o su `robots.txt` no permiten el acceso automático.
- La puntuación y la revisión de requisitos (años de experiencia, titulación, idiomas, certificaciones) son por palabras clave, no por IA: pueden fallar, así que la app muestra los avisos para que los compruebes.
- Solo pasan ofertas de prácticas o junior, o las que dicen expresamente que admiten estudiantes.
- Aún no hay notificaciones push.
