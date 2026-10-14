"""管理员审计查询的响应契约。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    """单条只读审计事件；details 必须遵守审计写入端的脱敏约束。"""

    id: str
    actor_user_id: str | None
    tenant_id: str | None
    action: str
    target_type: str
    target_id: str | None
    outcome: str
    source_ip: str | None
    details: dict[str, Any]
    created_at: datetime


class AuditSearchResponse(BaseModel):
    """服务端分页响应，total 表示当前全部过滤条件命中的事件数。"""

    items: list[AuditEventResponse]
    limit: int
    offset: int
    total: int
    has_more: bool
