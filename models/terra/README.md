# Terra submission

English publication documentation replacing the original Korean README. Executable source, tests, comments, UI labels and error strings are preserved byte for byte; they may contain Korean. Translation of those files would change the experimental artifact.

From this directory, run `python app.py`, then open http://127.0.0.1:8765. Stop with Ctrl+C. Python 3.11 or later and the standard library are required according to the supplied documentation. Launch only one submission at a time on this port. The application simulates timed jobs; it does not execute submitted commands. Runtime SQLite files are generated locally and excluded from publication.

Run the submitted suite with `python -m unittest discover -s tests -v`. Tests use temporary databases. Sol creates temporary data under `.test-tmp`. See the root results and methodology documents for independent reproduction and limits. This application is a local single-process demonstration without production authentication or deployment hardening.

The supplied README described creation, cancellation, retry, persistence and restart recovery. These are author claims until independently exercised. APIs include `/api/jobs`, `/api/jobs/{id}`, cancellation and retry actions, `/api/stats`, and `/api/events`. Response envelopes and attempt semantics differ between submissions; consult the preserved code.
