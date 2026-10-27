# Additional Queue Edge-Case Reproduction

## Scope and provenance

These probes are supplemental, not replacements for the five checks in `probes/http_probe.py`. They were adapted from separately authored external probes from the same contributor conversation. They inspect the three published artifacts, not a new generation run. They use isolated SQLite databases and do not modify the original model source.

The recovered Korean prompt, translated in [TASK_PROMPT.md](../TASK_PROMPT.md), explicitly requires FIFO waiting, meaningful attempt increments, first-actual-execution failure, and restart recovery. Exact model-input text is still not independently visible in the Orbit transcripts.

## Reproduce

Run from the repository root, using Python 3.11+:

```console
python probes/edge_cases.py terra
python probes/edge_cases.py luna
python probes/edge_cases.py sol
python probes/crash_recovery.py terra
python probes/crash_recovery.py luna
python probes/crash_recovery.py sol
```

An observation marked `passed` is a claim by the probe's specified policy, not proof of general correctness. The scripts deliberately run each model in a separate interpreter invocation. Do not run all three imports in one interpreter: they contain overlapping Python module names.

## Observations recovered in this session

The original archive's SHA-256 is `8f5c45b4d2e83aef70a2d281a45770224cb366d892e9032320542e07ae4aac1a`. Its source-file digests match `provenance.json`. The earlier external scripts were rerun against that archive in a Linux container with Python 3.13.5 and SQLite 3.46.1 on 2026-10-27. This is a distinct environment from the Korean Windows publication run.

| Check | Terra 6.1 | Luna 6 | Sol 6.1 |
| --- | --- | --- | --- |
| Previously queued B starts before older A's retry | Pass | **Fail: A starts first** | Pass |
| Cancel-before-start, retry: first actual run fails, attempt is 1 | Pass | Pass | **Fail: completes, attempt is 2** |
| Forced exit during first run, restart: succeeds on attempt 2 | Pass | Pass | **Fail: fails with attempt 1** |

Interpretation:

- **Luna:** `ORDER BY rowid` places the original job before a newer queued job even after that older job is retried. The retry does not receive a new FIFO ticket.
- **Sol (cancelled before running):** attempt numbering is advanced when the job is initially queued and again on retry, rather than at actual worker start. Thus the first real execution skips its configured first-attempt failure.
- **Sol (crash recovery):** re-queuing a previously running job does not advance its attempt on worker restart, so the same first-attempt failure condition is applied again.
- **Terra:** the tested paths passed; this does not mean all concurrency interleavings or long-running operation have been proven correct.

The original queue code stays unchanged, preserving each submission's behavior.

## Boundaries and caveats

- An abrupt exit via `os._exit(0)` simulates a hard process termination without graceful cleanup. It is a destructive operation **only inside the disposable test child process**; never run this on a shared service.
- Event ordering and worker timing are scheduling-dependent. Repeat runs on additional operating systems and inspect actual event records.
- FIFO in this probe means entry order into the pending queue, not the job's original creation order after a retry.
- The prompt's phrase “increment attempt on retry” can admit different interpretations; this report uses the observable requirement that the first **actual** execution should fail when `fail_first_attempt` is enabled. The full transcript metadata does not independently prove which inputs were sent.
- These checks supplement, but do not replace, UI, security, concurrency saturation, race fuzzing, Windows process lifecycle, and broader validation tests.
- The probe scripts were translated/rewritten in English for publication. The reproduction outputs above come from the prior scripts run against the same source archive, not from a separate execution of the newly published versions.
- This is one artifact per model label and is not a statistically valid leaderboard.
