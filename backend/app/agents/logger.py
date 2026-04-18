"""Structured step logger.

Produces both (a) the legacy string entries for `state.workflow_steps`
(backward-compatible with existing UI) and (b) structured records that can be
emitted to stdout or shipped to a log aggregator.

Each log entry has:
    stage:   one of the known pipeline stages
    level:   INFO | WARN | ERROR
    message: human-readable line
    data:    optional structured payload
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ── Stage constants ───────────────────────────────────────────────────────────

STAGE_SUPERVISOR = "Supervisor"
STAGE_REASONER = "Reasoner"
STAGE_CONTEXT = "Context Analyzer"
STAGE_TOOL_SELECT = "Tool Selector"
STAGE_EXTRACT = "Extractor"
STAGE_PERSONALIZE = "Personalization"
STAGE_VALIDATE = "Validator"
STAGE_EXECUTE = "Tool Execution"
STAGE_OBSERVER = "Observer"
STAGE_FORMAT = "Response Formatter"
STAGE_ERROR = "Error Handler"
STAGE_CLARIFY = "Clarifier"
STAGE_MOOD = "Mood Reflection"


LEVEL_INFO = "INFO"
LEVEL_WARN = "WARN"
LEVEL_ERROR = "ERROR"


_LEVEL_ICON = {LEVEL_INFO: "✓", LEVEL_WARN: "⚠", LEVEL_ERROR: "✗"}


# ── Dataclass record ──────────────────────────────────────────────────────────

@dataclass
class LogEntry:
    stage: str
    level: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    def as_step_string(self) -> str:
        """Render as the legacy workflow_steps string format."""
        icon = _LEVEL_ICON.get(self.level, "•")
        return f"{icon} [{self.stage}] {self.message}"

    def as_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


# ── Module-level stdlib logger configured once ────────────────────────────────

_stdlib = logging.getLogger("eduorchestrator")
if not _stdlib.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _stdlib.addHandler(handler)
    _stdlib.setLevel(logging.INFO)


# ── Public helpers (one per level × used-as-function style) ───────────────────

def log(stage: str, message: str, level: str = LEVEL_INFO, **data: Any) -> LogEntry:
    """Emit a log entry to stdout and return it for inclusion in state."""
    entry = LogEntry(stage=stage, level=level, message=message, data=data)
    py_level = {
        LEVEL_INFO: logging.INFO,
        LEVEL_WARN: logging.WARNING,
        LEVEL_ERROR: logging.ERROR,
    }.get(level, logging.INFO)
    _stdlib.log(py_level, entry.as_json())
    return entry


def info(stage: str, message: str, **data: Any) -> LogEntry:
    return log(stage, message, LEVEL_INFO, **data)


def warn(stage: str, message: str, **data: Any) -> LogEntry:
    return log(stage, message, LEVEL_WARN, **data)


def error(stage: str, message: str, **data: Any) -> LogEntry:
    return log(stage, message, LEVEL_ERROR, **data)


# ── State-mutation helper ─────────────────────────────────────────────────────

# LangGraph state has `workflow_steps: Annotated[List[str], operator.add]`,
# which means the reducer ADDS node outputs to the existing list. So each
# node must return ONLY the new step strings as its delta — not the
# accumulated history. These helpers do that correctly.

def append_step(state_update: Dict[str, Any], entry: LogEntry) -> Dict[str, Any]:
    """Set workflow_steps on the update to ONLY the new entry.

    The graph's reducer (operator.add) will append it to the existing list.
    """
    state_update["workflow_steps"] = [entry.as_step_string()]
    return state_update


def append_steps(state_update: Dict[str, Any], entries: List[LogEntry]) -> Dict[str, Any]:
    """Set workflow_steps on the update to ONLY the new entries."""
    state_update["workflow_steps"] = [e.as_step_string() for e in entries]
    return state_update
