#!/usr/bin/env python3
"""Buscador de ofertas: descarga de fuentes públicas, puntúa contra perfil.json
y escribe docs/data/ofertas.json (lo que lee la app web).

Solo usa la librería estándar. Uso:  python3 agente/buscar.py
"""
from __future__ import annotations

import hashlib
import os
import urllib.parse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PERFIL = json.loads((RAIZ / "perfil.json").read_text(encoding="utf-8"))
SALIDA = RAIZ / "docs" / "data" / "ofertas.json"
UA = "Work_Analyse/1.0 (buscador personal de empleo)"


# ---------------------------------------------------------------- utilidades
def descargar(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def limpiar(texto) -> str:
    texto = html.unescape(re.sub(r"<[^>]+>", " ", str(texto or "")))
    return re.sub(r"\s+", " ", texto).strip()


def fecha_iso(valor) -> str:
    """Normaliza epoch o ISO a AAAA-MM-DD ('' si no se puede)."""
    if not valor:
        return ""
    try:
        if str(valor).isdigit():
            return datetime.fromtimestamp(int(valor), timezone.utc).date().isoformat()
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).date().isoformat()
    except (ValueError, OSError, OverflowError):
        return str(valor)[:10]


def contiene(termino: str, texto: str) -> bool:
    """Coincidencia por palabra completa ('intern' no casa con 'internal')."""
    return re.search(r"(?<![\w])" + re.escape(termino) + r"(?![\w])", texto) is not None


def oferta(fuente, titulo, empresa, ubicacion, url, fecha, descripcion, etiquetas=(), remoto=False):
    return {
        "fuente": fuente, "titulo": limpiar(titulo), "empresa": limpiar(empresa),
        "ubicacion": limpiar(ubicacion), "url": url, "fecha": fecha_iso(fecha),
        "descripcion": limpiar(descripcion), "etiquetas": [str(e) for e in etiquetas or []],
        "remoto": bool(remoto),
    }


# ------------------------------------------------------------------- fuentes
def fuente_remotive():
    for categoria in ("software-dev", "data", "devops"):
        datos = descargar(f"https://remotive.com/api/remote-jobs?category={categoria}")
        for j in datos.get("jobs", []):
            yield oferta("Remotive", j["title"], j["company_name"], j.get("candidate_required_location"),
                         j["url"], j.get("publication_date"), j.get("description"), j.get("tags"), True)
        time.sleep(1)


def fuente_jobicy():
    for geo in ("spain", "emea", "europe"):
        datos = descargar(f"https://jobicy.com/api/v2/remote-jobs?count=50&geo={geo}")
        for j in datos.get("jobs", []):
            yield oferta("Jobicy", j["jobTitle"], j["companyName"], j.get("jobGeo"), j["url"],
                         j.get("pubDate"), j.get("jobDescription") or j.get("jobExcerpt"),
                         [j.get("jobLevel", "")], True)
        time.sleep(1)


def fuente_arbeitnow():
    datos = descargar("https://www.arbeitnow.com/api/job-board-api")
    for j in datos.get("data", []):
        if not j.get("remote"):  # presenciales: casi todo Alemania
            continue
        yield oferta("Arbeitnow", j["title"], j["company_name"], f"{j.get('location', '')} (remote)",
                     j["url"], j.get("created_at"), j.get("description"), j.get("tags"), True)


def fuente_himalayas():
    datos = descargar("https://himalayas.app/jobs/api?limit=20")
    for j in datos.get("jobs", []):
        yield oferta("Himalayas", j["title"], j["companyName"],
                     ", ".join(j.get("locationRestrictions") or ["Worldwide"]),
                     j.get("applicationLink") or j.get("guid"), j.get("pubDate"),
                     j.get("description") or j.get("excerpt"), j.get("categories"), True)


