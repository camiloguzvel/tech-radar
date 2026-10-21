"""Criterios de etiquetado por frente (qué entra y qué no). Fuente única para la guía y el Excel."""

GENERAL = [
    "Juzga con el título y el resumen. Si no hay resumen y el título no alcanza, marca «dudoso».",
    "«Sí» = el trabajo trata sobre la tecnología del frente; no basta con mencionarla.",
    "Si no pertenece pero encaja en otro frente del mismo dominio, elígelo en «frente correcto».",
    "No busques más información fuera de la fila: la idea es medir lo que el sistema ve.",
    "Usa «nota» para lo que te haga dudar; esas notas ayudan a corregir las definiciones.",
]

CRITERIA: dict[str, dict[str, str]] = {
    "pfas_remocion": {
        "incluye": "Eliminar, destruir, degradar o capturar PFAS en agua, suelo o efluentes "
        "(adsorción, intercambio iónico, membranas, oxidación, electroquímica, plasma, "
        "incineración) y su evaluación técnica o económica.",
        "excluye": "Toxicología, exposición o monitoreo de PFAS sin tratamiento; regulación sin "
        "componente técnico; métodos analíticos solos; otros contaminantes.",
    },
    "desalinizacion_membranas": {
        "incluye": "Desalinización (ósmosis inversa o directa, destilación por membrana, "
        "electrodiálisis, desionización capacitiva), membranas para tratar o reutilizar agua, "
        "manejo de salmueras.",
        "excluye": "Membranas para gases, alimentos, bebidas, biofármacos o baterías; "
        "extracción de litio de salmueras si no trata agua.",
    },
    "agua_atmosferica": {
        "incluye": "Captar agua del aire: sorbentes, MOF, hidrogeles, atrapanieblas, rocío, "
        "condensación activa.",
        "excluye": "Evaporación solar de agua de mar; deshumidificación para climatización sin "
        "fin de producir agua; captación de lluvia.",
    },
    "reutilizacion_avanzada": {
        "incluye": "Procesos de oxidación avanzada (ozono, UV/peróxido, Fenton, persulfato, "
        "fotocatálisis, electro-oxidación) para tratar agua; reúso de aguas residuales tratadas.",
        "excluye": "Tratamiento convencional sin oxidación avanzada ni reúso; saneamiento rural "
        "o estudios sociales; fotocatálisis para energía o hidrógeno.",
    },
    "redes_inteligentes": {
        "incluye": "Monitoreo, sensores, detección de fugas, gemelos digitales y control en redes "
        "de agua potable o alcantarillado.",
        "excluye": "Hidrología y cuencas; calidad de ríos sin red; acuicultura; oleoductos o gas.",
    },
    "edicion_genica_vegetal": {
        "incluye": "CRISPR/Cas, edición de bases, prime editing o TALEN aplicados a plantas o "
        "cultivos: herramientas y aplicaciones.",
        "excluye": "Edición en humanos, animales o microbios; mejoramiento convencional o "
        "transgénesis clásica sin edición; revisiones de CRISPR sin foco vegetal.",
    },
    "biopesticidas": {
        "incluye": "Microorganismos, virus, nematodos o extractos usados para controlar plagas o "
        "enfermedades de cultivos: formulación, eficacia, producción.",
        "excluye": "Taxonomía o biología básica de hongos o insectos sin aplicación de control; "
        "pesticidas químicos sintéticos. Control de mosquitos para salud humana: «dudoso».",
    },
    "bioestimulantes_fijacion_n": {
        "incluye": "Bioestimulantes (microbianos, extractos de algas, ácidos húmicos), "
        "rizobacterias promotoras del crecimiento, biofertilizantes, fijación biológica de N "
        "para cultivos.",
        "excluye": "Fertilizantes químicos; microbiología de suelo descriptiva sin efecto en el "
        "cultivo; biocontrol de enfermedades (va a biopesticidas).",
    },
    "rnai_spray": {
        "incluye": "dsRNA o RNAi aplicado desde fuera de la planta (spray, tópico, "
        "nanopartículas, riego) para proteger cultivos.",
        "excluye": "RNAi expresado por una planta transgénica; RNAi usado solo para estudiar la "
        "función de un gen.",
    },
    "agricultura_precision": {
        "incluye": "Sensores, imágenes, IA, riego y fertilización de tasa variable, monitoreo de "
        "cultivos y suelo para decidir a nivel de lote.",
        "excluye": "Ganadería; IA genérica sin aplicación agrícola; estudios de mercado.",
    },
}
