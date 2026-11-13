"""add task priority

Пример изменения схемы миграцией: у существующих задач появится priority = 2 (server_default).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14 01:48:45.814384

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('priority', sa.SmallInteger(), server_default='2', nullable=False))
    op.create_index(op.f('ix_tasks_priority'), 'tasks', ['priority'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tasks_priority'), table_name='tasks')
    op.drop_column('tasks', 'priority')
