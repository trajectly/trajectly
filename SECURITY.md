# Security Policy

## Supported Versions

Security updates are currently provided for:

| Version | Supported |
| --- | --- |
| `0.3.x` | Yes |
| `<0.3.0` | No |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately to:

- `founders@trajectly.dev`

Please include:

- a clear description of the issue
- affected version(s)
- reproduction steps or proof of concept
- potential impact

Do not open public GitHub issues for undisclosed vulnerabilities.

## Response Timeline

Target response timelines:

- initial acknowledgment: within 72 hours
- triage update: within 7 days
- fix plan or mitigation guidance: as soon as practical after triage

## Disclosure Process

1. Report is received and acknowledged privately.
2. Maintainers reproduce and assess severity.
3. Fix is developed and validated.
4. Patched release and advisory are published.
5. Public disclosure occurs after a fix or mitigation is available.

## Scope Notes

This project includes deterministic replay and fixture artifacts. Please avoid including sensitive production data in
test traces and artifacts. Use redaction settings in `.agent.yaml` where needed.