def fuente_greenhouse():
    for tablon in PERFIL["tablones_greenhouse"]:
        try:
            datos = descargar(f"https://boards-api.greenhouse.io/v1/boards/{tablon}/jobs")
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"  ! greenhouse/{tablon}: {e}", file=sys.stderr)
            continue
        for j in datos.get("jobs", []):
            o = oferta("Greenhouse", j["title"], j.get("company_name") or tablon.capitalize(),
                       (j.get("location") or {}).get("name"), j["absolute_url"],
                       j.get("first_published") or j.get("updated_at"), "")
            # El listado no trae descripción: se pide solo para las que pasan título y ubicación
            if puntuar(o, previo=True):
                try:
                    detalle = descargar(f"https://boards-api.greenhouse.io/v1/boards/{tablon}/jobs/{j['id']}")
                    o["descripcion"] = limpiar(html.unescape(detalle.get("content") or ""))
                except (urllib.error.URLError, TimeoutError, ValueError):
                    pass
                time.sleep(0.2)
            yield o
        time.sleep(0.5)


def fuente_adzuna():
    """Ofertas de España (API gratuita de Adzuna). Necesita ADZUNA_APP_ID y ADZUNA_APP_KEY."""
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        print("  adzuna: sin claves (ADZUNA_APP_ID / ADZUNA_APP_KEY), se omite")
        return
    consultas = [("prácticas informática", ""), ("prácticas programador", ""), ("becario informática", ""),
                 ("prácticas inteligencia artificial", ""), ("junior desarrollador", ""),
                 ("junior python", ""), ("prácticas", "León"), ("junior informática", "León")]
    for que, donde in consultas:
        params = {"app_id": app_id, "app_key": app_key, "results_per_page": 50, "what": que,
                  "sort_by": "date", "max_days_old": 30, "content-type": "application/json"}
        if donde:
            params.update(where=donde, distance=60)
        datos = descargar("https://api.adzuna.com/v1/api/jobs/es/search/1?" + urllib.parse.urlencode(params))
        for j in datos.get("results", []):
            lugar = (j.get("location") or {}).get("display_name") or ""
            # El enlace de Adzuna lleva tu app_id en utm_source: se quita para no publicarlo
            partes = urllib.parse.urlsplit(j["redirect_url"])
            consulta = [(k, v) for k, v in urllib.parse.parse_qsl(partes.query) if k != "utm_source"]
            enlace = urllib.parse.urlunsplit(partes._replace(query=urllib.parse.urlencode(consulta)))
            yield oferta("Adzuna", j["title"], (j.get("company") or {}).get("display_name") or "",
                         f"{lugar}, España", enlace, j.get("created"),
                         j.get("description"), [], False)
        time.sleep(1)


def fuente_lever():
    for emp in PERFIL.get("tablones_lever", []):
        try:
            datos = descargar(f"https://api.lever.co/v0/postings/{emp}?mode=json")
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"  ! lever/{emp}: {e}", file=sys.stderr)
            continue
        for j in datos:
            remoto = j.get("workplaceType") == "remote"
            lugar = (j.get("categories") or {}).get("location") or ""
            yield oferta("Lever", j["text"], emp.capitalize(), lugar + (" (remote)" if remoto else ""),
                         j["hostedUrl"], str(int(j.get("createdAt", 0)) // 1000) if j.get("createdAt") else "",
                         j.get("descriptionPlain") or j.get("description"), [], remoto)
        time.sleep(0.5)


FUENTES = [fuente_adzuna, fuente_lever, fuente_remotive, fuente_jobicy, fuente_arbeitnow, fuente_himalayas, fuente_greenhouse]


# ----------------------------------------------------------------- requisitos
IDIOMAS = (r"german|deutsch|french|fran[cç]ais|franc[eé]s|alem[aá]n|dutch|italian|italiano|portuguese|"
           r"swedish|danish|norwegian|finnish|nordic|polish|japanese|hebrew|arabic|mandarin|korean|turkish")
RE_IDIOMA = re.compile(
    rf"(?:fluen\w*|native|proficien\w*|business[- ]level|c1|c2|nativo|fluido)[^.;]{{0,40}}\b({IDIOMAS})\b"
    rf"|\b({IDIOMAS})\b[^.;]{{0,25}}(?:speaker|speaking|fluen\w*|native|proficien\w*|required|is a must|c1|c2|nativo|fluido|imprescindible)")
RE_ANIOS = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:(?:-|–|to|a)\s*\d{1,2}\s*)?\+?\s*(?:years?|yrs?|años?)[^.;]{0,60}?(?:experience|experiencia)"
    r"|(?:experience|experiencia)[^.;]{0,30}?(\d{1,2})\s*\+?\s*(?:years?|yrs?|años?)")
