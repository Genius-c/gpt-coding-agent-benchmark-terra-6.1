# Original sessions: sanitized reconstruction

This report translates and summarizes the contributor-supplied conversation extract. It records how the experiment was planned, what the visible agent did, and what was reported. It is not a verbatim transcript or a raw tool audit. Personal and machine-identifying details are excluded.

## Coverage of the supplied text

The supplied materials comprise the comparison proposal and Terra run, plus separate Sol and Luna session extracts. They do **not** contain a completed weighted evaluation or the full copy-button prompt. Many command bodies and outputs are visibly truncated. Duplicate expanded/collapsed views describe the same actions and are counted once: 7 for Terra, 21 for Luna, and 26 for Sol.

The contributor states that **Orbit is their own IDE**. It hosted these sessions and displayed model/reasoning metadata and action summaries. It is not treated as an official OpenAI application or an independent measuring instrument. Internal IDE URLs, project paths and browser/session identifiers are excluded.

Earlier release, pricing, community-reaction and third-party leaderboard claims in the conversation are unrelated to the local experiment and lack inspectable citations in this extract. They are not used as benchmark evidence or reproduced as verified facts.

## How the experiment was set up

The contributor proposed running Terra 6.1, Luna 6 and Sol 6.1 at **Medium reasoning**, each in a separate independent folder. The assistant recommended the same prompt for all three, with no additional hints or user-requested corrections during the first pass. These are reported/planned controls. The pasted metadata reports `gpt-6.1-terra`, `gpt-6-luna`, and `gpt-6.1-sol`, all with `medium` reasoning and one recorded turn. The transcript does not expose prompt text, so identical prompts and effective runtime controls cannot be independently audited. Internal self-corrections within the agent turn are visible and are described below.

The task summary describes a **Python + SQLite asynchronous job queue and browser dashboard** with:

- At most two simultaneous jobs and FIFO waiting order.
- Cancellation, retry and recovery after server restart.
- A browser dashboard with automatic updates.
- Concurrency protection and nine categories of automated testing.

The exact original prompt is not recoverable from this text: the conversation refers to a copy button, but supplies only the task summary. Endpoint specifications and detailed acceptance criteria must not be invented. Standard-library implementation details can additionally be inspected in the preserved source.

### Planned evaluation rubric

| Area | Planned maximum | Score actually available in the extract |
| --- | ---: | --- |
| Required functionality and API correctness | 25 | Not scored |
| Concurrency and race handling | 25 | Not scored |
| Database persistence and restart recovery | 15 | Not scored |
| Test effectiveness and pass rate | 15 | Not scored |
| UI completeness and usability | 10 | Not scored |
| Code structure and maintainability | 10 | Not scored |
| Total | 100 | No final score |

These are proposed weights, not achieved points. They are not converted into a radar chart or model ranking. `results/session-report.json` preserves the sanitized weights as data.

## What Terra did

The session UI reports **1 minute 36 seconds (96 seconds)** and **7 actions**. Absolute clock times are omitted. This is a UI-reported session duration, not an independently instrumented inference measurement.

| Action | Visible operation or sanitized reconstruction | Available outcome and evidence boundary |
| --- | --- | --- |
| T1 | Inspect the working directory; visible `Get-ChildItem` command prefix | Exit code 0; command body truncated |
| T2 | Create a directory; visible `New-Item -ItemT...` prefix | Exit code 0; target path removed |
| T3 | Write a Python source block beginning with `import json` | Exit code 0; full source-writing command unavailable |
| T4 | Write an HTML block beginning with a doctype | Exit code 0; full command unavailable |
| T5 | Python/test-related block, followed by test output | Visible cancellation and stale-worker test names report `ok`; full output truncated |
| T6 | Read/modify file content; visible `Get-Content -R...` prefix | Exit code 0; the agent reports correcting form-title field access, but the full patch is not visible |
| T7 | Python subprocess/HTTP smoke-check block | Visible output reports dashboard HTTP 200, 1,577 response bytes, and statistics HTTP 200 with zero jobs; output truncated |

