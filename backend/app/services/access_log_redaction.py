"""访问日志脱敏工具。

OIDC 登出等协议允许在查询参数中携带 bearer 类凭证。访问日志只记录路径，
丢弃整个查询串，避免未来新增敏感参数时漏进 allow/deny 清单。
"""

import logging


def redact_request_target(request_target: str) -> str:
    """保留请求路径并统一隐藏查询参数。"""
    path, separator, _query = request_target.partition("?")
    return f"{path}?[QUERY_REDACTED]" if separator else path


class UvicornAccessLogRedactionFilter(logging.Filter):
    """脱敏 Uvicorn 标准 access log 中的 request-target 参数。"""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        # Uvicorn AccessFormatter 的第 3 个参数是包含 query string 的请求目标。
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], redact_request_target(args[2]), *args[3:])
        return True


def install_uvicorn_access_log_redaction() -> None:
    """幂等安装脱敏过滤器，保留状态码、耗时等访问日志信息。"""
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, UvicornAccessLogRedactionFilter) for item in access_logger.filters):
        access_logger.addFilter(UvicornAccessLogRedactionFilter())
