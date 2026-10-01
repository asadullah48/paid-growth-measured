# Contributing

Build one focused improvement at a time. Document the behavior and its boundaries before changing the implementation.

## Workflow

1. Read the specification and permissions matrix.
2. Propose a clear change with acceptance criteria.
3. Keep every query and reference within agency/client scope.
4. Preserve provenance, expiry checks, and approval transitions.
5. Add meaningful validation for affected workflows and failure paths.
6. Run backend tests, frontend type checks, and the production build.
7. Describe the change, checks performed, and remaining limitations.

Never commit credentials, customer data, private context packs, or database snapshots. Use synthetic fixtures. Do not add auto-publishing, external messages, paid resources, or model-provider calls without explicit project authorization.

Contributions are licensed under MIT. Be respectful, constructive, and precise in reviews.
