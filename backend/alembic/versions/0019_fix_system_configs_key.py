"""fix malformed system_configs key column

0004 用 sa.Column("`key`", ...) 建表，MySQL/MariaDB 把反引号当成转义，
结果真实列名是带反引号的 ```key```，而 ORM 模型期望的是 key ——
读取 system_configs 时报 1054 Unknown column 'system_configs.key'，
AI 对话在预加载 LLM 配置时直接 500。

实现说明：列名里本身含反引号，用 Python 拼标识符很容易把反引号数量算错，
所以这里直接用 information_schema 的原始列名 + 预处理语句，让数据库自己转义。

本迁移幂等：列名已经是 key 时什么都不做。

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NORMAL_COLUMNS = "'value','description','updated_by','created_at','updated_at'"


def upgrade() -> None:
    # 已经是正常结构就跳过
    op.execute(
        f"""
        SET @has_key := (
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'system_configs'
              AND column_name = 'key'
        )
        """
    )
    op.execute(
        f"""
        SET @bad := (
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'system_configs'
              AND column_name NOT IN ({_NORMAL_COLUMNS}, 'key')
            LIMIT 1
        )
        """
    )
    # 只在这两件事同时成立时改名：没有 key 列，且存在一个畸形列
    op.execute(
        """
        SET @sql := IF(
            @has_key = 0 AND @bad IS NOT NULL,
            CONCAT(
                'ALTER TABLE system_configs CHANGE COLUMN `',
                REPLACE(@bad, '`', '``'),
                '` `key` VARCHAR(64) NOT NULL COMMENT ''配置键'''
            ),
            'DO 0'
        )
        """
    )
    op.execute("PREPARE stmt FROM @sql")
    op.execute("EXECUTE stmt")
    op.execute("DEALLOCATE PREPARE stmt")


def downgrade() -> None:
    # 不回滚：畸形列名本身是 bug，降级只会把问题带回来。
    pass
