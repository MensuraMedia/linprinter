---
paths:
  - "**/*"
---

# Universal Security Rules

1. NEVER log, commit, or store secrets (.env, API keys, tokens, passwords)
2. NEVER commit .env files — always .gitignore them
3. Validate all external input at system boundaries
4. Use parameterized queries for database access (no string concatenation)
5. Sanitize output to prevent XSS
6. Follow OWASP Top 10 guidelines
7. Review dependencies for known vulnerabilities before adding
8. Use least-privilege principles for file/network access
