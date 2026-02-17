from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Rules:
    hide_on_next: bool = False
    replace_menu: bool = False


@dataclass(frozen=True)
class Button:
    button_id: str
    text: str
    next_block: str


@dataclass(frozen=True)
class Block:
    block_id: str
    block_type: str
    text: str
    rules: Rules = field(default_factory=Rules)
    next_block: Optional[str] = None
    menu_id: Optional[str] = None
    buttons: tuple[Button, ...] = ()

    @property
    def has_interaction(self) -> bool:
        return len(self.buttons) > 0


@dataclass(frozen=True)
class Flow:
    flow_id: str
    start_block: str
    blocks: dict[str, Block]
