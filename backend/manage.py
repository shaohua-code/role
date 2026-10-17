"""一次性引导平台管理员。必须先应用数据库迁移，再运行 `py manage.py bootstrap-admin`。"""
import argparse
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.oidc_keys import public_jwks
from app.core.security import hash_password
from app.db.session import get_engine
from app.models import Tenant, TenantMembership, User


def bootstrap_admin() -> None:
    """建立首个管理员及其租户；配置缺失、弱密钥或重复账号时明确失败。"""
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        raise SystemExit("BOOTSTRAP_ADMIN_EMAIL 和 BOOTSTRAP_ADMIN_PASSWORD 必须设置")
    if len(settings.bootstrap_admin_password) < 16:
        raise SystemExit("引导管理员密码至少 16 位")
    with Session(get_engine()) as db:
        email = settings.bootstrap_admin_email.casefold()
        user = db.scalar(select(User).where(User.email == email))
        tenant = db.scalar(select(Tenant).where(Tenant.slug == "platform"))
        if tenant is None:
            tenant = Tenant(name="平台管理租户", slug="platform")
            db.add(tenant)
            db.flush()
        if user is None:
            user = User(email=email, display_name="平台管理员", password_hash=hash_password(settings.bootstrap_admin_password))
            db.add(user)
            db.flush()
        # 重跑部署命令或调整管理员邮箱时复用平台租户，避免重复插入固定 slug。
        membership = db.scalar(select(TenantMembership.id).where(
            TenantMembership.user_id == user.id, TenantMembership.tenant_id == tenant.id))
        if membership is None:
            db.add(TenantMembership(user_id=user.id, tenant_id=tenant.id))
        db.commit()
        print(f"管理员已就绪：{email}")


def ensure_oidc_signing_key() -> None:
    """校验活动/备用 RSA 密钥；只在开发环境首次启动时生成活动密钥。"""
    settings = get_settings()
    key_path = Path(settings.oidc_signing_key_path)
    if key_path.exists():
        # 读取并解析确保挂载的文件不是空文件或无效 PEM；绝不把密钥内容打印到日志。
        loaded = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        if not isinstance(loaded, RSAPrivateKey) or loaded.key_size < 2048:
            raise SystemExit("OIDC 签名私钥必须是至少 2048 位 RSA 密钥")
    else:
        if settings.app_env != "development":
            raise SystemExit("生产环境必须通过密钥管理器挂载 OIDC_SIGNING_KEY_PATH 私钥")
        key_path.parent.mkdir(parents=True, exist_ok=True)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # O_EXCL 防止并发启动意外覆盖现存密钥；POSIX 权限限定仅容器服务账号可读。
        descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as key_file:
            key_file.write(pem)

    # 有备用 key 配置时也必须在服务启动前校验，避免 /ready 正常但令牌验签失败。
    try:
        public_jwks()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print("OIDC 签名密钥集合已就绪")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["bootstrap-admin", "ensure-oidc-key"])
    command = parser.parse_args().command
    if command == "bootstrap-admin":
        bootstrap_admin()
    elif command == "ensure-oidc-key":
        ensure_oidc_signing_key()