RE_ESTUDIANTE = re.compile(
    r"currently (?:enrolled|pursuing|studying)|pursuing an? (?:bachelor|degree|master)|enrolled in an? |"
    r"estudiantes?\b|convenio|final[- ]year students?|penultimate|último curso|ultimo curso|"
    r"no (?:prior |previous )?(?:work )?experience (?:is )?(?:needed|required|necessary)|"
    r"sin experiencia|no se requiere experiencia")
RE_TITULO = re.compile(
    r"bachelor|\bb\.?sc?\b|university degree|degree in|college degree|grado en|graduad[oa] en|titulaci[oó]n|"
    r"titulad[oa]|licenciatura|ingenier[oa] (?:t[eé]cnic|superior|inform)")
RE_POSGRADO = re.compile(r"\bph\.?d\b|doctorate|doctorado|master'?s degree|\bm\.?sc\b|máster|master en")
RE_CERT = re.compile(r"certifi(?:ed|cation|cations|cado|cados|caci[oó]n|caciones)|\bcissp\b|\bccna\b|\bitil\b")
RE_YA_TITULADO = re.compile(r"recent graduates?|graduated|have completed (?:a|your)|reci[eé]n (?:titulad|graduad|licenciad)")
RE_REMOTO = re.compile(r"remot|teletrabaj|work from home|trabajo desde casa|home[- ]?office|fully remote")
RE_HIBRIDO = re.compile(r"h[ií]brid|hybrid|presencial|on-?site|in[- ]office")
RE_TODO_REMOTO = re.compile(r"100 ?% ?(?:remot|teletrabaj)|fully remote|totalmente remot|full[- ]remote")
RE_PAGADA = re.compile(r"remunerad[ao]s?|bolsa de ayuda|ayuda al estudio|paid intern|stipend|retribu[ií]d[ao]|retribuci[oó]n")
RE_NO_PAGADA = re.compile(r"no remunerad|unpaid|sin remuneraci|non[- ]paid|no retribu")
RE_ALEMAN = re.compile(r"\b(?:und|der|die|das|mit|wir|für|sie|bei|oder)\b")


def requisitos(titulo: str, cuerpo: str, es_practicas: bool, es_adzuna: bool = False):
    """Compara lo que pide la oferta con tu situación (estudiante de 4.º, sin experiencia
    laboral ni certificaciones, español e inglés). Devuelve (bloqueo, avisos, a_favor)."""
    avisos, a_favor = [], []
    texto = titulo + " . " + cuerpo
    if "(m/w/d)" in titulo or len(RE_ALEMAN.findall(cuerpo)) > 12:
        return "oferta en alemán", avisos, a_favor
    m = RE_IDIOMA.search(texto)
    if m:
        return f"exige otro idioma ({m.group(1) or m.group(2)})", avisos, a_favor
    anios = [int(a or b) for a, b in RE_ANIOS.findall(cuerpo)]
    anios = [a for a in anios if a <= 15]
    if anios and min(anios) >= 2:
        return f"pide {min(anios)}+ años de experiencia", avisos, a_favor
    if anios:
        avisos.append("pide 1 año de experiencia")
    if es_adzuna:
        avisos.append("descripción parcial: lee los requisitos completos en la oferta")
    if not cuerpo.strip():
        avisos.append("sin descripción: revisa los requisitos en la oferta")
        return None, avisos, a_favor
    estudiante = RE_ESTUDIANTE.search(cuerpo) is not None
    if estudiante:
        a_favor.append("admite estudiantes o perfiles sin experiencia")
    if RE_NO_PAGADA.search(texto):
        avisos.append("prácticas posiblemente NO remuneradas")
    elif RE_PAGADA.search(texto):
        a_favor.append("indica remuneración")
    if RE_POSGRADO.search(texto):
        avisos.append("menciona máster o doctorado")
    if RE_YA_TITULADO.search(cuerpo) and not es_practicas:
        avisos.append("dirigida a recién titulados (tú terminas en 2027)")
    elif RE_TITULO.search(cuerpo) and not estudiante and not es_practicas:
        avisos.append("pide titulación terminada (tú terminas en 2027)")
    if RE_CERT.search(cuerpo):
        avisos.append("menciona certificaciones")
    return None, avisos, a_favor


