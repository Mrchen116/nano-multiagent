# R14 bounded authentication feedback review

Reviewed fixed `2ebafe27b..b8f9a9bc6bfa0f64ed228f110c9724a9a11f0b7a`, solely the `AppModel.authenticate` catch in `NanoIMApp.swift` and its direct localization/error/countdown context. No surviving concrete finding: `code-review-r14.json` is `[]`.

HTTP 429 and 503 now select Chinese or English generic feedback through the existing `L` helper and current app language. Other HTTP statuses and non-API errors retain `error.localizedDescription`. The positive `APIError.retryAfter` update remains outside the status switch and unchanged, so the existing authentication button disablement and displayed countdown continue to use the same deadline. The patch changes neither request parameters nor authentication field/identity state, and preserves the existing busy guard and deferred reset.

`/tmp/nano-feat578-auth-build-r9.log` ends with `** BUILD SUCCEEDED **`. No UI or tests were run by this reviewer. Previously observed one-shot 429/503 transport behavior is retained as prior evidence; the new displayed wording remains pending safe installation and independent narrow UI verification. This static review does not grant product or device acceptance. R13 and earlier unaffected conclusions remain retained. No implementation edit or commit was made.
