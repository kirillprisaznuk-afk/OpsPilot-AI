# Stage 3 database compatibility and rollback

Before applying the change, the existing database reports PostgreSQL 17.11,
Debian Bookworm, migration 0002, and only plpgsql. The downloaded
`pgvector/pgvector:0.8.7-pg17-bookworm` image reports the identical PostgreSQL
17.11 Debian build and supplies pgvector 0.8.7. The image is pinned to digest
`sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d`.
The upstream [pgvector installation instructions](https://github.com/pgvector/pgvector#docker)
provide PostgreSQL-major-specific Bookworm images.

The proposed change keeps the Compose project, database name, credentials, port
and existing `opspilot-stage1_opspilot_pgdata` volume. Only the OpsPilot database
container image changes. A PostgreSQL custom-format backup was captured in the
ignored `.local-tools/stage3-before.dump` before migration (627,190 bytes).
Business fingerprint and complete analytics responses were captured separately.
The backup was restored successfully in an isolated temporary PostgreSQL container
without the accepted volume or host ports. Upgrade, downgrade to 0002 and upgrade
again passed there, preserving 2,400 purchase orders, 44 documents and the original
seed fingerprint. Only then was the existing volume used with the extension image.

Migration 0003 adds the extension and two derived retrieval tables. It does not
alter domain tables. Retrieval metadata is separate from business SQLAlchemy
metadata, so the Stage 1 fingerprint continues to describe the original business
records and corpus, not the newly added retrieval storage.

Rollback: stop only OpsPilot API, downgrade Alembic to 0002 while the pgvector
image is available, restore the Compose db image to the preserved original
`postgres@sha256:858bb5e98eed02eb8cafbcdc007f9a65d1b613972028944a8ec2133ccaf80d27`,
and recreate only db/api on the same volume with the accepted Stage 2 application.
Downgrade retains the vector extension to avoid deleting another schema's objects;
before using the old image, explicitly drop the unused extension after verifying
that no other vector objects depend on it. A backup restore is a separate recovery
operation, never an automatic overwrite of the accepted volume.

No volume deletion, prune, Docker reset or unrelated service restart is involved.
