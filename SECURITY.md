# Security policy

## Supported versions

Security reports are assessed against the current `main` branch.
PyFlowMap 1.0.0 is the current documented version. The project does not
promise security maintenance for older versions or historical commits.

## Reporting a vulnerability

**Do not disclose vulnerabilities, credentials, private code, or exploit
details in a public issue, pull request, or discussion.**

If the repository offers GitHub **Report a vulnerability** under its
Security tab, use that private reporting route. Otherwise, contact the
maintainer privately via the
[GitHub maintainer profile](https://github.com/SergioGilBorras)
to arrange a confidential reporting channel.

Include the affected version, a minimal reproduction using synthetic
data, potential impact, and relevant environment information. Never send
private Git backups or unrelated source archives to a public channel.

## Responsible handling

The maintainer will review reports, coordinate any fixes, and publish
appropriate advisories when needed. Response and remediation timelines
are not guaranteed.

PyFlowMap performs static source analysis; analyzed code should not be
executed by the analyzer. Optional semantic labeling may transmit
selected snippets only with explicit opt-in. Report any violation of
these boundaries privately.

## Historical repository exposure

The public `main` branch was rebuilt from a clean root commit. Some
older Git objects might still be accessible through GitHub's retained
references or caches. Their deletion is a separate remediation process;
**rewriting a branch is not proof of full removal**. Do not reproduce
sensitive code in public issue reports.
