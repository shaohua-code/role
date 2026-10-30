"""一次性引导平台管理员。必须先应用数据库迁移，再运行 `py manage.py bootstrap-admin`。"""
import argparse
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.oidc_keys import public_jwks
from app.db.session import get_engine


def bootstrap_admin() -> None:
    """绿场引导：平台租户 + 管理面目录 + L1 角色 + 引导超管绑定，全部幂等。

    权限只认角色绑定（ALLOW_BOOTSTRAP_EMAIL_BYPASS 默认 false），
    因此引导必须同时完成 L1 绑定，旧「仅建 membership」的流程会产生无权限管理员。
    """
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        raise SystemExit("BOOTSTRAP_ADMIN_EMAIL 和 BOOTSTRAP_ADMIN_PASSWORD 必须设置")
    if len(settings.bootstrap_admin_password) < 16:
        raise SystemExit("引导管理员密码至少 16 位")
    from app.db.seed_greenfield import (
        seed_bootstrap_admin,
        seed_l1_role,
        seed_permissions,
        seed_platform_tenant,
    )

    with Session(get_engine()) as db:
        seed_permissions(db)
        platform_tenant = seed_platform_tenant(db)
        l1_role = seed_l1_role(db, platform_tenant)
        seed_bootstrap_admin(db, platform_tenant, l1_role)
        db.commit()
        print(f"管理员已就绪：{settings.bootstrap_admin_email.casefold()}（已绑定 L1）")


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
    parser.add_argument("command", choices=["bootstrap-admin", "ensure-oidc-key", "seed-greenfield", "seed-walkthrough", "map-data-scope-codes"])
    parser.add_argument("--demo-tenant", action="store_true", help="seed-greenfield：创建演示租户与 L3 模板")
    parser.add_argument("--demo-application", action="store_true", help="seed-greenfield：连同演示应用与 L2/L4 模板（隐含 --demo-tenant）")
    parsed = parser.parse_args()
    if parsed.command == "bootstrap-admin":
        # 写库：幂等种子（权限目录 + 平台租户 + L1）并绑定引导超管。
        bootstrap_admin()
    elif parsed.command == "ensure-oidc-key":
        # 不写业务库；校验签名密钥文件（仅开发环境允许首次生成）。
        ensure_oidc_signing_key()
    elif parsed.command == "seed-greenfield":
        # 写库：幂等绿场种子；--demo-tenant/--demo-application 追加演示数据。
        from app.db.seed_greenfield import run_seed

        run_seed(demo_tenant=parsed.demo_tenant or parsed.demo_application,
                 demo_application=parsed.demo_application)
    elif parsed.command == "seed-walkthrough":
        # §6 浏览器四级走查造数：demo 应用 + 业务码 + self 范围 + L2/L3/L4 账号（幂等）。
        from app.db.seed_greenfield import seed_walkthrough_accounts

        with Session(get_engine()) as db:
            seed_walkthrough_accounts(db)
            db.commit()
            print("四级走查账号种子完成")
    elif parsed.command == "map-data-scope-codes":
        # 把存量 RoleDataScope 映射成 *.scope.* 数据码授权；不删旧策略。
        from app.services.permission_kinds import map_role_data_scopes_to_codes

        with Session(get_engine()) as db:
            granted = map_role_data_scopes_to_codes(db)
            db.commit()
            print(f"已映射 {granted} 条数据权限码授权")