# ---------------------------------------------------------------- puntuación
def puntuar(o: dict, previo: bool = False) -> dict | None:
    """Devuelve la oferta con puntuación y motivos, o None si se descarta."""
    titulo = o["titulo"].lower()
    cuerpo = (o["descripcion"] + " " + " ".join(o["etiquetas"])).lower()
    lugar = o["ubicacion"].lower()
    puntos, motivos, sin_region = 0, [], False

    # Nivel: lo decide el título
    niv = PERFIL["nivel"]
    if any(contiene(t, titulo) for t in niv["excluir"]):
        return None
    if any(contiene(t, titulo) for t in niv["practicas"]):
        nivel, puntos = "Prácticas", puntos + 40
        motivos.append("prácticas")
    elif any(contiene(t, titulo) for t in niv["junior"]):
        nivel, puntos = "Junior", puntos + 28
        motivos.append("junior")
    elif any(contiene(t, cuerpo[:1500]) for t in niv["practicas"] + niv["junior"]):
        nivel, puntos = "Posible junior", puntos + 10
    else:
        nivel = "Sin nivel"

    # Ubicación
    ub = PERFIL["ubicacion"]
    en_espana = any(contiene(t, lugar) for t in ub["espana"] + ub["local"])
    if any(contiene(t, lugar) for t in ub["local"]):
        puntos += 40
        motivos.append("León")
    elif en_espana:
        zona = lugar + " " + titulo + " " + cuerpo[:1500]
        es_remoto = (RE_REMOTO.search(zona) or o["remoto"]) and (
            not RE_HIBRIDO.search(lugar + " " + titulo + " " + cuerpo[:600]) or RE_TODO_REMOTO.search(zona))
        if es_remoto:
            puntos += 30
            motivos.append("remoto desde España")
        elif PERFIL.get("acepta_otras_ciudades", False):
            puntos += 8
            motivos.append("presencial fuera de León")
        else:
            DESCARTES["presencial fuera de León"] = DESCARTES.get("presencial fuera de León", 0) + 1
            return None
    elif any(contiene(t, lugar) for t in ub["remoto_ok"]) or (o["remoto"] and not lugar):
        puntos += 10
        motivos.append("remoto Europa/global")
    elif lugar.strip() in ("remote", "remoto"):
        puntos += 4
        motivos.append("remoto (región sin indicar)")
        sin_region = True
    else:
        return None  # restringida a otro país

    # Área: la decide el título (el cuerpo menciona "AI" en casi cualquier oferta)
    if any(contiene(t, titulo) for t in PERFIL["excluir_titulo"]):
        return None
    area = next((nombre for nombre, terminos in PERFIL["areas"].items()
                 if any(contiene(t, titulo) for t in terminos)), None)
    if not area and nivel == "Prácticas" and any(contiene(t, titulo + " " + cuerpo[:600]) for t in PERFIL["areas_practicas_amplias"]):
        area = "TI general"  # unas prácticas valen aunque no sean de tu área principal
    if not area:
        return None  # no es un puesto técnico de tus áreas
    puntos += PERFIL["peso_area"].get(area, 5)
    if previo:  # solo se comprobaba título y ubicación
        return o

    # Requisitos que no cumples: descartan o restan
    bloqueo, avisos, a_favor = requisitos(titulo, o["descripcion"].lower(), nivel == "Prácticas", o["fuente"] == "Adzuna")
    if bloqueo:
        clave = re.sub(r" \(.*| \d+\+", "", bloqueo)
        DESCARTES[clave] = DESCARTES.get(clave, 0) + 1
        return None
    # Sin "prácticas" o "junior" en el título, solo vale si dice expresamente que admite estudiantes
    if nivel not in ("Prácticas", "Junior") and "admite estudiantes o perfiles sin experiencia" not in a_favor:
        DESCARTES["no es junior ni prácticas"] = DESCARTES.get("no es junior ni prácticas", 0) + 1
        return None
    if sin_region:
        avisos.append("remoto sin región: comprueba que admite candidatos desde España")
    puntos += 10 * len(a_favor) - 7 * len(avisos)

    # Habilidades
    extra, vistas = 0, []
    for hab, peso in PERFIL["habilidades"].items():
        if contiene(hab, titulo):
            extra += 4 * peso
            vistas.append(hab)
        elif contiene(hab, cuerpo):
            extra += 2 * peso
            vistas.append(hab)
    puntos += min(extra, 30)
    if vistas:
        motivos.append("encaja: " + ", ".join(vistas[:5]))

    if puntos < PERFIL["puntuacion_minima"]:
        return None
    ident = hashlib.sha1(o["url"].encode()).hexdigest()[:12]
    return {
        "id": ident, "titulo": o["titulo"], "empresa": o["empresa"], "ubicacion": o["ubicacion"],
        "url": o["url"], "fuente": o["fuente"], "fecha": o["fecha"], "area": area, "nivel": nivel,
        "espana": en_espana, "puntos": min(puntos, 100), "motivos": motivos,
        "avisos": avisos, "a_favor": a_favor,
        "resumen": o["descripcion"][:280],
    }


