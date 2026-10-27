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

No historical scores from the earlier conversation are asserted because its analysis was unavailable in the recovered reference. There is no aggregate score, significance claim or general winner.
