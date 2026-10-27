# Limitations: Korean locale, Windows and generalizability

The contributor reports that the original experiment was conducted in a Korean-language Windows environment. The publication reproduction directly observed Windows 11, Korean locale and a CP949 preferred encoding; exact values are in the machine-readable result. These conditions limit interpretation.

## Language and international applicability

Korean instructions, UI labels, errors and tests can affect prompt interpretation, tokenization, generated wording and locale-specific assumptions. Translating the README into English does not turn this into an English-language generation experiment. The original prompts are unavailable, so semantic equivalence across languages cannot be checked. A successful Korean/emoji round trip is a narrow functional observation, not evidence of broad multilingual performance.

Do not extrapolate these results to English or other languages, countries, user populations, enterprise tasks or all coding-agent workflows. International comparison requires matched prompts reviewed by fluent speakers, multiple languages and tasks, repeated generations, randomized/blinded assessment and equivalent environments.

## Encoding and tooling

Windows Python or PowerShell output can use CP949 while source, browser HTTP and JSON expect UTF-8. During preparation, printing an original README produced a CP949 UnicodeEncodeError for punctuation. That was an inspection-tool encoding issue, not a model implementation failure. The reproduction runner explicitly sets `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` for child processes, so the published results do not test an entirely default CP949 execution environment. Unicode escaping in result JSON is a storage choice, not loss of the tested Unicode payload.

PowerShell quoting, path separators, Unicode paths, CRLF/LF behavior, terminal code pages and UTF-8 BOM handling can differ from Unix shells. This publication preserves original executable bytes, including line endings. It does not establish portability to every shell, filename normalization rule or case-sensitive filesystem.

## Operating system and runtime

Windows file locking and SQLite WAL/SHM cleanup, antivirus interference, thread scheduling, timer resolution, ephemeral ports, firewall and local execution restrictions can change test outcomes. Restricted local execution initially blocked loopback HTTP access and some temporary database access; that attempt is not treated as evidence of model defects. The final run was repeated with local execution access. The independent harness also had a syntax error during preparation that was corrected before the recorded reproduction; it is not attributed to any submission.

Only the recorded Python/SQLite combination was measured. A documented Python 3.11 minimum is an author claim, not validation across all supported interpreters. Linux, macOS, browser locale/timezone differences, alternate SQLite builds and stress workloads remain unverified. Browser rendering and manual UI quality were not assessed. UTC storage or browser-local display differences may affect user interpretation even when API tests pass.

## Experimental scope

There is one recovered artifact per label, no independent proof of the exact model backend, no controlled generation logs, no matched sampling budget and no repeated-run distribution. Test counts differ and cannot serve as a common score. Independent checks are small, code-informed and policy-dependent. No confidence intervals, statistical significance, universal ranking, cost-efficiency or speed conclusion is justified. More repetitions of these same artifacts would measure runtime variability, not variation in model generation.
