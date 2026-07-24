# ADR 0001: Django monolith and SQLite

- Status: Accepted
- Date: 2026-07-23
- Scope: M1 local single-instance deployment

## Context

Grounded Growth must validate a guided personal-development experience on a
self-hosted machine. Its initial workload is one local instance, a small
number of users, read-heavy canonical curriculum data, and low-volume
assessment/practice writes. The product does not yet need independently scaled
services, background jobs, or a distributed data layer.

The previous suggested Next.js architecture introduced a JavaScript server,
frontend/backend boundaries, a second package ecosystem, and more deployment
surface than this milestone needs.

## Decision

Use a server-rendered Django monolith:

- supported stable Django 6.0.x on Python 3.13 in the container;
- Django templates, local CSS, and minimal local JavaScript;
- Django's built-in authentication, sessions, and CSRF protection;
- Gunicorn bound to `0.0.0.0:8000`;
- one Docker Compose application service;
- SQLite through the Django ORM at
  `/data/grounded_growth.sqlite3`;
- a named volume mounted at `/data`;
- a 20-second SQLite busy timeout and WAL mode where the filesystem supports
  it;
- migrations, an idempotent seed command, and an online-backup management
  command.

No reverse proxy is part of M1. Direct local-network HTTP is the supported
deployment. Caddy or another proxy may be added later for HTTPS or remote
access; secure cookies are already environment-configurable.

## Why SQLite is appropriate here

SQLite keeps installation to one service and one durable volume, provides
transactional storage and online backups, and is sufficient for the expected
single-instance write rate. WAL permits readers while a writer commits, while
the busy timeout handles brief lock contention without hiding sustained
concurrency problems.

This decision would be revisited if measured usage shows multiple application
replicas, sustained concurrent writes, remote database administration, or
availability requirements that a single database file cannot meet.

## Portability boundary

Application code uses Django models, constraints, transactions, and ordinary
querysets. It avoids database-specific application SQL. The SQLite PRAGMAs and
backup command are isolated operational adapters. A later PostgreSQL migration
therefore changes deployment and those adapters, not canonical IDs or domain
logic.

## Consequences

Positive:

- shortest reproducible self-hosted installation;
- one language and one runtime service;
- authentication, migrations, templates, and ORM share one transaction
  boundary;
- backup and restore are understandable to a self-hoster;
- no Node.js server is deployed.

Constraints:

- one application instance owns the SQLite file;
- long transactions and high write concurrency must be avoided;
- HTTPS requires a later reverse proxy;
- browser-side assessment scoring remains JavaScript until its reference
  behavior is integrated and locked by golden tests.
