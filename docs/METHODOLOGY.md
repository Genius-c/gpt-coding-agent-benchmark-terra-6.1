# Methodology and provenance

## Recovered evidence

The original source is the attached `terratest.zip`, containing three submission directories. After the initial ZIP-based publication, the contributor supplied a comparison conversation and separate original Terra, Luna and Sol session extracts. The [sanitized report](SESSION_REPORT.md) adds the planned task/rubric, reported Medium setting, elapsed durations, action summaries, intermediate failures and fixes. Raw attachments remain private.

The task summary is a Python/SQLite asynchronous queue with two simultaneous workers, FIFO, cancellation/retry, restart recovery and a browser dashboard. The exact copy-button prompt is still unavailable. All three extracts report Medium reasoning and one recorded turn in Orbit, an IDE built by the contributor; this is reported session metadata rather than independent backend verification. Exact matched prompts, tool budgets, task-token consumption, cost and model snapshot identities remain unverified. No third-party release or leaderboard claim is imported from the conversation.

## Evidence classes

1. Original artifacts: source and submitted tests copied byte for byte. SHA-256 values and archive member names appear in `provenance.json`.
2. Author claims: descriptions in supplied documentation, such as concurrency limits, restart behavior and transaction integrity. These are not accepted solely because a README states them.
3. Submitted-suite reproduction: `unittest` executed separately in each model directory. Logs contain the actual observed test verdicts.
4. Independent probes: newly authored common HTTP checks, outside the submitted test modules. They are independent of the submitted assertions, but not a blind external audit: their author inspected the code and knew the model labels.

5. Original-session reconstruction: English translations and summaries of visible action prefixes, truncated outcomes and agent narration; distinct from later independent execution. Duplicated views are counted once.

## Independent checks

Each model runs in a fresh interpreter with an ephemeral loopback port and a temporary database. Adapters only construct the appropriate server; requests use the same endpoint and payload shape. Checks exercise first-attempt failure, retry, completion and retry conflict; a Korean-plus-emoji UTF-8 title round trip; rejection of boolean duration; blank status-filter handling; unknown creation-field handling; and cancellation of running work followed by a delayed status check.

The last two validation checks intentionally measure strict policies. The recovered planned rubric gives category weights but does not specify these input policies; accepting an unknown field or blank filter cannot automatically be scored as task failure. A passing cancellation check samples one interleaving, not every possible race. This independent suite does not establish FIFO, worker upper bounds under load, restart safety, transactional rollback, browser XSS resistance, accessibility or production readiness. Submitted tests may cover some of these, but they remain a separate evidence class.

## Publication hygiene

SQLite databases and sidecars were not opened or published. Bytecode, temporary directories and original README files are excluded. Publication uses an explicit file list, not a recursive upload of the working directory. Logs are sanitized to remove absolute benchmark and interpreter installation paths. Session summaries additionally omit account usage, wall-clock times, personal projects, IDE links and browser/session identifiers. Generic Windows/Korean/encoding context is retained for reproducibility, not device identification. Retained source may contain synthetic Korean test strings; those are part of the preserved code, not translated result prose.

To verify preservation, compute each published source file's SHA-256 and compare with `provenance.json`. Given the original ZIP, compare its listed member bytes directly. Reproduction uses no OpenAI API calls and measures artifact behavior, not fresh model generation.
