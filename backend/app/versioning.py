"""Content-hashed identity for agent versions.

An AgentVersion's identity should be a function of what actually determines its
behavior - model, system_prompt, tool_schema_hash, config - not its label (name) or
where its code came from (git_sha). Two versions with the same content_hash are the
same version, full stop, even if someone gave them different names or created them
from different commits; two different commits that happen to produce identical
model/prompt/tools/config are, for evaluation purposes, indistinguishable.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_agent_version_content_hash(
    model: str, system_prompt: str, tool_schema_hash: str, config: dict[str, Any]
) -> str:
    canonical = json.dumps(
        {
            "model": model,
            "system_prompt": system_prompt,
            "tool_schema_hash": tool_schema_hash,
            "config": config,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
