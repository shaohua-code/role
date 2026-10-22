#!/usr/bin/env python3
"""幂等创建管理台邮箱注册试点：consumer 租户 + iam-dev-console-reg 应用与主题。"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from uuid import uuid4

API_BASE = os.environ.get('IAM_API_BASE', 'http://127.0.0.1:8002/api/v1')
ADMIN_EMAIL = os.environ.get('IAM_ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD = os.environ.get('IAM_ADMIN_PASSWORD', '')
CLIENT_ID = os.environ.get('IAM_CONSOLE_REGISTRATION_CLIENT_ID', 'iam-dev-console-reg')
TERMS_URL = os.environ.get('IAM_DEV_TERMS_URL', 'https://example.com/terms')
PRIVACY_URL = os.environ.get('IAM_DEV_PRIVACY_URL', 'https://example.com/privacy')


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict | list]:
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        f'{API_BASE}{path}',
        data=data,
        method=method,
        headers={'Content-Type': 'application/json', **({'Authorization': f'Bearer {token}'} if token else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = resp.read()
            return resp.status, json.loads(payload) if payload else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'{method} {path} -> HTTP {error.code}: {detail}') from error


def main() -> int:
    if not ADMIN_PASSWORD:
        print('请设置环境变量 IAM_ADMIN_PASSWORD（勿写入仓库）', file=sys.stderr)
        return 1
    _, login = request('POST', '/auth/login', {'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD})
    token = login['access_token']

    tenants = request('GET', '/admin/tenants', token=token)[1]
    tenant = next((item for item in tenants if item.get('kind') == 'consumer' and item.get('status') == 'active'), None)
    if tenant is None:
        slug = f'dev-console-reg-{uuid4().hex[:8]}'
        _, tenant = request('POST', '/admin/tenants', {'name': '控制台注册试点', 'slug': slug, 'kind': 'consumer'}, token=token)
        print('created_tenant', tenant['id'])

    apps = request('GET', f'/admin/applications?tenant_id={tenant["id"]}', token=token)[1]
    app = next((item for item in apps if item.get('client_id') == CLIENT_ID), None)
    if app is None:
        _, app = request('POST', '/admin/applications', {
            'tenant_id': tenant['id'],
            'name': '控制台邮箱注册',
            'client_id': CLIENT_ID,
            'description': '本地开发：管理台登录页邮箱 OTP 注册试点',
            'redirect_uris': ['http://localhost:5175/'],
            'post_logout_redirect_uris': [],
        }, token=token)
        print('created_application', app['id'])

    roles = request('GET', f'/admin/roles?tenant_id={tenant["id"]}', token=token)[1]
    role = next((item for item in roles if item.get('application_id') == app['id'] and item.get('key') == 'console.member'), None)
    if role is None:
        _, role = request('POST', '/admin/roles', {
            'tenant_id': tenant['id'],
            'application_id': app['id'],
            'key': 'console.member',
            'name': '控制台注册用户',
        }, token=token)
        print('created_role', role['id'])

    theme_config = {
        'show_register': True,
        'show_forgot_password': True,
        'terms_url': TERMS_URL,
        'privacy_url': PRIVACY_URL,
        'title': '邮箱注册试点',
        'welcome_text': '使用邮箱验证码创建账号',
    }
    request('PUT', f'/admin/themes/{app["id"]}?publish=true', {'config': theme_config}, token=token)
    print('published_theme', app['id'])

    request('PATCH', f'/admin/applications/{app["id"]}', {
        'registration_policy': 'open',
        'registration_role_id': role['id'],
        'registration_terms_version': 'dev-terms-v1',
        'registration_privacy_version': 'dev-privacy-v1',
    }, token=token)
    print('done_client_id', CLIENT_ID)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