The table is a translation and reconstruction from visible prefixes, output fragments and agent narration. It is not an exact command replay. No per-action durations can be recovered: repeated displayed timestamps are not sufficient timing instrumentation.

Terra's progress narration reports implementing transactional queue state and execution generations, adding the dashboard and HTTP concurrency tests, and correcting an HTML form property collision by using `form.elements`. Its final answer claims completion of SQLite persistence, state-change history, the two-worker limit, cancellation/retry, restart recovery, JSON endpoints and a one-second dashboard refresh.

The reported feature set is not accepted solely on narration. The source and later reproduction provide additional, separate evidence. The agent expressly said it **did not visually verify the dashboard in a browser**. No screenshots, browser interaction trace or visual-quality score is recovered.

## What Luna did

Orbit reports **4 minutes 48 seconds (288 seconds)** and **21 actions**. Luna first attempted a directory/search command, encountered unavailable `rg`, and fell back to PowerShell inspection. It wrote the server, static assets, README and tests, then ran the submitted suite.

The first test execution failed. Luna's narration attributes the problems to retry and worker-start code both incrementing the attempt count, and a concurrency test checking before the last job finished. It reported correcting both and passing nine tests. Later inspection found a missing queued-to-cancelled transition and a FIFO tie-order issue; it patched the implementation and added/updated tests. Its final report claims **10 tests passed, zero failed**. The visible trace includes a final successful test command, but its full output is truncated.

Startup checking was uneven: the trace shows a subprocess smoke check timing out after eight seconds, a PowerShell `Invoke-WebRequest` object-reference error, and launch commands ending with code 1. A separate Python request visibly returned **HTTP 200 and 2,373 response bytes**. The extract does not establish the causes of the failed launch checks or independently prove the same long-running server remained healthy. No browser automation or visual dashboard inspection is visible in Luna's 21 actions.

## What Sol did

Orbit reports **6 minutes 8 seconds (368 seconds)** and **26 actions**. Sol also encountered unavailable `rg` and used a fallback inspection. It created a launcher, queue server, static assets, tests and ignore rules. Its first suite execution failed; the agent reported **8 of 10 passing**, with two temporary-DB cleanup errors caused by SQLite connections left open on Windows. It reported closing those connections explicitly, rerunning successfully, and later running the final suite again with **10 passed, zero failed**. Full intermediate failure details are not present in the truncated output.

Sol attempted the in-app browser, received an unavailable-browser response, enumerated browsers and continued in Chrome. The trace includes typing a synthetic script-tag title, inspecting a first-attempt failure, attempting retry, and encountering **`Node is detached from document`**. Sol attributed this to replacing list/button nodes on each polling refresh, changed rendering to refresh only when job data changed, and retried the browser flow. It also exercised a **390-pixel viewport**, adjusted styling, and checked again.

Its final narration reports create → fail → retry → complete, literal display of the script text, and mobile-layout checking. The visible browser actions corroborate that these checks were attempted; the state dumps are truncated and no screenshot is supplied. This is more UI exercise than the other visible traces, not an independent security or accessibility audit. Launch output also includes process exit codes 1 and -1 without complete diagnostics; the UI success marker or startup banner alone cannot prove clean persistent server operation.

## What the models produced

The attached ZIP supplies executable artifacts for all three labels. This table describes those files separately from the reconstructed session actions.

| Label | Preserved implementation | Submitted suite | Original action trace available |
| --- | --- | ---: | --- |
| Terra 6.1 | Single `app.py`, static HTML/CSS/JS, SQLite queue with a lock/condition and execution generations | 9 tests | Partial, seven visible action entries |
| Luna 6 | Single `app.py`, static HTML/CSS/JS, SQLite queue with a condition, cancellation events and generation tracking | 10 tests | Partial, 21 visible action entries |
| Sol 6.1 | Launcher `app.py` plus `queue_server.py`, static HTML/CSS/JS, SQLite queue with two workers and per-execution cancellation signals | 10 tests | Partial, 26 visible action entries |

