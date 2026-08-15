"""add content hash to agent versions

content_hash can't get a single server_default: it has to be computed per row from
that row's own model/system_prompt/tool_schema_hash/config, and a shared default
would violate the unique constraint the moment there's more than one existing row.
Add nullable, backfill each row with the same hash function the app uses, then
tighten to NOT NULL and unique - confirmed necessary by actually inserting a row and
watching the naive "add NOT NULL column" version fail against it.

Revision ID: 9a1faddf3548
Revises: bd25f8b625ce
Create Date: 2026-08-14 18:14:39.105267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.versioning import compute_agent_version_content_hash

# revision identifiers, used by Alembic.
revision: str = '9a1faddf3548'
down_revision: Union[str, Sequence[str], None] = 'bd25f8b625ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


agent_versions = sa.table(
    "agent_versions",
    sa.column("id", sa.Uuid()),
    sa.column("model", sa.String()),
    sa.column("system_prompt", sa.String()),
    sa.column("tool_schema_hash", sa.String()),
    sa.column("config", sa.JSON()),
    sa.column("content_hash", sa.String()),
)


def upgrade() -> None:
    op.add_column("agent_versions", sa.Column("content_hash", sa.String(), nullable=True))

    connection = op.get_bind()
    existing_rows = connection.execute(
        sa.select(
            agent_versions.c.id,
            agent_versions.c.model,
            agent_versions.c.system_prompt,
            agent_versions.c.tool_schema_hash,
            agent_versions.c.config,
        )
    ).fetchall()
    for row in existing_rows:
        content_hash = compute_agent_version_content_hash(row.model, row.system_prompt, row.tool_schema_hash, row.config)
        connection.execute(
            agent_versions.update().where(agent_versions.c.id == row.id).values(content_hash=content_hash)
        )

    op.alter_column("agent_versions", "content_hash", nullable=False)
    op.create_unique_constraint("uq_agent_versions_content_hash", "agent_versions", ["content_hash"])


def downgrade() -> None:
    op.drop_constraint("uq_agent_versions_content_hash", "agent_versions", type_="unique")
    op.drop_column("agent_versions", "content_hash")
