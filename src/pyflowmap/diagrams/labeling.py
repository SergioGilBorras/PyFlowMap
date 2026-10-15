"""Generic, deterministic labels for code symbols; no project-specific lookup tables.

Source identifiers and docstrings provide suggestions, not a translation of
arbitrary domain terminology. An optional semantic provider may refine labels but cannot
edit graph topology.
"""

import ast
import re

from ..project import Symbol

# Common programming *verbs*, not fully qualified symbols or domain nouns.
# Unknown verbs remain readable via identifier splitting.
VERBS = {
    "add": ("Add", "Añadir"),
    "analyze": ("Analyze", "Analizar"),
    "append": ("Append", "Agregar"),
    "assemble": ("Assemble", "Ensamblar"),
    "build": ("Build", "Construir"),
    "calculate": ("Calculate", "Calcular"),
    "check": ("Check", "Comprobar"),
    "clean": ("Clean", "Limpiar"),
    "collect": ("Collect", "Recopilar"),
    "complete": ("Complete", "Completar"),
    "consume": ("Consume", "Consumir"),
    "create": ("Create", "Crear"),
    "decompose": ("Decompose", "Descomponer"),
    "execute": ("Execute", "Ejecutar"),
    "fetch": ("Fetch", "Obtener"),
    "find": ("Find", "Encontrar"),
    "generate": ("Generate", "Generar"),
    "load": ("Load", "Cargar"),
    "parse": ("Parse", "Analizar"),
    "persist": ("Persist", "Persistir"),
    "plan": ("Plan", "Planificar"),
    "predict": ("Predict", "Predecir"),
    "process": ("Process", "Procesar"),
    "record": ("Record", "Registrar"),
    "recurse": ("Recurse", "Recorrer de forma recursiva"),
    "resolve": ("Resolve", "Resolver"),
    "read": ("Read", "Leer"),
    "research": ("Research", "Investigar"),
    "run": ("Run", "Ejecutar"),
    "save": ("Save", "Guardar"),
    "schedule": ("Schedule", "Programar"),
    "sanitize": ("Sanitize", "Sanear"),
    "send": ("Send", "Enviar"),
    "split": ("Split", "Dividir"),
    "transform": ("Transform", "Transformar"),
    "track": ("Track", "Seguir"),
    "update": ("Update", "Actualizar"),
    "validate": ("Validate", "Validar"),
    "write": ("Write", "Escribir"),
}

# Generic structural role endings, not application-specific class names.
ROLES = {
    "agent", "client", "controller", "handler", "loader", "manager", "planner",
    "predictor", "processor", "repository", "service", "worker",
}


def identifier_words(value: str) -> list[str]:
    """Separate snake_case, CamelCase and acronyms without losing source names."""
    parts = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", parts)
    return [word for word in re.split(r"[_\W\s]+", parts) if word]


def words(value: str) -> str:
    return " ".join(identifier_words(value)).capitalize()


def _description(symbol: Symbol) -> str | None:
    """Prefer a short, explicit description already supplied by the author."""
    doc = ast.get_docstring(symbol.node)
    if not doc:
        return None
    first = next((line.strip() for line in doc.splitlines() if line.strip()), "")
    if not first or len(first) > 85:
        return None
    return first.rstrip(".")


def describe_symbol(symbol: Symbol, language: str = "en") -> str:
    """Use source docstrings or common verb + symbol context, with no project assumptions.

    The subject is deliberately *not translated*: doing so requires a general
    language model/dictionary. A mixed-language fallback is more honest than
    making up domain-specific translations.
    """
    explicit = _description(symbol)
    if explicit:
        return explicit
    method_tokens = identifier_words(symbol.name)
    if not method_tokens:
        return "Activity" if language == "en" else "Actividad"
    action = method_tokens[0].lower()
    verb = VERBS.get(action)
    heading = (verb[0] if language == "en" else verb[1]) if verb else method_tokens[0].capitalize()
    remainder = method_tokens[1:]
    if symbol.owner and not remainder:
        tokens = identifier_words(symbol.owner)
        while tokens and tokens[-1].lower() in ROLES:
            tokens.pop()
        # Only remove class words that obviously repeat the method stem, e.g.
        # Analyze/Analysis or Plan/Planning. Never infer new process stages.
        tokens = [t for t in tokens if t.lower()[:4] != action[:4]]
        remainder = tokens
    return " ".join([heading, *[token.lower() for token in remainder]])


def describe_unresolved(name: str, language: str = "en") -> str:
    """Readable fallback when static dispatch cannot resolve a call."""
    items = identifier_words(name)
    if not items:
        return "Dynamic call" if language == "en" else "Llamada dinámica"
    action = items[0].lower()
    pair = VERBS.get(action)
    heading = pair[0 if language == "en" else 1] if pair else items[0].capitalize()
    return " ".join([heading, *[t.lower() for t in items[1:]]])
