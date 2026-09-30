"""ziomek avatar state machine — ported from TypeScript.

Implements the same expression system, intensity preemption, and
cycle tracking as the TypeScript version in src/humanize/avatar/state-machine.ts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List


class TriggerType:
    BUTTON = "button"
    AXIS = "axis"
    VSCODE = "vscode"
    IDLE = "idle"


@dataclass
class ExpressionDef:
    name: str
    cycleCount: int
    durationMs: float  # 999999999 means infinite/level-triggered
    intensity: int
    triggers: list


@dataclass
class Trigger:
    type: str
    condition: Callable[["AvatarInput"], bool]


@dataclass
class AvatarInput:
    buttons: list  # [{"pressed": bool, "value": float}, ...]
    axes: list  # [float, ...]
    connected: bool
    streaming: bool
    chatFocused: bool
    errorState: bool


@dataclass
class ExpressionState:
    expressionName: str
    cycleIndex: int
    message: str | None = None
    messageExpiry: float | None = None


@dataclass
class _CurrentState:
    defn: ExpressionDef
    name: str
    cycleIndex: int
    timer: float
    cycleCount: int


# ── Expression definitions (same as TS version) ──────────────────────

_EXPRESSIONS: list[ExpressionDef] = [
    ExpressionDef(
        name="idle",
        cycleCount=60,
        durationMs=999999999,
        intensity=0,
        triggers=[Trigger(type=TriggerType.IDLE, condition=lambda inp: True)],
    ),
    ExpressionDef(
        name="bored",
        cycleCount=3,
        durationMs=900,
        intensity=0,
        triggers=[Trigger(type=TriggerType.IDLE, condition=lambda inp: True)],
    ),
    ExpressionDef(
        name="happy",
        cycleCount=1,
        durationMs=500,
        intensity=1,
        triggers=[
            Trigger(
                type=TriggerType.BUTTON,
                condition=lambda inp: inp.buttons[0]["pressed"] if len(inp.buttons) > 0 else False,
            )
        ],
    ),
    ExpressionDef(
        name="surprised",
        cycleCount=1,
        durationMs=300,
        intensity=2,
        triggers=[
            Trigger(
                type=TriggerType.BUTTON,
                condition=lambda inp: inp.buttons[1]["pressed"] if len(inp.buttons) > 1 else False,
            )
        ],
    ),
    ExpressionDef(
        name="curious",
        cycleCount=1,
        durationMs=400,
        intensity=1,
        triggers=[
            Trigger(
                type=TriggerType.BUTTON,
                condition=lambda inp: inp.buttons[2]["pressed"] if len(inp.buttons) > 2 else False,
            )
        ],
    ),
    ExpressionDef(
        name="looking",
        cycleCount=1,
        durationMs=200,
        intensity=1,
        triggers=[
            Trigger(
                type=TriggerType.BUTTON,
                condition=lambda inp: (
                    len(inp.buttons) > 15
                    and (
                        inp.buttons[12]["pressed"]
                        or inp.buttons[13]["pressed"]
                        or inp.buttons[14]["pressed"]
                        or inp.buttons[15]["pressed"]
                    )
                ),
            )
        ],
    ),
    ExpressionDef(
        name="focused",
        cycleCount=1,
        durationMs=999999999,
        intensity=2,
        triggers=[
            Trigger(
                type=TriggerType.AXIS,
                condition=lambda inp: len(inp.axes) >= 3 and (abs(inp.axes[0]) > 0.3 or abs(inp.axes[2]) > 0.3),
            )
        ],
    ),
    ExpressionDef(
        name="thinking",
        cycleCount=1,
        durationMs=999999999,
        intensity=1,
        triggers=[Trigger(type=TriggerType.VSCODE, condition=lambda inp: inp.streaming)],
    ),
    ExpressionDef(
        name="dying",
        cycleCount=2,
        durationMs=2000,
        intensity=3,
        triggers=[Trigger(type=TriggerType.VSCODE, condition=lambda inp: inp.errorState)],
    ),
]

_IDLE_SEQUENCE = ["bored", "bored", "bored", "neutral", "neutral", "neutral"]
_AXIS_THRESHOLD = 0.3


class AvatarStateMachine:
    """Avatar state machine — same logic as TypeScript version."""

    def __init__(self) -> None:
        self._current: _CurrentState | None = None
        self._idle_index = 0
        self._prev_buttons: set[int] = set()
        self._prev_axis_active = False
        self._prev_streaming = False
        self._prev_error_state = False
        self._current_expression_type: str | None = None
        self._current_message: str | None = None
        self._message_expiry_timestamp: float = 0
        self._timed_expression_timer: object | None = None
        self._message_timer: object | None = None

    def update(self, input: AvatarInput) -> None:
        """Process input — same logic as TS update()."""
        pressed_buttons: list[int] = []
        for i in range(len(input.buttons)):
            btn = input.buttons[i] if i < len(input.buttons) else {}
            pressed = btn.get("pressed", False) if isinstance(btn, dict) else False
            if pressed:
                pressed_buttons.append(i)
            if pressed and i not in self._prev_buttons:
                self._prev_buttons.add(i)
                self._try_start_button_expr(input, i)
            if not pressed:
                self._prev_buttons.discard(i)

        if len(pressed_buttons) > 0:
            pass  # logger.debug would go here

        self._update_level_triggers(input)

        if self._current is None:
            self._start_expression(self._find_idle_expression())

    def tick(self, dt_ms: float) -> ExpressionState:
        """Advance state by dt_ms — same logic as TS tick()."""
        if self._current is None:
            self._start_expression(self._find_idle_expression())

        if self._current is None:
            # Check message expiry
            has_msg = self._message_expiry_timestamp and time.time() * 1000 < self._message_expiry_timestamp
            return ExpressionState(
                expressionName="idle",
                cycleIndex=0,
                message=self._current_message if has_msg else None,
                messageExpiry=self._message_expiry_timestamp if has_msg else None,
            )

        self._current.timer += dt_ms

        # Handle cycle advancement
        frame_duration = (
            self._current.defn.durationMs / self._current.cycleCount
            if self._current.cycleCount > 1
            else self._current.defn.durationMs
        )

        while self._current.timer >= frame_duration:
            self._current.timer -= frame_duration
            if self._current.cycleCount > 1:
                self._current.cycleIndex += 1
                if self._current.cycleIndex >= self._current.defn.cycleCount:
                    leftover = self._current.timer
                    self._current = None
                    if self._current_expression_type in ("button", "external"):
                        self._current_expression_type = None
                    if self._current_expression_type is None:
                        self._start_expression(self._find_idle_expression())
                        return self.tick(dt_ms - leftover)
                    return self.tick(dt_ms)
            else:
                # Single-cycle expression ended
                leftover = self._current.timer
                self._current = None
                if self._current_expression_type in ("button", "external"):
                    self._current_expression_type = None
                if self._current_expression_type is None:
                    self._start_expression(self._find_idle_expression())
                    return self.tick(dt_ms - leftover)

        # Handle infinite duration (level-triggered)
        if self._current.defn.durationMs >= 999999999:
            if not self._is_trigger_active(self._current.defn):
                self._current = None
                self._current_expression_type = None
                return self.tick(dt_ms)

        # Check message expiry
        now_ms = time.time() * 1000
        has_msg = self._message_expiry_timestamp and now_ms < self._message_expiry_timestamp
        if not has_msg:
            self._message_expiry_timestamp = 0

        return ExpressionState(
            expressionName=self._current.name,
            cycleIndex=self._current.cycleIndex,
            message=self._current_message if has_msg else None,
            messageExpiry=self._message_expiry_timestamp if has_msg else None,
        )

    def reset(self) -> None:
        """Reset state machine to initial state."""
        self._current = None
        self._idle_index = 0
        self._prev_buttons.clear()
        self._prev_axis_active = False
        self._prev_streaming = False
        self._prev_error_state = False
        self._current_expression_type = None
        self._current_message = None
        self._message_expiry_timestamp = 0
        if self._message_timer:
            self._message_timer = None
        if self._timed_expression_timer:
            self._timed_expression_timer = None

    def getCurrentState(self) -> ExpressionState:
        return ExpressionState(
            expressionName=self._current.name if self._current else "idle",
            cycleIndex=self._current.cycleIndex if self._current else 0,
        )

    def getExpressionNames(self) -> list[str]:
        return [e.name for e in _EXPRESSIONS]

    def getDefaultExpression(self) -> str:
        return "idle"

    def setExpression(self, expression_name: str, duration_ms: float | None = None) -> bool:
        expr = next((e for e in _EXPRESSIONS if e.name == expression_name), None)
        if not expr:
            return False
        self._start_expression(expr)
        self._current_expression_type = "external"

        if self._timed_expression_timer:
            self._timed_expression_timer = None

        if duration_ms and duration_ms > 0:
            import threading

            def _timeout() -> None:
                self._current_expression_type = None
                self._timed_expression_timer = None

            # In Python we'd use timer threads; simplified here
            self._timed_expression_timer = threading.Timer(duration_ms / 1000, lambda: None)
            self._timed_expression_timer.daemon = True
            self._timed_expression_timer.start()

        return True

    def setMessage(self, text: str | None = None, duration_ms: float = 10000) -> None:
        if self._message_timer:
            self._message_timer = None

        if text and text.strip():
            self._current_message = text.strip()
            if duration_ms > 0:
                self._message_expiry_timestamp = time.time() * 1000 + duration_ms
                import threading

                def _clear_msg() -> None:
                    self._current_message = None
                    self._message_expiry_timestamp = 0

                self._message_timer = threading.Timer(duration_ms / 1000, _clear_msg)
                self._message_timer.daemon = True
                self._message_timer.start()
            else:
                self._message_expiry_timestamp = 0
        else:
            self._current_message = None
            self._message_expiry_timestamp = 0

    def getMessage(self) -> str | None:
        return self._current_message

    # ── Private helpers ──────────────────────────────────────────────

    def _try_start_button_expr(self, input: AvatarInput, btn_idx: int) -> None:
        for expr in _EXPRESSIONS:
            for trigger in expr.triggers:
                if trigger.type == TriggerType.BUTTON and trigger.condition(input):
                    if self._can_start(expr):
                        self._start_expression(expr)
                        self._current_expression_type = "button"
                        return

    def _update_level_triggers(self, input: AvatarInput) -> None:
        axis_active = len(input.axes) >= 3 and (
            abs(input.axes[0]) > _AXIS_THRESHOLD or abs(input.axes[2]) > _AXIS_THRESHOLD
        )

        if axis_active != self._prev_axis_active:
            self._prev_axis_active = axis_active
            if axis_active:
                if self._try_start_by_type("focused"):
                    self._current_expression_type = "axis"
            elif self._current_expression_type == "axis":
                self._current = None
                self._current_expression_type = None

        if input.streaming != self._prev_streaming:
            self._prev_streaming = input.streaming
            if input.streaming:
                if self._try_start_by_type("thinking"):
                    self._current_expression_type = "vscode"
            elif self._current_expression_type == "vscode" and self._current and self._current.defn.name == "thinking":
                self._current = None
                self._current_expression_type = None

        if input.errorState != self._prev_error_state:
            self._prev_error_state = input.errorState
            if input.errorState:
                if self._try_start_by_type("dying"):
                    self._current_expression_type = "vscode"
            elif self._current_expression_type == "vscode" and self._current and self._current.defn.name == "dying":
                self._current = None
                self._current_expression_type = None

    def _try_start_by_type(self, name: str) -> bool:
        expr = next((e for e in _EXPRESSIONS if e.name == name), None)
        if not expr:
            return False
        if not self._can_start(expr):
            return False
        self._start_expression(expr)
        return True

    def _find_idle_expression(self) -> str:
        return _IDLE_SEQUENCE[self._idle_index % len(_IDLE_SEQUENCE)]

    def _can_start(self, expr: ExpressionDef) -> bool:
        if self._current is None:
            return True
        if expr.intensity > self._current.defn.intensity:
            return True
        current_type = self._current_expression_type
        new_type = self._get_trigger_type(expr)
        if current_type == new_type:
            return False
        if current_type == "idle" and new_type in ("button", "axis", "vscode"):
            return True
        return False

    def _get_trigger_type(self, expr: ExpressionDef) -> str:
        for t in expr.triggers:
            if t.type != TriggerType.IDLE:
                return t.type
        return "idle"

    def _is_trigger_active(self, defn: ExpressionDef) -> bool:
        # Lifecycle handled by _update_level_triggers
        return True

    def _start_expression(self, name_or_def: str | ExpressionDef) -> None:
        if isinstance(name_or_def, str):
            expr_def = next(
                (e for e in _EXPRESSIONS if e.name == name_or_def),
                _EXPRESSIONS[0],
            )
            name = name_or_def
        else:
            expr_def = name_or_def
            name = name_or_def.name

        # For cycle expressions (bored → neutral), advance the idle index
        if name in ("bored", "neutral"):
            self._idle_index += 1
            name = _IDLE_SEQUENCE[self._idle_index % len(_IDLE_SEQUENCE)]
            expr_def = next(
                (e for e in _EXPRESSIONS if e.name == name),
                _EXPRESSIONS[0],
            )

        self._current = _CurrentState(
            defn=expr_def,
            name=name,
            cycleIndex=0,
            cycleCount=expr_def.cycleCount,
            timer=0.0,
        )
