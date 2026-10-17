import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.admin import router as admin_router
from app.api.v1.tenant_admin import router as tenant_admin_router
from app.api.v1.authorization import router as authorization_router
from app.api.v1.health import readiness_check, router as health_router
from app.api.v1.oidc import discovery_document, router as oidc_router
from app.api.v1.model_usage import router as model_usage_router
from app.core.config import get_settings
from app.services.maintenance import cleanup_expired_credentials_from_database
from app.services.public_registration import deliver_registration_emails
from app.services.access_log_redaction import install_uvicorn_access_log_redaction

# 先集中初始化配置，再注册版本化路由；身份认证中间件会在认证切片中加入。
install_uvicorn_access_log_redaction()
settings = get_settings()
logger = logging.getLogger(__name__)


def _database_ready_for_background_work() -> bool:
    """旧 schema 不具备当前源码依赖的表时，暂停维护/发件箱任务。"""
    try:
        readiness_check()
        return True
    except HTTPException as exc:
        if exc.status_code == 503:
            return False
        raise


async def _credential_cleanup_loop() -> None:
    """每个 API worker 启动轻量清理循环；分批 + SKIP LOCKED 保证并发安全。"""
    interval = settings.credential_cleanup_interval_seconds
    while True:
        try:
            ready = await asyncio.to_thread(_database_ready_for_background_work)
            if not ready:
                # 例如开发库还未到当前 migration head；不要对缺失的新表执行 DELETE。
                await asyncio.sleep(interval)
                continue
            counts = await asyncio.to_thread(
                cleanup_expired_credentials_from_database,
                batch_size=settings.credential_cleanup_batch_size,
            )
            if any(counts.values()):
                # 只记录表名和数量，不记录令牌、用户或任何凭证内容。
                logger.info("已回收过期认证凭证: %s", counts)
        except Exception:
            # 清理失败不影响登录/API 可用性；下一轮继续重试并保留错误堆栈供告警采集。
            logger.exception("过期认证凭证清理失败，将在下一周期重试")
        await asyncio.sleep(interval)


async def _registration_email_outbox_loop() -> None:
    """后台投递注册验证码；数据库 outbox + 锁租约支持多 worker 和崩溃后重试。"""
    while True:
        try:
            if settings.allow_public_registration and settings.smtp_host and settings.smtp_from:
                ready = await asyncio.to_thread(_database_ready_for_background_work)
                if not ready:
                    await asyncio.sleep(settings.public_registration_delivery_interval_seconds)
                    continue
            await asyncio.to_thread(deliver_registration_emails)
        except Exception:
            # 发件箱投递异常只记录服务端堆栈，不包含收件邮箱或验证码。
            logger.exception("ToC 注册验证码发件箱处理失败，将在下一周期重试")
        await asyncio.sleep(settings.public_registration_delivery_interval_seconds)


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """API 正常提供服务期间维护短期认证记录，关闭时停止后台协程。"""
    cleanup_task = asyncio.create_task(_credential_cleanup_loop(), name="iam-expired-credential-cleanup")
    registration_email_task = asyncio.create_task(
        _registration_email_outbox_loop(), name="iam-registration-email-outbox",
    )
    try:
        yield
    finally:
        cleanup_task.cancel()
        registration_email_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        try:
            await registration_email_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="统一身份与权限管理平台 API", version="0.1.0", lifespan=lifespan)
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(admin_router, prefix=settings.api_v1_prefix)
app.include_router(tenant_admin_router, prefix=settings.api_v1_prefix)
app.include_router(authorization_router, prefix=settings.api_v1_prefix)
app.include_router(oidc_router, prefix=settings.api_v1_prefix)
app.include_router(model_usage_router, prefix=settings.api_v1_prefix)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """返回服务标识和文档入口，不包含部署环境中的任何凭证信息。"""
    return {"service": settings.app_name, "docs": "/docs"}


@app.get("/.well-known/openid-configuration", include_in_schema=False)
def openid_configuration() -> dict:
    """OIDC 标准发现地址；内容只公布实际启用的授权码 + PKCE 能力。"""
    return discovery_document()
