# Prototype-only state checks

Run from the repository root after the frontend locked dependencies are installed:

```sh
for test in docs/changes/feat-616-personal-agent/research/prototype-state-checks/*.cjs; do node "$test" || exit 1; done
```

97 checks across the baseline and R1–R5 regression scripts. These execute the self-contained design prototype in jsdom with synthetic data, not product code. They do not verify browser rendering, accessibility, production security, real delivery receipts, credentials or DeepSeek. The prototype deliberately simulates asynchronous results. Independent review conclusions are in design-review.md.
