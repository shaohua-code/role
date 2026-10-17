"""健康检查响应结构，与 API 路由的返回字段保持一致。"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """通用健康响应；具体探针决定它表示存活还是完整就绪。"""

    status: str
    service: str
