import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


QUESTION_RE = re.compile(r"^\s*В:\s*(.+?)\s*$", re.IGNORECASE)
ANSWER_RE = re.compile(r"^\s*О:\s*(.+?)\s*$", re.IGNORECASE)


def run_bootstrap(knowledge_dir: str, generated_dir: str, faq_file: str) -> dict:
    root = Path(knowledge_dir)
    out_dir = Path(generated_dir)
    out_file = Path(faq_file)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    questions: list[str] = []
    faq_pairs: list[dict[str, str]] = []
    sources: list[str] = []

    if root.exists():
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".txt"}:
                continue
            sources.append(str(path.relative_to(root)))
            text = path.read_text(encoding="utf-8", errors="ignore")
            file_questions, file_pairs = _extract_faq(text)
            questions.extend(file_questions)
            faq_pairs.extend(file_pairs)

    unique_questions = _unique(questions)
    if not unique_questions:
        unique_questions = [
            "Какой срок возврата товара?",
            "Сколько стоит доставка?",
            "Как связаться с оператором?",
        ]

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "knowledge_dir": knowledge_dir,
        "sources": _unique(sources),
        "questions": unique_questions,
        "faq": faq_pairs,
    }

    out_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data


def _extract_faq(text: str) -> tuple[list[str], list[dict[str, str]]]:
    questions: list[str] = []
    pairs: list[dict[str, str]] = []
    pending_question: Optional[str] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        q_match = QUESTION_RE.match(line)
        if q_match:
            pending_question = q_match.group(1).strip()
            questions.append(pending_question)
            continue

        a_match = ANSWER_RE.match(line)
        if a_match and pending_question:
            pairs.append({"q": pending_question, "a": a_match.group(1).strip()})
            pending_question = None
            continue

        if "?" in line and len(line) <= 120:
            normalized = line.strip(" -•\t")
            if normalized:
                questions.append(normalized)

    return questions, pairs


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.strip()
        if not key:
            continue
        lowered = key.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(key)
    return out


if __name__ == "__main__":
    knowledge_dir = os.getenv("KNOWLEDGE_DIR", "core/knowledge").strip()
    generated_dir = os.getenv("GENERATED_DIR", "core/generated").strip()
    faq_file = os.getenv("GENERATED_FAQ_FILE", "core/generated/faq.json").strip()
    result = run_bootstrap(
        knowledge_dir=knowledge_dir,
        generated_dir=generated_dir,
        faq_file=faq_file,
    )
    print(
        f"bootstrap_done: sources={len(result['sources'])}, questions={len(result['questions'])}, file={faq_file}"
    )
