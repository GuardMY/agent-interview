# Changelog

## 2026-07-12

- Type: Changed
- Modules: Backend persistence and environment configuration
- Changes: Switched the default SQLAlchemy async database URL to MySQL 8.0 with the `asyncmy` driver and enabled connection health checks. Connection credentials remain external configuration.
- Verification: Tests continue to use in-memory SQLite fixtures; MySQL integration verification requires the deployment connection configuration.
- Unfinished: Run an integration test after the MySQL 8.0 connection is supplied.
