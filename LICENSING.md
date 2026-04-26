# Creator Spark Registry — Licensing

Creator Spark Registry uses a **dual-license model**: open source for the community,
commercial for enterprise use.

---

## Open Source Core — AGPLv3

Creator Spark Registry is licensed under the
[GNU Affero General Public License v3.0](LICENSES/AGPLv3.txt) (AGPLv3).

This covers:
- Creator profile management
- Engagement tracking and history
- Tag-based organization
- Import/export functionality
**AGPLv3 in plain English:**
- Free to use, modify, and distribute
- If you modify and run it as a service (SaaS), you must publish your modifications
- If you distribute it as part of a product, that product must also be AGPLv3
- Protects against cloud providers silently forking and offering as managed service

---

## Commercial License — Enterprise

A commercial license is required if you:

1. Use Creator Spark Registry commercially with **>50 users** and **>$5M revenue/year**
2. Distribute Creator Spark Registry inside a product **without** releasing your source under AGPLv3
3. Offer Creator Spark Registry as a **hosted/managed service** without releasing modifications

A commercial license grants:
- Usage rights without AGPLv3 obligations
- Priority support and SLA options

See [LICENSES/COMMERCIAL.txt](LICENSES/COMMERCIAL.txt) for full terms.
Contact: erling@rognsund.no or open an issue.

---

## What Is Free vs. Commercial

| Feature | AGPLv3 (Free) | Commercial |
|---------|:---:|:---:|
| Creator profile management | ✅ | ✅ |\n| Engagement tracking and history | ✅ | ✅ |\n| Tag-based organization | ✅ | ✅ |\n| Import/export functionality | ✅ | ✅ |\n| **Multi-user team workspaces** | — | ✅ |\n| **Advanced analytics and reporting** | — | ✅ |\n| **API integrations (YouTube, Twitch, etc.)** | — | ✅ |\n| **SSO / SAML integration** | — | ✅ |\n
---

## Why AGPLv3?

We chose AGPLv3 over MIT/Apache 2.0 deliberately:

**The SaaS loophole:** MIT and Apache 2.0 allow cloud providers to offer Creator Spark Registry
as a managed service, fork it, add proprietary features, and never contribute back.
AGPLv3 closes this loophole — if you run it as a service, your modifications
must be open.

**We commit to the core staying open:** The core will remain AGPLv3 forever.
Enterprise features that we build on top may be commercial,
but the foundation will not be.

---

## Contributor License Agreement (CLA)

Contributors must sign a Contributor License Agreement (CLA).
This allows us to offer the commercial license while accepting community contributions.

The CLA grants us the right to:
- Include your contribution in the AGPLv3 release
- Include your contribution in commercial releases

It does NOT transfer copyright ownership. You retain copyright over your contributions.

---

## Questions?

Open an issue: https://github.com/egkristi/creator-spark-registry/issues
Email: erling@rognsund.no
