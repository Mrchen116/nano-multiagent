"""agent.sdk — the sole public surface for products embedding the agent kernel.

Products (coding_cli, personal_assistant) must import only from this package.
All other agent.* sub-packages are internal implementation detail.

Public API:
    build_kernel — assemble a Kernel from configuration
    Kernel       — in-process agent kernel with async-native interface
"""

from .kernel import Kernel, build_kernel

__all__ = ["Kernel", "build_kernel"]
