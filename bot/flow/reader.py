import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

import yaml

from .models import Block, Button, Flow, Rules

_FLOW_HEADER_RE = re.compile(r"^#\s*Support Flow:\s*([A-Za-z0-9_.-]+)\s*$")
_BLOCK_HEADER_RE = re.compile(r"^##\s*block:\s*([A-Za-z0-9_.-]+)\s*$")
_SEPARATOR_RE = re.compile(r"^\s*---\s*$")
_ALLOWED_TYPES = {"message", "menu", "mes-menu"}


@dataclass(frozen=True)
class FlowSpecError:
    code: str
    message: str
    block_id: Optional[str] = None


class FlowSpecValidationError(Exception):
    def __init__(self, errors: list[FlowSpecError]):
        self.errors = errors
        summary = "\n".join(
            f"{e.code}: {e.message}" + (f" (block={e.block_id})" if e.block_id else "")
            for e in errors
        )
        super().__init__(summary)


def load_flow_from_markdown(path: str) -> Flow:
    source = Path(path)
    if not source.exists():
        raise FlowSpecValidationError(
            [FlowSpecError(code="E_FLOW_FILE_NOT_FOUND", message=f"File not found: {path}")]
        )

    content = source.read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines:
        raise FlowSpecValidationError(
            [FlowSpecError(code="E_FLOW_HEADER", message="Empty flow file.")]
        )

    header_match = _FLOW_HEADER_RE.match(lines[0].strip())
    if not header_match:
        raise FlowSpecValidationError(
            [
                FlowSpecError(
                    code="E_FLOW_HEADER",
                    message="First line must be '# Support Flow: <flow_id>'.",
                )
            ]
        )

    flow_id = header_match.group(1)
    blocks_text = _split_blocks(lines[1:])
    blocks: dict[str, Block] = {}
    errors: list[FlowSpecError] = []

    for chunk in blocks_text:
        if not chunk:
            continue
        block, block_errors = _parse_block(chunk)
        errors.extend(block_errors)
        if block:
            if block.block_id in blocks:
                errors.append(
                    FlowSpecError(
                        code="E_DUPLICATE_BLOCK_ID",
                        message="Duplicate block id.",
                        block_id=block.block_id,
                    )
                )
            else:
                blocks[block.block_id] = block

    errors.extend(_validate_graph(blocks))
    if errors:
        raise FlowSpecValidationError(errors)

    return Flow(flow_id=flow_id, start_block="start", blocks=blocks)


def _split_blocks(lines: list[str]) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _SEPARATOR_RE.match(line):
            if current:
                chunks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        chunks.append(current)
    return chunks


