# Integrated product selected approval metrics

Captured: 2026-10-27T13:26:23.571Z. Product tree334bf622; execution report R5 in [acceptance.md](acceptance.md).

Source: public RuntimeClient initialize/session.observe, exact original host partitions, profiles and trusted bindings. Gateway/IM/DSH and reviewer proxy stopped first. Product calls refused; original observation stayed only in memory. Only36 selected Global calls and10 selected PA calls are represented. First mixed-host initialization failed before observation; corrected native partitioning succeeded, shutdown/exit0. No tool permission bypass or raw export.

Full minimized fields: [integrated-product-audit-metrics.json](integrated-product-audit-metrics.json). HTTP counts are not attempts. Missing disclosure/notice approval rows remain unknown; this audit does not close R5-PA1.

## review668-integrated-cc

Session `2b54b2de-8b0c-4c7d-82cd-7b328d8a9b36`. Selected calls 18; retry aggregates 18; attempts 31; unique review IDs 18; missing approval rows 0.

| callId | reviewId | attempts category / ms | extra / invalid | final |
|---|---|---|---|---|
| `call_6b5acfda85be4a1e958d69684a611d33` | `19ed4b4e-7dad-4ef5-ab3c-bc7fd94ac843` | allow:2788 | 0/0 | allow |
| `call_8f16e66ec14b4f58a91b757898240f8e` | `552cfa3f-94b0-4461-aa3a-4a1e9d718d56` | allow:3859 | 0/0 | allow |
| `call_61ea6118d73c4101b781a5b8430476c5` | `5d7bb119-e0d1-44e6-8f19-3d0b1f8a112f` | allow:2396 | 0/0 | allow |
| `call_053591d06f464b938bc33e2bf8a51423` | `228dc7a6-cc6a-4d8b-a6b2-41b745c06bb4` | service:23 → allow:2933 | 1/0 | allow |
| `call_48e1cdb13ff74399b6e2f2736ae5cee3` | `0ddfda89-c18f-41cf-9899-96f79d06e523` | service:8 → service:5 → service:10 | 2/0 | service |
| `call_2e776a405dbe42f5a4f11f37adc7585a` | `8e836314-c69a-4379-89ce-fb85cd5267d3` | auth:17 | 0/0 | auth |
| `call_673132ee520949268ad2b38f898511e3` | `bc894da6-5151-4a37-be68-d7fb6e53f3e8` | deny:23 | 0/0 | deny |
| `call_508d01cc6c4c4301af15713f1851864d` | `36055ca5-8847-461d-99cc-544018833256` | invalid:21 → invalid:5 | 1/1 | invalid |
| `call_3bcd1de92e064138bc5a40e868327743` | `3bb63d40-d6ac-45ae-9ffc-68955cd6dd1c` | invalid:20 → service:16 → allow:5013 | 2/1 | allow |
| `call_6c746501c9574123a1e05aaac3da4004` | `1b195fb7-085c-4252-9d23-790e703b5396` | service:6 → invalid:9 → invalid:13 | 2/1 | invalid |
| `call_06537ac650df4aa39f252d514a2e1aef` | `f9f00b9c-9cc0-4f29-b298-ac3584062b38` | service:17 → transport:9 → allow:4441 | 2/0 | allow |
| `call_463088543f4e42a9b7e32bb7ee34ea53` | `f87e8c98-ff10-4fc6-b071-e7f8c3958d40` | invalid:16 → invalid:4 | 1/1 | invalid |
| `call_afb6015085e4454a88eeb02dce5e51d3` | `a881659a-f89a-451e-b940-1e024eff6ddf` | timeout:30006 → allow:3327 | 1/0 | allow |
| `call_4a83b4b1e4b54e03b50840486ec38a75` | `eab83f29-30f3-45b7-9a13-6e442a18d790` | cancel:95 | 0/0 | cancel |
| `call_329627790a044baeb6cc67777c53ce3e` | `89d86f36-9a81-4fc1-bc84-737a747f9325` | service:10 | 0/0 | cancel |
| `call_29a5f590b1ea40da99c7f2f239fc58a7` | `4f54a4c0-6ad2-4eff-a45f-d562a40154c9` | service:20 → allow:3573 | 1/0 | allow |
| `call_c8ed761f8df54dad9c06281d05b2f519` | `7aecb74a-b8e1-4f9f-b0f0-20b097aaaf86` | auth:9 | 0/0 | auth |
| `call_0880cb1112fd43f99d54979ba05c8f9f` | `a911ab41-e788-4cdf-86e7-e790844284b0` | cancel:161 | 0/0 | cancel |

Missing row callIds: none.

Backoff cancel `call_329627790a044baeb6cc67777c53ce3e`: audit.time - attempt.end = 57ms; recorded delayAfterMs=500; extraUsed=0.

## review668-integrated-codex

Session `f6b55bbf-ec82-4f1a-af96-fe1eda639889`. Selected calls 18; retry aggregates 18; attempts 31; unique review IDs 18; missing approval rows 0.