DESCARTES: dict[str, int] = {}  # por qué se descartaron ofertas por requisitos


# ---------------------------------------------------------------------- main
def main() -> int:
    hoy = datetime.now(timezone.utc).date().isoformat()
    anteriores = {}
    if SALIDA.exists():
        anteriores = {o["id"]: o for o in json.loads(SALIDA.read_text(encoding="utf-8")).get("ofertas", [])}

    resultado, leidas, estado = {}, 0, {}
    for fuente in FUENTES:
        nombre = fuente.__name__.removeprefix("fuente_")
        if nombre in PERFIL.get("fuentes_desactivadas", []):
            continue
        n = 0
        try:
            for bruta in fuente():
                n += 1
                p = puntuar(bruta)
                if p and (p["id"] not in resultado or p["puntos"] > resultado[p["id"]]["puntos"]):
                    resultado[p["id"]] = p
            estado[nombre] = n
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            estado[nombre] = f"error: {e}"
            print(f"  ! {nombre}: {e}", file=sys.stderr)
        leidas += n
        print(f"  {nombre}: {n} leídas")

    if leidas == 0:
        print("Ninguna fuente respondió; no se sobrescribe el archivo.", file=sys.stderr)
        return 1

    for o in resultado.values():
        o["vista_desde"] = anteriores.get(o["id"], {}).get("vista_desde", hoy)
    # Variantes del mismo puesto (p. ej. una por región) cuentan como una sola
    unicas = {}
    for o in sorted(resultado.values(), key=lambda o: -o["puntos"]):
        clave = (o["empresa"].lower(), re.sub(r"\([^)]*\)|\s+", " ", o["titulo"].lower()).strip())
        unicas.setdefault(clave, o)
    ofertas = sorted(unicas.values(), key=lambda o: o["fecha"] or "", reverse=True)
    ofertas.sort(key=lambda o: -o["puntos"])
    ofertas = ofertas[: PERFIL["max_ofertas"]]
    nuevas = sum(1 for o in ofertas if o["id"] not in anteriores)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "leidas": leidas, "nuevas": nuevas, "fuentes": estado, "descartes": DESCARTES, "ofertas": ofertas,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  descartadas por requisitos:", DESCARTES)
    print(f"{leidas} ofertas leídas -> {len(ofertas)} seleccionadas ({nuevas} nuevas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