All three expose simulated job creation, listing/detail, cancellation, retry, statistics and event-history behavior. Their response shapes and attempt-count conventions differ. For example, Sol initializes attempt 1 on creation, while Terra and Luna advance the attempt when execution starts. This is an implementation observation, not a task-compliance judgment without the exact acceptance rules.

## Results and graphics

![Submitted suites and independent policy observations](../assets/results-overview.png)

The chart uses the already-recorded publication reproduction, not the original model's self-report. The submitted suites passed 9/9, 10/10 and 10/10 respectively. These are distinct model-authored test collections, not a common scale of quality. The independent matrix shows the same five probes for each artifact. Luna accepts a blank status filter and an unknown creation field; the strict probe policy expects rejection. With the original detailed requirements missing, those two differences cannot be labeled confirmed task defects.

![Original-session coverage and timing availability](../assets/session-evidence.png)

The original UI durations are 96, 288 and 368 seconds, with 7, 21 and 26 actions. These are single-turn session summaries, not pure inference latency. Sol's duration includes Chrome/mobile interaction and a UI correction; Luna's includes unsuccessful startup checks and self-correction. Tool availability and verification scope differ, so no general model-speed ranking or speedup ratio is calculated.

| Evidence class | Terra 6.1 | Luna 6 | Sol 6.1 |
| --- | --- | --- | --- |
| Original agent final test claim | 9 passed, 0 failed | 10 passed, 0 failed | 10 passed, 0 failed |
| Original HTTP/UI evidence | Dashboard 200; stats 200 | HTTP 200; several failed startup checks | Chrome interactions; viewport check; some launch exits nonzero |
| Later submitted-suite reproduction | 9 tests, OK | 10 tests, OK | 10 tests, OK |
| Later independent probes | 5 met policy | 3 met policy; 2 policy differences | 5 met policy |

The later tests verify the ZIP artifacts, not necessarily every intermediate state shown during generation. No artifact hash was recorded in the pasted original session, so exact identity between the tested final ZIP and the original runtime state is unproven. No official backend identity, token efficiency, cost, general ranking or international performance conclusion is established.

## Redaction choices

The raw conversation is kept out of the repository. Removed material includes personal project references and prior incidents; account quota readings and cumulative usage; absolute local paths and OS installation paths; precise wall-clock start/end times; and unrelated personal commentary. Generic commands, relative repository paths, elapsed duration, reported action count and synthetic HTTP statistics are retained because they explain the experiment without identifying the computer.

The technically relevant **Korean-language / Windows / CP949** context is retained at a generic level, as required to explain reproducibility. No CPU/GPU specification, hostname, device identifier, local username or directory layout is added. See [LIMITATIONS.md](LIMITATIONS.md) for encoding and international-generalization caveats. Existing public GitHub account and commit metadata are separate from transcript content; this redaction does not rewrite repository history.

## Traceability without publishing the raw conversation

The following line ranges refer only to the locally supplied text and help audit the reconstruction. They are provenance references, not additional public evidence; the raw attachment is intentionally not published.

| Report element | Local supplied-text lines |
| --- | --- |
| Medium reasoning and independent-folder plan | 164-188, 225-244 |
| Planned 100-point rubric | 190-223 |
| Terra model/reasoning metadata | 259-281 |
| Agent progress, correction and self-test claims | 284-299 |
| Duration, seven actions and visible command fragments | 301-364 |
| Original assistant interpretation and usage-accounting caution | 366-437 |

The separately supplied **Sol extract** has 276 lines: model/reasoning at 1-23, narrative and final result at 25-61, duration/action count at 62-64, and the 26 deduplicated action entries at 68-170 (repeated at 172-274). The **Luna extract** has 230 lines: metadata at 1-23, narrative/result at 25-56, duration/action count at 58-60, and 21 deduplicated actions at 62-144 (repeated at 146-228). Account usage sections and the final quota readings are excluded from the published data.

The separate files `results/session-report.json` and `results/session-actions.csv` contain only sanitized facts and evidence labels. The existing `results/reproduction.json` and six reproduction logs remain unchanged.
