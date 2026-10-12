"""Change balance columns from Float to Numeric for precision

Revision ID: change_balance_numeric
Revises: f7f83c87eca4
Create Date: 2024-10-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'change_balance_numeric'
down_revision = 'f7f83c87eca4'
branch_labels = None
depends_on = None


def upgrade():
    # Supplier balance changes
    op.alter_column('suppliers', 'opening_balance',
               existing_type=mysql.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=True)
    op.alter_column('suppliers', 'current_balance',
               existing_type=mysql.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=True)
    
    # Customer balance changes
    op.alter_column('customers', 'opening_balance',
               existing_type=mysql.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=True)
    op.alter_column('customers', 'current_balance',
               existing_type=mysql.FLOAT(),
               type_=sa.Numeric(precision=12, scale=2),
               existing_nullable=True)


def downgrade():
    # Revert Supplier balance changes
    op.alter_column('suppliers', 'opening_balance',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=mysql.FLOAT(),
               existing_nullable=True)
    op.alter_column('suppliers', 'current_balance',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=mysql.FLOAT(),
               existing_nullable=True)
    
    # Revert Customer balance changes
    op.alter_column('customers', 'opening_balance',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=mysql.FLOAT(),
               existing_nullable=True)
    op.alter_column('customers', 'current_balance',
               existing_type=sa.Numeric(precision=12, scale=2),
               type_=mysql.FLOAT(),
               existing_nullable=True)
