# Security

[Report vulnerabilities privately](https://github.com/enesdemirag/google-health-mcp/security/advisories/new). Include the affected version, impact and steps to reproduce with synthetic data. Do not include health records, working tokens or client secrets. Do not report vulnerabilities that could expose user data in public issues.

Operators should keep dependencies updated, use HTTPS, restrict callback hosts, protect keys and encrypted backups, and rate-limit authorization endpoints. See the [deployment guide](docs/deployment.md). Repository tests do not replace Google's verification or security assessment.

Run one application process on one host. Multiple workers or hosts need shared transactional OAuth storage and concurrency testing.
