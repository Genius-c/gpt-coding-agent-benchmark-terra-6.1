# Observed results

Reproduction recorded on 2026-10-27 UTC using Windows 11, Python 3.13.9 and SQLite 3.50.4. Host preferred encoding was CP949; child Python processes were forced to UTF-8. These are results of the supplied artifacts, not a new generation experiment.

| Submission label | Submitted suite | Independent checks meeting the probe policy |
| --- | --- | --- |
| Terra 6.1 | 9 tests, OK | 5 of 5 |
| Luna 6 | 10 tests, OK | 3 of 5 |
| Sol 6.1 | 10 tests, OK | 5 of 5 |

All three passed the independent failure/retry/completion sequence with a Korean-plus-emoji title, boolean-duration rejection, and the sampled running-cancellation check. Luna returned HTTP 200 for a blank status filter where the probe expected 400, and HTTP 201 for creation with an unknown field where the probe expected 400. Terra and Sol rejected both inputs. These are policy differences; the missing original prompt prevents deciding whether strict rejection was mandatory. Do not convert the counts into a model ranking.

Submitted suites were executed as supplied and all exited successfully. Their different test counts and assertion scope are not comparable coverage metrics. The new probes are separate from those tests, but cover only the limited behaviors documented in `METHODOLOGY.md`.

The machine-readable observations in `results/reproduction.json` and six log files provide the recorded evidence. Log timings reflect this one run and are not model generation latency. The initial restricted attempt encountered environment access failures; it was replaced by a completed run with loopback and temporary-file access. No runtime source fixes were made to the model submissions.

## Supplemental queue edge-case checks

The recovered Korean common task has been translated into English in `TASK_PROMPT.md`. A separate set of probes in `probes/edge_cases.py` and `probes/crash_recovery.py` covers FIFO after retry, cancelled-before-first-execution attempt accounting, and forced-exit restart behavior. The original probe implementations were rerun against the same archive in a Linux/Python 3.13.5 environment and yielded: Terra 3/3, Luna 2/3 (FIFO inversion), Sol 1/3 (attempt and restart failures). These counts are scenario checks, not a general accuracy score; see [EDGE_CASES.md](EDGE_CASES.md) for details and caveats.

## Original generation sessions, reported separately

The later supplied extracts report Terra 96 seconds / 7 actions, Luna 288 seconds / 21 actions, and Sol 368 seconds / 26 actions, each at Medium reasoning in the contributor-built Orbit IDE. Final agent claims were 9, 10 and 10 tests passing respectively. These are reported session summaries; the table above is the later measured reproduction of the ZIP artifacts.

Luna corrected attempt accounting, a premature test assertion, queued cancellation and FIFO tie ordering. Sol corrected Windows SQLite cleanup and polling-related detached UI nodes, and used Chrome with a 390-pixel viewport. Terra corrected form field access and explicitly did not visually inspect the UI. Failed startup checks and incomplete diagnostics are retained in the sanitized action ledger rather than hidden.

![Reproduction results](../assets/results-overview.png)

![Reported original sessions](../assets/session-evidence.png)

See [SESSION_REPORT.md](SESSION_REPORT.md) and `results/session-report.json`. There are no awarded weighted scores in the supplied text. No aggregate score, significance claim or general winner is assigned.
