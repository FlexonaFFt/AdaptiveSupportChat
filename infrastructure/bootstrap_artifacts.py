import json
from pathlib import Path


def load_bootstrap_questions(path: str, limit: int) -> list[str]:
    file_path = Path(path)
    if not file_path.exists():
        return []

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    raw = data.get("questions", [])
    if not isinstance(raw, list):
        return []

    questions: list[str] = []
    for item in raw:
        question = str(item).strip()
        if question:
            questions.append(question)
        if len(questions) >= max(limit, 0):
            break
    return questions
