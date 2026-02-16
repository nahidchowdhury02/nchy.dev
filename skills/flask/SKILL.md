---
name: flask
description: Build, refactor, debug, and validate Flask web applications that use app factories, blueprints, templates, static assets, and service modules. Use when tasks involve adding or changing Flask routes, request/form handling, template rendering, redirects, JSON or file-backed data flows, startup configuration, or Flask-focused testing and regression checks.
---

# Flask

## Overview

Use this skill to make reliable Flask changes with a short feedback loop. Keep changes small, trace request flow end-to-end, and verify behavior with targeted smoke checks.

## Workflow

1. Inspect the app entrypoint and factory wiring.
2. Trace the impacted flow from route to service to template or response payload.
3. Implement minimal changes in the correct layer.
4. Validate syntax and runtime behavior with quick checks.
5. Summarize behavior changes and residual risks.

## Inspect Existing Structure

Use this repository map to find the right edit location quickly:

- `app.py`: process entrypoint and dev server startup.
- `app/__init__.py`: app factory, template/static folder binding, blueprint registration.
- `app/routes/main.py`: route handlers and request/response logic.
- `app/services/`: data access and persistence helpers.
- `templates/`: Jinja templates by page/feature.
- `static/`: CSS, images, and local data files.

## Edit Routes and Handlers

Follow these rules for route changes:

- Keep decorators explicit with methods where non-GET behavior is required.
- Parse and normalize query/form inputs near the start of the handler.
- Validate and coerce input before persistence.
- Keep persistence and transformation logic in `app/services/` when possible.
- Return redirect responses after successful mutations to avoid duplicate form submissions.
- Prefer `url_for(...)` for internal navigation when practical.

## Edit Templates and Static Assets

Follow these rules for frontend-facing changes:

- Keep template paths aligned with the configured template root.
- Keep naming consistent across route handlers and template files.
- Verify that every referenced static asset exists under `static/`.
- Preserve existing page structure unless the task requires redesign.

## Validate Changes

Run lightweight checks after edits:

```bash
python3 -m compileall app.py app
```

Use a quick local smoke run when behavior changes are route-visible:

```bash
FLASK_DEBUG=1 python3 app.py
```

Then exercise changed URLs and form flows in a browser.

## Deliverable Standard

Provide:
- File-level change summary.
- Behavior impact summary (request and response flow).
- Validation performed and any gaps.
