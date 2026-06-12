"""Persona pack loading & rendering (docs/personas.md).

- Markdown files with optional YAML-ish front matter (key: value lines).
- Language packs: personas/<lang>/*.md override the root (en) pack.
- Unknown {VARIABLES} are a boot error (typo protection).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ALLOWED_VARS = {
    "OWNER_NAME", "LAST_NAME_IF_SET", "NOW", "TZ", "TWILIO_NUMBER",
    "TASK_BRIEF", "SUCCESS_CRITERIA", "BUDGET",
    "REMINDER_TEXT", "URGENCY", "ATTEMPT_NUMBER", "MAX_CALL_MINUTES",
}
_VAR = re.compile(r"\{([A-Z_]+)\}")


class PersonaError(Exception):
    pass


@dataclass(frozen=True)
class Persona:
    id: str
    meta: dict
    body: str

    def variables(self) -> set[str]:
        return set(_VAR.findall(self.body))

    def render(self, **vars: str) -> str:
        missing = self.variables() - vars.keys()
        if missing:
            raise PersonaError(f"{self.id}: missing variables {sorted(missing)}")
        out = self.body
        for key, val in vars.items():
            out = out.replace("{" + key + "}", str(val))
        return out


def _parse(path: Path) -> Persona:
    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    body = text
    if text.startswith("---"):
        try:
            _, fm, body = text.split("---", 2)
        except ValueError as exc:
            raise PersonaError(f"{path.name}: malformed front matter") from exc
        for line in fm.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    pid = meta.get("id", path.stem)
    persona = Persona(id=pid, meta=meta, body=body.strip())
    unknown = persona.variables() - ALLOWED_VARS
    if unknown:
        raise PersonaError(f"{path.name}: unknown variables {sorted(unknown)}")
    return persona


def load_pack(root: Path, lang: str = "en") -> dict[str, Persona]:
    """Load root pack, then overlay personas/<lang>/ if present."""
    if not root.is_dir():
        raise PersonaError(f"persona directory not found: {root}")
    pack = {p.id: p for p in (_parse(f) for f in sorted(root.glob("*.md")))}
    if lang and lang != "en":
        sub = root / lang
        if not sub.is_dir():
            raise PersonaError(f"language pack not found: {sub}")
        pack.update({p.id: p for p in (_parse(f) for f in sorted(sub.glob("*.md")))})
    required = {"master_mode", "assistant_mode", "outbound_call", "wakeup"}
    missing = required - pack.keys()
    if missing:
        raise PersonaError(f"persona pack incomplete, missing: {sorted(missing)}")
    return pack
