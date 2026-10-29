"""SQLAlchemy 元数据基类，Alembic 会从这里读取所有业务模型。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 实体共用同一 MetaData，便于集中生成和检查迁移。"""

