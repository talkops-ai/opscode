# Observability Data Privacy & Secret Scrubbing Guide

Preventing secret leakage in telemetry, log artifacts, and external callback plugins.

## Privacy Guidelines

1. **`no_log: true` Enforcement**: Apply `no_log: true` on any task producing or consuming sensitive variables (tokens, API keys, private keys, passwords).
2. **Scrubbing Artifacts**: Ensure event logs generated in `/artifacts/<job_id>/job_events/` do not contain unmasked secret values.
3. **Log Storage Permissions**: Restrict permissions on `private_data_dir/artifacts/` to mode `0700` owned strictly by the runner service account.
4. **Environment Variables**: Avoid setting credentials in plain environment variables (`envvars`) when vault encryption or secure token injection is available.