| callId | reviewId | attempts category / ms | extra / invalid | final |
|---|---|---|---|---|
| `call_43fb8ee021c340e881e693df71e0fc12` | `408e9088-ed4c-4fd7-a8d5-6a53998f5590` | allow:4370 | 0/0 | allow |
| `call_caade33bab7247fd936c7caf15847168` | `3030afa3-a4b1-4930-bd9f-3891c14e8b8b` | allow:2362 | 0/0 | allow |
| `call_a0d0125eba1f447a9400b59d2caeb236` | `93facd4f-d580-4228-b6c4-3ba615e0952c` | allow:4448 | 0/0 | allow |
| `call_926d4c8d76cc4482a529430802221a4d` | `e35afe4c-9e9f-4d7d-a98a-f4efde3cbae0` | service:42 → allow:2215 | 1/0 | allow |
| `call_4a111fd0913048d3b54e3226705b074a` | `a5681fc1-a0c0-4a5b-8052-1ed0d364cb72` | service:59 → service:90 → service:85 | 2/0 | service |
| `call_fa0a609bc03c47be835fe8c019e2b6a9` | `b67f92bd-d24d-4256-a083-64a26665abd2` | auth:90 | 0/0 | auth |
| `call_288713de4a9043fd8dd9ad561d86d232` | `1e54e96e-58ff-4a52-81aa-df3e931deafd` | deny:78 | 0/0 | deny |
| `call_5ae8280efa324dbbbcf919fc0f82e0dd` | `3cdcff9c-041b-4b6e-b3e6-33bd2d4fa131` | invalid:52 → invalid:80 | 1/1 | invalid |
| `call_fb32ea6bbc5a4f6f8c28bd03ae21183c` | `8abd58b2-c670-4cc3-a3bb-6d5a817a4e26` | invalid:94 → service:86 → allow:3269 | 2/1 | allow |
| `call_0660ec4f1c354f119bec74bd47f7f227` | `d7111686-3a5a-488f-8829-560120894c5c` | service:57 → invalid:61 → invalid:66 | 2/1 | invalid |
| `call_0596696e830e45899bfcf1874a7d6153` | `21af9ec9-d782-49cf-9e7c-2ef9092c8501` | service:95 → transport:90 → allow:4407 | 2/0 | allow |
| `call_e01500fc22774b67ae12db062ce89ce2` | `4f4d8aba-209e-4132-a919-46aa2b251b3a` | invalid:64 → invalid:83 | 1/1 | invalid |
| `call_60c7648226d445f1b3b8dad4efcc8526` | `8462d50d-627e-4e56-a0d3-221c1aba9d92` | timeout:90055 → allow:2834 | 1/0 | allow |
| `call_7182ed06abd1420ba18c32710345a8cc` | `9f08cb94-2411-4391-b38f-88f806c13ad1` | cancel:215 | 0/0 | cancel |
| `call_b360c3d95ad8463486df694cc4dfcff4` | `4bc33c2f-4f21-4044-a216-1be7c13bac86` | service:110 | 0/0 | cancel |
| `call_e45b86c2b5304ae29105133f1f2d3e18` | `bbe089ca-0fc0-47bc-8f05-300873185c54` | service:237 → allow:3054 | 1/0 | allow |
| `call_dd665af3d0344719aed6a720d8fea623` | `4b6ca124-c593-4256-aa1a-26faa6c5e704` | auth:58 | 0/0 | auth |
| `call_ce541dcf03b04e9aa503788a5c8d07b1` | `b9f8db79-6ca2-4ad5-9ecd-a3c8f31596b5` | cancel:126 | 0/0 | cancel |

Missing row callIds: none.

Backoff cancel `call_b360c3d95ad8463486df694cc4dfcff4`: audit.time - attempt.end = 27ms; recorded delayAfterMs=500; extraUsed=0.

## pa_432e9d68e4a5

Session `f93e98b5-a734-46d7-8d55-57602a464b3d`. Selected calls 10; retry aggregates 3; attempts 4; unique review IDs 3; missing approval rows 0.

| callId | reviewId | attempts category / ms | extra / invalid | final |
|---|---|---|---|---|
| `call_64691ac6825543d392a1c795cabd75d9` | `2b956657-b54b-4f01-9d62-487c3a6089e8` | allow:3225 | 0/0 | allow |
| `call_23c2b8ae38164637882874ecc3961c7a` | `bef0707c-614c-4b34-bbaf-8c6c1bf2afdf` | allow:2484 | 0/0 | allow |
| `call_3000b9797ff7487384f33ccb32c071fe` | `92e4f282-6802-4c08-b785-233977d1a14f` | service:34 → allow:4561 | 1/0 | allow |

Missing row callIds: none.

The three selected failed PA1 inbox calls have `safe_tool / allow` records, not tool-classifier failures. Their later product operation still failed in notice handling. Four selected sends have `product_disclosure_gate / allow`, meaning dispatch is delegated to the separate product disclosure gate—not that disclosure was authorized or delivered. In particular the 503 disclosure case has this dispatch record but actual `unavailable` and zero delivery. No disclosure-model attempt or internal fixed-notice audit is fabricated from those rows.

## Interpretation limits

All observed reviewer IDs come from actual audit fields, not configured model guesses. Usage is reported only where present. SDK zero fields on transport/service failures and synthetic injected1/1 values are not live billable-token measurements. Do not sum child and aggregate usage or treat different provider cache accounting fields as a common bill. PA disclosure has no tool-retry aggregate by design; actual delivery and purpose evidence are independently recorded in acceptance.md.
