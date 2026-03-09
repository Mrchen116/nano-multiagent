"""Unit tests: LOCAL_CODING_PROFILE matches current coding defaults."""

from nano_multiagent.agent.prompting import CODING_SYSTEM_PROMPT
from nano_multiagent.platform.product import ProductProfile
from nano_multiagent.platform.products.local_coding import LOCAL_CODING_PROFILE


def test_local_coding_profile_is_product_profile() -> None:
    assert isinstance(LOCAL_CODING_PROFILE, ProductProfile)


def test_local_coding_profile_product_id() -> None:
    assert LOCAL_CODING_PROFILE.product_id == "local_coding"


def test_local_coding_profile_config_namespace() -> None:
    # Must match the global config directory documented in the architecture.
    assert LOCAL_CODING_PROFILE.config_namespace == "nanocode"


def test_local_coding_profile_system_prompt_uses_coding_system_prompt() -> None:
    """local_coding profile must use CODING_SYSTEM_PROMPT, not the generic DEFAULT_SYSTEM_PROMPT."""
    assert LOCAL_CODING_PROFILE.default_system_prompt == CODING_SYSTEM_PROMPT
    assert "coding assistant" in LOCAL_CODING_PROFILE.default_system_prompt or \
           "expert coding" in LOCAL_CODING_PROFILE.default_system_prompt


def test_local_coding_profile_has_display_name() -> None:
    assert LOCAL_CODING_PROFILE.display_name
    assert isinstance(LOCAL_CODING_PROFILE.display_name, str)
