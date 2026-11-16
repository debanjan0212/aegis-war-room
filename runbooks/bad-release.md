# Errors right after a release

Use when a service starts failing within minutes of a new version of that same service going out.

1. Confirm the timing: the release went out shortly before the errors started.
2. Confirm the errors come from inside the service (panics, 500s) and not from something it calls.
3. Roll the service back to the previous version. Do not try to fix forward during the incident.
4. A rollback changes what customers run, so a human must approve and perform it.
5. After the rollback, error rate should drop below 5% within a few minutes.
