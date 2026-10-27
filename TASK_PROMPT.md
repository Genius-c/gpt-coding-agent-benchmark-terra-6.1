# Common Coding Task: English Translation

> **Provenance and language warning:** This is an English translation of the Korean coding-task prompt recovered from the assistant's copy-control text in the contributor's conversation. It is **not** an English prompt that the original agents necessarily received. The actual prompts are hidden in the Orbit session extracts, so their byte-for-byte identity and whether the user submitted the copied text unchanged cannot be independently established. This translation preserves the visible task requirements for review; an English rerun would be a different experiment.

You are an independent software development agent. Build a runnable application in the currently open working directory.

## Objective

Implement an asynchronous job-queue server and a live web dashboard using only the Python standard library and HTML/CSS/JavaScript.

## Runtime constraints

- Support Python 3.11+ on Windows.
- Use no external packages or CDNs.
- Persist data in SQLite.
- Start the server with `python app.py`.
- Serve the dashboard at `http://127.0.0.1:8765`.
- Do not read, change or delete files outside the current working directory.
- Simulate jobs; never run external commands.

## Feature 1: Job queue

- Create a job with a title, `duration_ms` (100–5,000), and `fail_first_attempt` (boolean).
- Support states `queued`, `running`, `completed`, `failed` and `cancelled`.
- Run no more than two jobs concurrently; queue the remainder in FIFO order.
- Simulate duration with sleeping while responding promptly to cancellation.
- A job with `fail_first_attempt=true` must fail on its first actual execution and succeed when retried.
- Allow retries of failed and cancelled jobs; reject retries of completed jobs.
- Preserve the job ID across retries and increment the `attempt` counter.
- Store jobs, state, attempt count, creation time, start time and end time.

## Feature 2: Concurrency and state integrity

- Enforce the two-job concurrency limit even under simultaneous requests.
- Handle duplicate cancellation safely.
- Prevent concurrent retry requests from executing the same job twice.
- After a running job is cancelled and promptly retried, an older worker must not overwrite the new execution's state.
- Keep state transitions and corresponding event records transactionally consistent in the database.
- Return HTTP 409 for prohibited state transitions.
- On server restart, recover previously running jobs as queued and execute them again.

## Feature 3: HTTP API

- `POST /api/jobs`: create a job.
- `GET /api/jobs`: list jobs with an optional state filter.
- `GET /api/jobs/{id}`: retrieve details.
- `POST /api/jobs/{id}/cancel`: cancel.
- `POST /api/jobs/{id}/retry`: retry.
- `GET /api/stats`: counts per state and number currently running.
- `GET /api/events`: state-transition history.
- Use JSON for every API.
- Return 400 for invalid input, 404 for missing jobs, and 409 for state conflicts.

## Feature 4: Web dashboard

- Use no external framework.
- Include job creation, state statistics, job list and cancel/retry buttons.
- Support state filtering.
- Refresh automatically once per second without reloading the entire page.
- Display pending activity and API errors to the user.
- Maintain usable layouts on desktop and mobile widths.
- Prevent user-entered text from executing as HTML or JavaScript.
- Deliver a visually coherent, usable interface.

## Feature 5: Automated tests

Use Python `unittest` to verify all of the following:

1. Normal job creation and completion.
2. Invalid input and HTTP error codes.
3. Two-job execution limit when at least ten jobs are created concurrently.
4. Cancellation of a running job.
5. First-execution failure followed by successful retry.
6. Protection against concurrent duplicate retries of one job.
7. Protection against stale-worker overwrites after cancel-and-retry.
8. Recovery of unfinished work after a server restart.
9. SQLite persistence and state-change history.

Every test must use its own temporary database and leave no server or worker threads running. The suite must run with `python -m unittest discover -s tests -v`.

## Development instructions

- Write and execute the actual application, not only a design.
- Document startup and test instructions in `README.md`.
- Choose an appropriate file and module layout.
- Do not use superficial workarounds or tests that falsely report success.
- Diagnose errors, fix the cause and rerun the tests.
- Do not add features outside the requested scope.
- Disclose omitted requirements in the final report.

## Final report

1. Implemented features.
2. Created file tree.
3. Tests actually executed, including pass/fail counts.
4. Errors found and fixed.
5. Missing features and known risks.
6. Startup instructions.

Begin without asking clarifying questions.

---

## Evidentiary boundary

The text above is **translated documentation**, not a verified transcript of a model input. The source instruction was written in Korean, and the experiment ran in a Korean-language Windows environment. A direct English-language replication is not equivalent. See [Methodology](docs/METHODOLOGY.md) and [Language/locale limitations](docs/LIMITATIONS.md).
