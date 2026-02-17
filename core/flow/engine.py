from dataclasses import dataclass
from typing import Optional

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.flow.models import Block, Flow


@dataclass(frozen=True)
class RenderItem:
    text: str
    rules_hide_on_next: bool
    keyboard: Optional[InlineKeyboardMarkup] = None


class FlowEngine:
    def __init__(self, flow: Flow):
        self._flow = flow
        self._user_state: dict[int, str] = {}

    @property
    def flow_id(self) -> str:
        return self._flow.flow_id

    def start(self, user_id: int) -> list[RenderItem]:
        blocks, current = self._resolve_chain(self._flow.start_block)
        self._user_state[user_id] = current.block_id
        return [self._to_render_item(block) for block in blocks]

    def on_button(self, user_id: int, button_id: str) -> list[RenderItem]:
        current_id = self._user_state.get(user_id, self._flow.start_block)
        current_block = self._flow.blocks[current_id]
        next_id = None
        for button in current_block.buttons:
            if button.button_id == button_id:
                next_id = button.next_block
                break
        if not next_id:
            blocks, current = self._resolve_chain(current_id)
            self._user_state[user_id] = current.block_id
            return [self._to_render_item(block) for block in blocks]

        blocks, current = self._resolve_chain(next_id)
        self._user_state[user_id] = current.block_id
        return [self._to_render_item(block) for block in blocks]

    def _resolve_chain(self, start_block_id: str) -> tuple[list[Block], Block]:
        max_depth = 20
        chain: list[Block] = []
        current = self._flow.blocks[start_block_id]
        visited: set[str] = set()

        for _ in range(max_depth):
            chain.append(current)
            if current.block_id in visited:
                break
            visited.add(current.block_id)
            if current.has_interaction or not current.next_block:
                break
            current = self._flow.blocks[current.next_block]
        return chain, current

    def _to_render_item(self, block: Block) -> RenderItem:
        keyboard = None
        if block.has_interaction:
            kb = InlineKeyboardBuilder()
            for button in block.buttons:
                kb.button(
                    text=button.text,
                    callback_data=f"flow:{button.button_id}",
                )
            kb.adjust(1)
            keyboard = kb.as_markup()
        return RenderItem(
            text=block.text,
            rules_hide_on_next=block.rules.hide_on_next,
            keyboard=keyboard,
        )
