import re


_LEADING_PHRASES = [
    r"^please\s+",
    r"^can you\s+",
    r"^could you\s+",
    r"^i want you to\s+",
    r"^i need you to\s+",
    r"^i'd like you to\s+",
    r"^i would like you to\s+",
    r"^you should\s+",
    r"^you need to\s+",
    r"^go ahead and\s+",
    r"^make sure to\s+",
    r"^try to\s+",
]

_LEADING_RE = re.compile("|".join(f"({p})" for p in _LEADING_PHRASES), re.IGNORECASE)


def _first_sentence(text: str) -> str:
    line = text.strip().split("\n")[0].strip()
    match = re.search(r"[.!?](\s|$)", line)
    if match:
        line = line[: match.start()].strip()
    return line


def _title_case(text: str) -> str:
    small_words = {"a", "an", "the", "and", "but", "or", "for", "nor",
                   "in", "on", "at", "to", "of", "by", "with", "from", "as", "is"}
    words = text.split()
    result = []
    for i, word in enumerate(words):
        if i == 0 or word.lower() not in small_words:
            result.append(word.capitalize())
        else:
            result.append(word.lower())
    return " ".join(result)


def generate_task_title(task_description: str) -> str:
    text = task_description.strip()
    if not text:
        return "Untitled Task"

    sentence = _first_sentence(text)

    cleaned = _LEADING_RE.sub("", sentence).strip()
    if not cleaned:
        cleaned = sentence

    cleaned = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()

    titled = _title_case(cleaned)

    if len(titled) <= 60:
        return titled

    truncated = titled[:57].rsplit(" ", 1)[0]
    return truncated + "..."
