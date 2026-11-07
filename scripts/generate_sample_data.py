"""Generate the illustrative sample dataset in data/sample/.

The universities and degree names are real, but every cut-off score, scholarship
amount and income threshold produced here is ILLUSTRATIVE. They are derived
deterministically from a base value per degree type plus a hash-based offset, so
the output is reproducible and obviously not copied from any official source.

Run from the repository root:

    python scripts/generate_sample_data.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "sample"
YEARS = [2022, 2023, 2024, 2025]
LATEST_YEAR = YEARS[-1]
NOTICE = (
    "SAMPLE DATA. University and degree names are real, but cut-off scores, "
    "scholarship amounts and income thresholds are ILLUSTRATIVE and NOT OFFICIAL. "
    "Always check the university's and the awarding body's official publication."
)

UNIVERSITIES = [
    ("ucm", "Universidad Complutense de Madrid", "UCM", "Madrid", "Madrid"),
    ("uam", "Universidad Autónoma de Madrid", "UAM", "Madrid", "Madrid"),
    ("uc3m", "Universidad Carlos III de Madrid", "UC3M", "Getafe", "Madrid"),
    ("upm", "Universidad Politécnica de Madrid", "UPM", "Madrid", "Madrid"),
    ("ub", "Universitat de Barcelona", "UB", "Barcelona", "Cataluña"),
    ("uab", "Universitat Autònoma de Barcelona", "UAB", "Cerdanyola del Vallès", "Cataluña"),
    ("upc", "Universitat Politècnica de Catalunya", "UPC", "Barcelona", "Cataluña"),
    ("upf", "Universitat Pompeu Fabra", "UPF", "Barcelona", "Cataluña"),
    ("uv", "Universitat de València", "UV", "Valencia", "Comunidad Valenciana"),
    ("upv", "Universitat Politècnica de València", "UPV", "Valencia", "Comunidad Valenciana"),
    ("us", "Universidad de Sevilla", "US", "Sevilla", "Andalucía"),
    ("ugr", "Universidad de Granada", "UGR", "Granada", "Andalucía"),
    ("uma", "Universidad de Málaga", "UMA", "Málaga", "Andalucía"),
    ("usal", "Universidad de Salamanca", "USAL", "Salamanca", "Castilla y León"),
    ("uva", "Universidad de Valladolid", "UVa", "Valladolid", "Castilla y León"),
    ("unizar", "Universidad de Zaragoza", "UNIZAR", "Zaragoza", "Aragón"),
    ("ehu", "Universidad del País Vasco / Euskal Herriko Unibertsitatea", "UPV/EHU", "Leioa", "País Vasco"),
    ("usc", "Universidade de Santiago de Compostela", "USC", "Santiago de Compostela", "Galicia"),
    ("um", "Universidad de Murcia", "UM", "Murcia", "Murcia"),
    ("uniovi", "Universidad de Oviedo", "UNIOVI", "Oviedo", "Asturias"),
]

# slug -> (name, branch, base_cutoff, years, ects, keywords)
DEGREE_TYPES: dict[str, tuple[str, str, float, int, int, list[str]]] = {
    "medicina": ("Grado en Medicina", "ciencias_salud", 13.1, 6, 360, ["medico", "sanidad", "hospital", "salud"]),
    "enfermeria": ("Grado en Enfermería", "ciencias_salud", 11.6, 4, 240, ["enfermero", "cuidados", "sanidad", "salud"]),
    "fisioterapia": ("Grado en Fisioterapia", "ciencias_salud", 11.5, 4, 240, ["fisio", "rehabilitacion", "salud"]),
    "psicologia": ("Grado en Psicología", "ciencias_salud", 9.9, 4, 240, ["psicologo", "mente", "conducta", "terapia"]),
    "farmacia": ("Grado en Farmacia", "ciencias_salud", 10.6, 5, 300, ["farmaceutico", "medicamentos"]),
    "odontologia": ("Grado en Odontología", "ciencias_salud", 12.6, 5, 300, ["dentista", "dental"]),
    "veterinaria": ("Grado en Veterinaria", "ciencias_salud", 11.9, 5, 300, ["animales", "veterinario"]),
    "biotecnologia": ("Grado en Biotecnología", "ciencias", 12.4, 4, 240, ["genetica", "biologia", "laboratorio"]),
    "biologia": ("Grado en Biología", "ciencias", 10.4, 4, 240, ["seres vivos", "naturaleza", "laboratorio"]),
    "matematicas": ("Grado en Matemáticas", "ciencias", 11.6, 4, 240, ["mates", "algebra", "estadistica"]),
    "fisica": ("Grado en Física", "ciencias", 12.1, 4, 240, ["fisico", "astrofisica", "particulas"]),
    "quimica": ("Grado en Química", "ciencias", 9.6, 4, 240, ["quimico", "laboratorio"]),
    "ingenieria-informatica": (
        "Grado en Ingeniería Informática", "ingenieria_arquitectura", 10.6, 4, 240,
        ["informatica", "programacion", "software", "computacion", "ordenadores"],
    ),
    "ingenieria-aeroespacial": (
        "Grado en Ingeniería Aeroespacial", "ingenieria_arquitectura", 12.8, 4, 240,
        ["aviones", "aeronautica", "espacio"],
    ),
    "ingenieria-industrial": (
        "Grado en Ingeniería en Tecnologías Industriales", "ingenieria_arquitectura", 10.9, 4, 240,
        ["industrial", "mecanica", "electrica", "energia"],
    ),
    "ingenieria-civil": (
        "Grado en Ingeniería Civil", "ingenieria_arquitectura", 6.4, 4, 240,
        ["caminos", "obras publicas", "puentes"],
    ),
    "telecomunicacion": (
        "Grado en Ingeniería de Tecnologías y Servicios de Telecomunicación", "ingenieria_arquitectura", 9.6, 4, 240,
        ["teleco", "redes", "comunicaciones", "electronica"],
    ),
    "arquitectura": ("Grado en Fundamentos de la Arquitectura", "ingenieria_arquitectura", 9.1, 5, 300, ["arquitecto", "edificios", "diseno"]),
    "ciencia-datos": (
        "Grado en Ciencia e Ingeniería de Datos", "ingenieria_arquitectura", 12.3, 4, 240,
        ["datos", "big data", "inteligencia artificial", "estadistica", "programacion"],
    ),
    "derecho": ("Grado en Derecho", "ciencias_sociales_juridicas", 9.1, 4, 240, ["abogado", "leyes", "juridico"]),
    "ade": (
        "Grado en Administración y Dirección de Empresas", "ciencias_sociales_juridicas", 9.5, 4, 240,
        ["ade", "empresa", "negocios", "empresariales", "gestion"],
    ),
    "economia": ("Grado en Economía", "ciencias_sociales_juridicas", 9.0, 4, 240, ["economista", "finanzas", "mercados"]),
    "periodismo": ("Grado en Periodismo", "ciencias_sociales_juridicas", 10.3, 4, 240, ["periodista", "comunicacion", "medios"]),
    "relaciones-internacionales": (
        "Grado en Relaciones Internacionales", "ciencias_sociales_juridicas", 12.0, 4, 240,
        ["diplomacia", "politica", "internacional"],
    ),
    "magisterio": (
        "Grado en Maestro en Educación Primaria", "ciencias_sociales_juridicas", 9.2, 4, 240,
        ["magisterio", "maestro", "profesor", "colegio", "ensenanza"],
    ),
    "criminologia": ("Grado en Criminología", "ciencias_sociales_juridicas", 10.9, 4, 240, ["criminologo", "seguridad", "delito"]),
    "historia": ("Grado en Historia", "artes_humanidades", 7.1, 4, 240, ["historiador", "pasado"]),
    "filosofia": ("Grado en Filosofía", "artes_humanidades", 6.0, 4, 240, ["filosofo", "pensamiento", "etica"]),
    "estudios-ingleses": ("Grado en Estudios Ingleses", "artes_humanidades", 9.0, 4, 240, ["ingles", "filologia", "idiomas"]),
    "bellas-artes": ("Grado en Bellas Artes", "artes_humanidades", 8.1, 4, 240, ["arte", "pintura", "escultura", "dibujo"]),
    "traduccion": (
        "Grado en Traducción e Interpretación", "artes_humanidades", 11.1, 4, 240,
        ["traductor", "interprete", "idiomas"],
    ),
    "historia-del-arte": ("Grado en Historia del Arte", "artes_humanidades", 5.6, 4, 240, ["arte", "museos", "patrimonio"]),
}

OFFERINGS: dict[str, list[str]] = {
    "ucm": ["medicina", "psicologia", "derecho", "periodismo", "filosofia", "bellas-artes",
            "ingenieria-informatica", "historia-del-arte"],
    "uam": ["medicina", "biotecnologia", "fisica", "matematicas", "derecho", "economia", "traduccion"],
    "uc3m": ["ingenieria-informatica", "ingenieria-aeroespacial", "ciencia-datos", "derecho", "ade",
             "periodismo", "relaciones-internacionales"],
    "upm": ["ingenieria-aeroespacial", "ingenieria-informatica", "arquitectura", "ingenieria-civil",
            "ingenieria-industrial", "telecomunicacion"],
    "ub": ["medicina", "psicologia", "farmacia", "biologia", "derecho", "filosofia", "estudios-ingleses"],
    "uab": ["medicina", "biotecnologia", "criminologia", "periodismo", "traduccion", "ciencia-datos"],
    "upc": ["ingenieria-informatica", "ingenieria-aeroespacial", "arquitectura", "telecomunicacion",
            "ingenieria-industrial", "matematicas"],
    "upf": ["ade", "economia", "derecho", "periodismo", "traduccion", "ingenieria-informatica"],
    "uv": ["medicina", "enfermeria", "fisioterapia", "psicologia", "derecho", "magisterio"],
    "upv": ["ingenieria-informatica", "arquitectura", "ingenieria-aeroespacial", "telecomunicacion",
            "ingenieria-industrial", "bellas-artes"],
    "us": ["medicina", "enfermeria", "fisioterapia", "derecho", "ade", "arquitectura", "historia-del-arte"],
    "ugr": ["medicina", "traduccion", "psicologia", "farmacia", "ingenieria-informatica", "matematicas", "filosofia"],
    "uma": ["medicina", "enfermeria", "ingenieria-informatica", "ade", "periodismo"],
    "usal": ["medicina", "biotecnologia", "traduccion", "derecho", "filosofia", "estudios-ingleses"],
    "uva": ["medicina", "enfermeria", "arquitectura", "ingenieria-informatica", "derecho"],
    "unizar": ["medicina", "veterinaria", "ingenieria-informatica", "ingenieria-industrial", "derecho"],
    "ehu": ["medicina", "enfermeria", "ingenieria-informatica", "derecho", "filosofia"],
    "usc": ["medicina", "farmacia", "derecho", "periodismo", "filosofia"],
    "um": ["medicina", "veterinaria", "odontologia", "criminologia", "magisterio"],
    "uniovi": ["medicina", "ingenieria-informatica", "derecho", "historia", "estudios-ingleses"],
}

# Offerings published as "admission without cut-off" (all applicants admitted).
WITHOUT_CUTOFF = {"ucm-filosofia", "usc-filosofia", "us-historia-del-arte", "ucm-historia-del-arte",
                  "uniovi-historia"}


def _unit(key: str) -> float:
    """Deterministic pseudo-random number in [0, 1) derived from a string."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0x100000000