def _parse_block(lines: List[str]) -> Tuple[Optional[Block], List[FlowSpecError]]:
    errors: list[FlowSpecError] = []
    if not lines:
        return None, errors

    # trim leading empty lines
    while lines and not lines[0].strip():
        lines = lines[1:]
    if not lines:
        return None, errors

    header_match = _BLOCK_HEADER_RE.match(lines[0].strip())
    if not header_match:
        return None, [
            FlowSpecError(
                code="E_BLOCK_HEADER",
                message="Each block must start with '## block: <block_id>'.",
            )
        ]
    block_id = header_match.group(1)
    body = "\n".join(lines[1:]).strip()
    payload: dict[str, Any] = {}
    if body:
        loaded = yaml.safe_load(body)
        if not isinstance(loaded, dict):
            return None, [
                FlowSpecError(
                    code="E_BLOCK_BODY",
                    message="Block body must be a key-value mapping.",
                    block_id=block_id,
                )
            ]
        payload = loaded

    block_type = str(payload.get("type", "")).strip()
    if block_type not in _ALLOWED_TYPES:
        errors.append(
            FlowSpecError(
                code="E_UNKNOWN_TYPE",
                message=f"Unknown block type: {block_type!r}.",
                block_id=block_id,
            )
        )

    text = str(payload.get("text", "")).strip()
    if not text:
        errors.append(
            FlowSpecError(
                code="E_MISSING_FIELD",
                message="Field 'text' is required.",
                block_id=block_id,
            )
        )

    rules_payload = payload.get("rules", {}) or {}
    if not isinstance(rules_payload, dict):
        errors.append(
            FlowSpecError(
                code="E_RULES_INVALID",
                message="'rules' must be an object.",
                block_id=block_id,
            )
        )
        rules_payload = {}
    rules = Rules(
        hide_on_next=bool(rules_payload.get("hide_on_next", False)),
        replace_menu=bool(rules_payload.get("replace_menu", False)),
    )

    next_block = payload.get("next")
    if next_block is not None:
        next_block = str(next_block).strip() or None

    menu_id = payload.get("menu_id")
    if menu_id is not None:
        menu_id = str(menu_id).strip() or None

    buttons: tuple[Button, ...] = ()
    if block_type == "menu":
        raw_buttons = payload.get("buttons")
        if not isinstance(raw_buttons, list) or not raw_buttons:
            errors.append(
                FlowSpecError(
                    code="E_MISSING_FIELD",
                    message="Field 'buttons' is required for type 'menu'.",
                    block_id=block_id,
                )
            )
            raw_buttons = []
        buttons = _parse_buttons(raw_buttons, block_id, errors)
        if menu_id is None:
            errors.append(
                FlowSpecError(
                    code="E_MISSING_FIELD",
                    message="Field 'menu_id' is required for type 'menu'.",
                    block_id=block_id,
                )
            )

    if block_type == "mes-menu":
        raw_button = payload.get("button")
        if not isinstance(raw_button, dict):
            errors.append(
                FlowSpecError(
                    code="E_MISSING_FIELD",
                    message="Field 'button' is required for type 'mes-menu'.",
                    block_id=block_id,
                )
            )
            raw_button = {}
        buttons = _parse_buttons([raw_button], block_id, errors)

    if block_type == "message":
        if "buttons" in payload or "button" in payload or "menu_id" in payload:
            errors.append(
                FlowSpecError(
                    code="E_TYPE_FIELDS",
                    message="Type 'message' cannot contain button/menu fields.",
                    block_id=block_id,
                )
            )

    if block_type == "menu" and "button" in payload:
        errors.append(
            FlowSpecError(
                code="E_TYPE_FIELDS",
                message="Type 'menu' cannot contain singular 'button'.",
                block_id=block_id,
            )
        )
    if block_type == "mes-menu" and ("buttons" in payload or "menu_id" in payload):
        errors.append(
            FlowSpecError(
                code="E_TYPE_FIELDS",
                message="Type 'mes-menu' cannot contain 'buttons' or 'menu_id'.",
                block_id=block_id,
            )
        )

    if errors:
        return None, errors

    return (
        Block(
            block_id=block_id,
            block_type=block_type,
            text=text,
            rules=rules,
            next_block=next_block,
            menu_id=menu_id,
            buttons=buttons,
        ),
        [],
    )


def _parse_buttons(
    raw_buttons: list[dict[str, Any]],
    block_id: str,
    errors: list[FlowSpecError],
) -> tuple[Button, ...]:
    parsed: list[Button] = []
    seen_ids: set[str] = set()
    for item in raw_buttons:
        if not isinstance(item, dict):
            errors.append(
                FlowSpecError(
                    code="E_BUTTON_INVALID",
                    message="Button entry must be an object.",
                    block_id=block_id,
                )
            )
            continue
        button_id = str(item.get("id", "")).strip()
        text = str(item.get("text", "")).strip()
        next_block = str(item.get("next", "")).strip()
        if not button_id or not text or not next_block:
            errors.append(
                FlowSpecError(
                    code="E_BUTTON_INVALID",
                    message="Button must include 'id', 'text', and 'next'.",
                    block_id=block_id,
                )
            )
            continue
        if button_id in seen_ids:
            errors.append(
                FlowSpecError(
                    code="E_DUPLICATE_BUTTON_ID",
                    message=f"Duplicate button id: {button_id}.",
                    block_id=block_id,
                )
            )
            continue
        seen_ids.add(button_id)
        parsed.append(Button(button_id=button_id, text=text, next_block=next_block))
    return tuple(parsed)


def _validate_graph(blocks: dict[str, Block]) -> list[FlowSpecError]:
    errors: list[FlowSpecError] = []
    if "start" not in blocks:
        errors.append(
            FlowSpecError(
                code="E_MISSING_START",
                message="Block 'start' is required.",
            )
        )
        return errors

    terminal_exists = False
    for block in blocks.values():
        if block.next_block and block.next_block not in blocks:
            errors.append(
                FlowSpecError(
                    code="E_INVALID_NEXT",
                    message=f"Unknown next block: {block.next_block}.",
                    block_id=block.block_id,
                )
            )
        for button in block.buttons:
            if button.next_block not in blocks:
                errors.append(
                    FlowSpecError(
                        code="E_INVALID_NEXT",
                        message=f"Unknown next block in button '{button.button_id}': {button.next_block}.",
                        block_id=block.block_id,
                    )
                )
        if not block.next_block and not block.buttons:
            terminal_exists = True

    if "end" in blocks:
        terminal_exists = True
    if not terminal_exists:
        errors.append(
            FlowSpecError(
                code="E_NO_TERMINAL",
                message="At least one terminal block (or 'end') is required.",
            )
        )
    return errors
