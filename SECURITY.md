# Security Policy

## Supported Versions

Only the latest version on the `main` branch is supported.

## Reporting a Vulnerability

Please report vulnerabilities via GitHub's private vulnerability reporting
("Report a vulnerability" under the Security tab) or by opening an issue for
non-sensitive findings. You can expect an initial response within 14 days.

## Scope

This project reads public open data and publishes a static file. It handles no
user data, credentials, or personal information. The GitHub Actions workflow
uses OIDC with minimal permissions (`contents: read`, `pages: write`,
`id-token: write`) and no long-lived secrets.