def _clamp(score: float) -> float:
    return round(min(14.0, max(5.0, score)), 3)


def build_degrees() -> list[dict]:
    degrees = []
    unis = {u[0]: u for u in UNIVERSITIES}
    for uni_id, slugs in OFFERINGS.items():
        for slug in slugs:
            name, branch, base, years, ects, keywords = DEGREE_TYPES[slug]
            degree_id = f"{uni_id}-{slug}"
            without = degree_id in WITHOUT_CUTOFF
            cut_offs = []
            if not without:
                latest = base + (_unit(degree_id) - 0.5) * 1.2
                drift = (_unit(degree_id + ":drift") - 0.4) * 0.3
                for year in YEARS:
                    if year == YEARS[0] and _unit(degree_id + ":gap") < 0.15:
                        continue  # some offerings lack an older year, as in real catalogues
                    jitter = (_unit(f"{degree_id}:{year}") - 0.5) * 0.2
                    score = latest - drift * (LATEST_YEAR - year) + jitter if year != LATEST_YEAR else latest
                    cut_offs.append({"year": year, "score": _clamp(score), "round": "ordinaria"})
            degrees.append({
                "id": degree_id,
                "name": name,
                "university_id": uni_id,
                "branch": branch,
                "campus": unis[uni_id][3],
                "duration_years": years,
                "credits_ects": ects,
                "admission_without_cutoff": without,
                "cut_offs": cut_offs,
                "keywords": keywords,
                "source": "sample",
            })
    return degrees


