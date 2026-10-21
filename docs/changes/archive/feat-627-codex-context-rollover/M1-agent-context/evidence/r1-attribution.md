# R1 findings: attribution and scoped repair

User clarification after R1: distinguish context-management regressions introduced by this unit from ordinary Agent behavior. This note does not erase the original failed product observations in acceptance.md or claim that the erroneous answer was correct.

## Confirmed integration defect: model plugin inventory

The model-facing WorkspaceOwner.command list_bundles path still filtered only `bundle.installed`, while the new control-plane inventory admitted the shipped dsh-agent-context bundle. A shipped default has installed=false, so the model received an empty list even when the bundle was enabled. This is a direct regression introduced by the default integration.

Repair: use the same shipped-bundle inclusion condition in the model-facing list. The existing workspace lifecycle test now calls list_bundles through actual native model tool dispatch before installing any workspace bundle and asserts the enabled default entry. It failed with entries=[] before the repair and passed after it (1 file / 1 test, 35s). No plugin code or distribution asset changed.

## Arithmetic: correct restored data, incorrect model computation

The 12 delivered rows match the independent generated oracle, with baseline sum 13482, confirmed sum 13237, gap sum 245. The model instead introduced aggregate values 14353 and 13308 while keeping gap245; these incorrect aggregates were subsequently saved in its notes and repeated after restart.

The actual provider request before the first erroneous final-report write is `2026-10-21_11-44-52_585-req-anthropic_messages.json`; all 12 correct baseline values and the complete row table are present. Product review independently verified every delivered row. There is no observed loss or transformation of those source values by Notes, History or rollover. This supports classifying the demonstrated error as model calculation/verification behavior, rather than a demonstrated context-data corruption. It does not prove that reset timing or salience has zero influence on every model response; no such causal claim is made.

No arithmetic-specific prompt, oracle answer injection, tool exception or source-data change is added to the feature. The original wrong artifact and failed R1 observation remain available.

## Forbidden bash attempts: constraint was present in the actual requests

- Before native tool/call seq382, the actual provider request `2026-10-21_11-42-37_313-req-anthropic_messages.json` contains two explicit `不用 bash` occurrences: the restored Notes result seq371 and progress-file result seq377. The current window had already recovered the prohibition before the model requested echo ok.
- Before seq654, request `2026-10-21_11-44-34_432-req-anthropic_messages.json` contains `禁用 bash` in the restored Notes task heading (seq649), together with the original constraint reference. The model nevertheless requested directory listing. The precise text is a heading/reference, not a claim that the full original user message was automatically retained.
- Both requests reached the ordinary approval path and were rejected; no prohibited shell action executed. Successful approval enforcement does not turn those model attempts into compliant behavior.

Thus the observed failure is not absence of the prohibition from model input. Instruction adherence/salience is still a model-behavior observation; attributing it specifically to this unit would require additional comparative evidence. Do not add a new instruction parser, hard-coded bash ban, automatic user-tail retention or prompt rewrite to disguise this distinction. The approved Codex prompts and local checkpoint text remain unchanged.

Raw request directory for these locators: `/Users/czj/Repos/LLM_PROXY/logs/session/2026-10-21_10-58-11_852_d21f31a1-755a-49f4-b9cf-25f21709791a/`. Native seqs are from the R1 session recorded in acceptance.md. Raw requests and full logs remain local; this note records only synthetic-task facts and bounded locators.

## Revalidation boundary

Revalidate the corrected model inventory and complete missing identity/default evidence. Retain the demonstrated R1 facts: 13 meaningful same-turn resets, intact per-row data, latest factual correction, original-result tail recovery, one and only one send, restart persistence, honest missing/error behavior and workspace lifecycle isolation. Keep ordinary model arithmetic/adherence observations visible separately; do not claim they were fixed by the one-line inventory change or call the original long-task answer fully correct. Independent review must assess this attribution, not accept it merely because the implementation owner proposed it.
