"""Wire schema for LLM registry config — shared between Gateway and Kernel processes.

This module is the contract type for LLM configuration. It is not a Gateway YAML
detail; it is the serialized form used to transfer LLM registry state from Gateway
to Kernel via env (NANO_MULTIAGENT_LLM_CONFIG_JSON).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LLMModelPayload:
    """Describe one model entry in the LLM registry wire schema."""

    name: str
    extra_request_body: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class LLMProviderPayload:
    """Describe one provider entry in the LLM registry wire schema."""

    name: str
    base_url: str | None
    models: tuple[LLMModelPayload, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class LLMConfigPayload:
    """Top-level LLM registry wire schema shared between Gateway and Kernel.

    Gateway parses YAML into this type, serializes it to JSON, passes it via env
    NANO_MULTIAGENT_LLM_CONFIG_JSON to the Kernel process, which deserializes and
    calls init_model_registry(payload) to populate the in-process singleton.
    """

    default_model: str
    providers: tuple[LLMProviderPayload, ...] = field(default_factory=tuple)

    def to_json(self) -> str:
        """Serialize payload to a compact JSON string."""
        data: dict[str, Any] = {
            "default_model": self.default_model,
            "providers": [
                {
                    "name": p.name,
                    "base_url": p.base_url,
                    "models": [
                        {
                            "name": m.name,
                            "extra_request_body": m.extra_request_body,
                        }
                        for m in p.models
                    ],
                }
                for p in self.providers
            ],
        }
        return json.dumps(data, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "LLMConfigPayload":
        """Deserialize payload from a JSON string.

        Raises:
            ValueError: When the JSON structure is missing required fields.
            json.JSONDecodeError: When raw is not valid JSON.
        """
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("LLMConfigPayload JSON must be an object")
        if "default_model" not in data:
            raise ValueError("LLMConfigPayload JSON missing 'default_model'")
        providers: list[LLMProviderPayload] = []
        for p in data.get("providers", []):
            models: list[LLMModelPayload] = []
            for m in p.get("models", []):
                models.append(
                    LLMModelPayload(
                        name=m["name"],
                        extra_request_body=m.get("extra_request_body"),
                    )
                )
            providers.append(
                LLMProviderPayload(
                    name=p["name"],
                    base_url=p.get("base_url"),
                    models=tuple(models),
                )
            )
        return cls(
            default_model=data["default_model"],
            providers=tuple(providers),
        )