def build_universities() -> list[dict]:
    return [
        {
            "id": uid,
            "name": name,
            "short_name": short,
            "city": city,
            "region": region,
            "ownership": "public",
            "source": "sample",
        }
        for uid, name, short, city, region in UNIVERSITIES
    ]


ALL_LEVELS = ["bachillerato", "fp_grado_medio", "fp_grado_superior", "grado", "master"]


def build_scholarships() -> list[dict]:
    def sch(sid, name, provider, scope, regions, levels, income, grade, amin, amax, desc, reqs):
        return {
            "id": sid, "name": name, "provider": provider, "scope": scope, "regions": regions,
            "levels": levels, "max_family_income": income, "min_grade": grade,
            "amount_min_eur": amin, "amount_max_eur": amax, "description": desc,
            "requirements": reqs, "source": "sample",
        }

    return [
        sch("sch-general-ministerio", "Beca general del Ministerio (modelo)", "Ministerio de educación (modelo genérico)",
            "national", [], ALL_LEVELS, 40000, 5.0, 300, 6000,
            "Modelo de la beca general estatal: componente de matrícula, cuantía fija ligada a la renta y "
            "componente variable.", ["Umbral de renta familiar", "Rendimiento académico mínimo", "Nacionalidad o residencia"]),
        sch("sch-excelencia-estatal", "Ayuda estatal a la excelencia académica (modelo)", "Ministerio de educación (modelo genérico)",
            "national", [], ["grado", "master"], None, 8.5, 1000, 2500,
            "Modelo de premio o ayuda por expediente sobresaliente, sin requisito de renta.", ["Nota media alta"]),
        sch("sch-colaboracion", "Beca de colaboración en departamentos (modelo)", "Ministerio de educación (modelo genérico)",
            "national", [], ["grado", "master"], 40000, 7.0, 2000, 2000,
            "Modelo de beca para colaborar en un departamento universitario durante el último curso.",
            ["Último curso de grado o primer curso de máster", "Nota media mínima"]),
        sch("sch-neae", "Ayuda para alumnado con necesidad específica de apoyo educativo (modelo)",
            "Ministerio de educación (modelo genérico)", "national", [], ["bachillerato", "fp_grado_medio", "fp_grado_superior"],
            None, None, 400, 1500, "Modelo de ayuda para alumnado con necesidad específica de apoyo educativo.",
            ["Acreditación de la necesidad de apoyo"]),
        sch("sch-movilidad-internacional", "Complemento de movilidad internacional (modelo)", "Programa europeo de movilidad (modelo genérico)",
            "national", [], ["grado", "master"], None, 6.0, 1500, 4500,
            "Modelo de complemento para estancias de estudio en otra universidad europea.",
            ["Plaza de movilidad concedida por la universidad"]),
        sch("sch-fp", "Ayuda para estudiantes de Formación Profesional (modelo)", "Ministerio de educación (modelo genérico)",
            "national", [], ["fp_grado_medio", "fp_grado_superior"], 30000, 5.0, 300, 3000,
            "Modelo de ayuda para ciclos formativos de grado medio y superior.", ["Umbral de renta familiar"]),
        sch("sch-madrid-excelencia", "Beca regional de excelencia (modelo, Madrid)", "Comunidad de Madrid (modelo genérico)",
            "regional", ["Madrid"], ["grado"], None, 9.0, 2000, 3000,
            "Modelo de beca regional para estudiantes con calificación de acceso muy alta.", ["Residencia en la comunidad"]),
        sch("sch-cataluna-matricula", "Reducción de matrícula por renta (modelo, Cataluña)", "Generalitat de Catalunya (modelo genérico)",
            "regional", ["Cataluña"], ["grado", "master"], 32000, 5.0, 200, 1800,
            "Modelo de bonificación parcial del precio de matrícula según tramos de renta.", ["Residencia o estudios en la comunidad"]),
        sch("sch-valencia-matricula", "Beca de matrícula autonómica (modelo, Comunidad Valenciana)", "Generalitat Valenciana (modelo genérico)",
            "regional", ["Comunidad Valenciana"], ["grado", "master"], 26000, 5.0, 300, 1500,
            "Modelo de ayuda autonómica que cubre la matrícula a quien no obtiene la beca general.", ["Umbral de renta familiar"]),
        sch("sch-andalucia-bonificacion", "Bonificación de créditos aprobados (modelo, Andalucía)", "Junta de Andalucía (modelo genérico)",
            "regional", ["Andalucía"], ["grado", "master"], None, 5.0, 100, 1200,
            "Modelo de bonificación del precio de los créditos aprobados en primera matrícula.",
            ["Créditos aprobados en el curso anterior"]),
        sch("sch-pais-vasco", "Beca autonómica de estudios postobligatorios (modelo, País Vasco)", "Gobierno Vasco (modelo genérico)",
            "regional", ["País Vasco"], ["bachillerato", "fp_grado_superior", "grado", "master"], 36000, 5.0, 300, 4000,
            "Modelo de convocatoria autonómica propia con componentes de matrícula y residencia.", ["Residencia en la comunidad"]),
        sch("sch-galicia", "Ayuda autonómica de matrícula (modelo, Galicia)", "Xunta de Galicia (modelo genérico)",
            "regional", ["Galicia"], ["grado"], 22000, 5.0, 300, 1200,
            "Modelo de ayuda de matrícula para rentas bajas.", ["Umbral de renta familiar"]),
        sch("sch-castilla-leon", "Ayuda universitaria autonómica (modelo, Castilla y León)", "Junta de Castilla y León (modelo genérico)",
            "regional", ["Castilla y León"], ["grado"], 28000, 5.5, 300, 1500,
            "Modelo de ayuda complementaria a la beca general.", ["Residencia en la comunidad"]),
        sch("sch-aragon", "Beca complementaria de matrícula (modelo, Aragón)", "Gobierno de Aragón (modelo genérico)",
            "regional", ["Aragón"], ["grado", "master"], 26000, 5.0, 300, 1400,
            "Modelo de ayuda de matrícula para quien queda fuera de la beca general.", ["Umbral de renta familiar"]),
        sch("sch-murcia", "Ayuda al estudio universitario (modelo, Murcia)", "Región de Murcia (modelo genérico)",
            "regional", ["Murcia"], ["grado"], 20000, 6.0, 300, 1000,
            "Modelo de ayuda regional para rentas bajas con rendimiento mínimo.", ["Umbral de renta familiar", "Nota media mínima"]),
        sch("sch-asturias", "Beca regional de residencia (modelo, Asturias)", "Principado de Asturias (modelo genérico)",
            "regional", ["Asturias"], ["grado", "master"], 24000, 5.0, 800, 2500,
            "Modelo de ayuda para estudiantes que se desplazan fuera de su domicilio familiar.", ["Residencia fuera del domicilio familiar"]),
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    universities = build_universities()
    degrees = build_degrees()
    scholarships = build_scholarships()
    metadata = {
        "dataset_version": "0.1.0-sample",
        "sample": True,
        "notice": NOTICE,
        "latest_cut_off_year": LATEST_YEAR,
        "score_scale": "Admission grade over 14 (PAU/EBAU: 10 access phase + up to 4 specific phase)",
        "description": "Illustrative dataset modelled on the data domain of Franky (franky.es).",
    }
    for name, payload in [("metadata", metadata), ("universities", universities),
                          ("degrees", degrees), ("scholarships", scholarships)]:
        (OUT / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"universities={len(universities)} degrees={len(degrees)} scholarships={len(scholarships)}")


if __name__ == "__main__":
    main()
