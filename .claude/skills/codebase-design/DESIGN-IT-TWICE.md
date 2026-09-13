# Design It Twice

Use when an important interface has substantively different viable designs and the user needs to compare their trade-offs. Naming and parameter order alone do not justify alternatives.

Compare the same concrete caller needs and constraints across designs. Each proposal should include interface shape and invariants, a usage example, hidden responsibilities, dependency/test strategy and costs. Use [DEEPENING.md](DEEPENING.md) if dependency placement matters.

Choose the number of alternatives and whether independent agents add value from the actual design uncertainty. Do not require 3+ agents, an arbitrary entry-point count or hypothetical flexibility. If delegating, give neutral constraints and relevant code, then wait for completion rather than polling.

Recommend the design with the best supported trade-off in caller effort, locality and seam placement. Preserve project vocabulary; fold the result into the existing design artifact.
