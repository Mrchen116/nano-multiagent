[
  {
    "file": "apps/im-server/src/work.ts",
    "line": 98,
    "summary": "[P1] Do not let a revoked company Agent block the private Agent's shared journal",
    "failure_scenario": "A personal-enabled company member can receive a company device and create a private global Agent on that same node. If company membership is suspended while a company Work event is unacknowledged, agentAvailable rejects that event and rolls back the entire append batch. GlobalAgent.flushWork uses one node-wide InboxStore journal and throughSeq for all Agents, so it resends the rejected company event before every later private event. GlobalAgent.receive awaits main()->flushWork() before wake(), and therefore even a new private chat never reaches session.submit. Independently reproduced at 59650f196 through real IM Work, InboxStore, NodeStore and GlobalAgent.receive with a stubbed runtime: private receive failed with scope_not_allowed; runtime calls were only [session.ensure]; session.submit was false. A private-only seq=2 retry also returned expected_seq=1. Preserve the company authorization denial while allowing the private journal/work to advance; add a mixed company/private revocation regression at the appropriate seam.",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "apps/im-server/assets/install.sh",
    "line": 29,
    "summary": "[P2] Promote a downloaded Node runtime only after extraction completes",
    "failure_scenario": "On a computer without an existing supported Node/npm, the installer extracts the official archive directly into the final tooling directory and treats executable bin/node as a complete installation. If extraction fails after bin/node is written (for example disk full), a repeat of the advertised recovery command skips extraction and runs with missing npm/libraries. Independently reproduced by executing the actual frozen install.sh with local download/tar fixtures: first extraction created executable final bin/node then failed; attempt1 exited 1 with the preserve/retry message; attempt2 skipped tar and exited 127 with npm: command not found. This is a controlled extraction-failure reproduction, not a claim about which files the product review's separate disk-full run had written. Extract into a temporary directory and promote only a complete verified runtime; failed attempts must remain safely retryable.",
    "review_mode": "full",
    "status": "CONFIRMED"
  },
  {
    "file": "apps/node/src/model-setup.ts",
    "line": 64,
    "summary": "[P2] Refresh local discovery when the user repairs or starts a connection",
    "failure_scenario": "The first setup status permanently memoizes discoverLocalModels, including an absent or stopped optional proxy. Starting/fixing the proxy afterward does not make it discoverable on any status poll, explicit query retry, browser refresh or re-login; only restarting the node creates another ModelSetup. Independently reproduced at 59650f196 by changing the discovery fixture from no proxy to a live proxy between two public handle({action:status}) calls: both snapshots returned {codex:false}, with discovery calls=1. The recovery journey says to repair/retry and reuse a local connection without editing configuration; the cached result prevents that path. Use a bounded refresh policy or explicit discovery retry and protect absent-to-available recovery with a behavioral test.",
    "review_mode": "full",
    "status": "CONFIRMED"
  }
]
