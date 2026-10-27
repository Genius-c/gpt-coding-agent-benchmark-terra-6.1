# Methodology and provenance

## Recovered evidence

The source is the attached `terratest.zip`, containing three named submission directories. The preceding conversation preview did not expose its assistant analysis or earlier downloadable benchmark package: those messages were content-reference markers. Therefore earlier scores, timing, prompts, tool transcripts and independent-check claims could not be recovered and are not reproduced as facts here. This publication reconstructs a reproducible artifact comparison from the actual attached files.

The original task is inferred from the implementations: a standard-library Python/SQLite simulated asynchronous queue with two workers, an HTTP API and a local dashboard. This inference is not an exact original prompt. Original generation date, number of attempts, reasoning settings, token budget, latency, cost and model snapshot identities are unverified. The contributor's model labels are retained without asserting official release or availability facts.

## Evidence classes

1. Original artifacts: source and submitted tests copied byte for byte. SHA-256 values and archive member names appear in `provenance.json`.
2. Author claims: descriptions in supplied documentation, such as concurrency limits, restart behavior and transaction integrity. These are not accepted solely because a README states them.
3. Submitted-suite reproduction: `unittest` executed separately in each model directory. Logs contain the actual observed test verdicts.
4. Independent probes: newly authored common HTTP checks, outside the submitted test modules. They are independent of the submitted assertions, but not a blind external audit: their author inspected the code and knew the model labels.

## Independent checks

Each model runs in a fresh interpreter with an ephemeral loopback port and a temporary database. Adapters only construct the appropriate server; requests use the same endpoint and payload shape. Checks exercise first-attempt failure, retry, completion and retry conflict; a Korean-plus-emoji UTF-8 title round trip; rejection of boolean duration; blank status-filter handling; unknown creation-field handling; and cancellation of running work followed by a delayed status check.

The last two validation checks intentionally measure strict policies. Without the original rubric, accepting an unknown field or blank filter cannot automatically be scored as task failure. A passing cancellation check samples one interleaving, not every possible race. This independent suite does not establish FIFO, worker upper bounds under load, restart safety, transactional rollback, browser XSS resistance, accessibility or production readiness. Submitted tests may cover some of these, but they remain a separate evidence class.

## Publication hygiene

SQLite databases and sidecars were not opened or published. Bytecode, temporary directories and original README files are excluded. Publication uses an explicit file list, not a recursive upload of the working directory. Logs are sanitized to remove absolute benchmark and interpreter installation paths. Retained source may contain synthetic Korean test strings; those are part of the preserved code, not translated result prose.

To verify preservation, compute each published source file's SHA-256 and compare with `provenance.json`. Given the original ZIP, compare its listed member bytes directly. Reproduction uses no OpenAI API calls and measures artifact behavior, not fresh model generation.
