"""角色作用域隔离实测脚本：模拟「应用角色访问其他应用」，验证前后端拦截与放行边界。

场景：给 crud-demo@example.com 临时绑上 CRUD Demo 应用的 app.admin（管理台 L2），
跑完整攻击矩阵后立即解绑恢复原状（try/finally 保证，零残留）。

跨应用目标动态选取：优先复用平台目录中任一非 CRUD Demo 的既有应用；
若目录中只有 CRUD Demo（如绿场重置后），脚本会临时创建 isolation-target
探测应用并在 finally 中删除，保证零残留。

判定口径（防枚举设计）：
- 跨应用资源型访问返回 **404**（无权应用按「不存在」处理，杜绝应用 ID 枚举）——强于 403 的隔离；
- **403** 用于「资源可见但操作被拒」（如无 rbac.role.manage 访问平台角色目录）；
- **200** 对照：本人应用的正常访问必须放行（隔离不误伤）；
- 前端路由守卫与菜单读 `/auth/me/capabilities` 同一数据源：目标应用无条目即不可达，
  脚本据此验证前端拦截的充分条件（UI 级深链走查可用浏览器另行复验）。

用法（api 容器内）：
    docker exec -e DEMO_USER_PASSWORD=<crud-demo 密码> -i iam-platform-api-1 python -B - < scripts/verify_role_isolation.py
凭据来源：BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD 来自容器环境变量；
DEMO_USER_PASSWORD 由调用方注入，本脚本不落任何明文密码。
副作用：测试期间临时绑定 app.admin 并 bump 该用户 auth_version（业务系统旧会话失效），
结束后解绑恢复；临时创建的探测应用会被删除；除此之外零数据变更。
"""

import json
import os
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8000/api/v1'
ADMIN_EMAIL = os.environ.get('BOOTSTRAP_ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD', '')
DEMO_EMAIL = 'crud-demo@example.com'
DEMO_PASSWORD = os.environ.get('DEMO_USER_PASSWORD', '')
PROBE_CLIENT_ID = 'isolation-target'
MISSING = []


def request(method, path, token=None, payload=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        body = error.read().decode('utf-8', errors='replace')
        try:
            return error.code, json.loads(body)
        except json.JSONDecodeError:
            return error.code, {'detail': body[:160]}


def login(email, password):
    status, body = request('POST', '/auth/login', payload={'email': email, 'password': password})
    if status != 200:
        MISSING.append(f'{email} 登录失败 HTTP {status}：{body.get("detail", "")}')
        return None
    return body.get('access_token')


if not ADMIN_PASSWORD:
    MISSING.append('容器环境变量 BOOTSTRAP_ADMIN_PASSWORD 缺失')
if not DEMO_PASSWORD:
    MISSING.append('执行时未注入 DEMO_USER_PASSWORD（docker exec -e）')

admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD) if ADMIN_PASSWORD else None

# ---- 前置：定位 CRUD Demo 与跨应用隔离目标 ----
crud_app_id = target_app_id = target_label = app_admin_role_id = demo_user_id = None
probe_app_created = False
if admin_token:
    status, apps = request('GET', '/admin/applications', token=admin_token)
    if status == 200 and isinstance(apps, list):
        for app in apps:
            if app.get('client_id') == 'crud-demo':
                crud_app_id = app['id']
            elif target_app_id is None:
                # 动态选取任一非 CRUD Demo 应用作为跨应用攻击目标
                target_app_id = app['id']
                target_label = app.get('client_id') or app.get('name') or target_app_id[:8]
    if crud_app_id is None:
        MISSING.append('平台应用目录中未找到 crud-demo')
    if target_app_id is None and crud_app_id:
        # 绿场重置后目录可能只有 CRUD Demo：临时创建探测应用作为隔离目标，finally 中删除
        tenant_id = next((app.get('tenant_id') for app in (apps or []) if app.get('client_id') == 'crud-demo'), None)
        status, body = request('POST', '/admin/applications', token=admin_token, payload={
            'tenant_id': tenant_id,
            'name': '隔离探测目标（临时）',
            'client_id': PROBE_CLIENT_ID,
            'description': 'verify_role_isolation 临时创建，跑完即删',
            'redirect_uris': ['https://localhost/callback'],
            'post_logout_redirect_uris': ['https://localhost/logout'],
        })
        if status in (200, 201):
            target_app_id = body['id']
            target_label = PROBE_CLIENT_ID
            probe_app_created = True
            print(f'[探测] 已临时创建目标应用 {PROBE_CLIENT_ID}（{target_app_id[:8]}…），结束后删除')
        else:
            MISSING.append(f'临时创建隔离目标应用失败 HTTP {status}：{body}')
    if crud_app_id:
        status, roles = request('GET', f'/tenant-admin/applications/{crud_app_id}/roles', token=admin_token)
        if status == 200 and isinstance(roles, list):
            app_admin_role_id = next((r['id'] for r in roles if r.get('key') == 'app.admin'), None)
        if not app_admin_role_id:
            MISSING.append('CRUD Demo 应用下未找到 app.admin 角色')

        # crud-demo 用户的 user_id（经本应用成员列表检索）
        status, members = request(
            'GET', f'/tenant-admin/applications/{crud_app_id}/members?q={DEMO_EMAIL}', token=admin_token)
        if status == 200:
            items = members.get('items') or []
            demo_user_id = next((item['user_id'] for item in items if item.get('email') == DEMO_EMAIL), None)
        if not demo_user_id:
            MISSING.append(f'成员列表未定位到 {DEMO_EMAIL}')

# ---- 临时绑定 app.admin（try/finally 保证解绑，held_bindings 跟踪全部临时绑定） ----
results = []
held_bindings = []

def check(label, expected, actual, note=''):
    ok = actual == expected
    results.append((label, expected, actual, ok, note))
    return ok

if admin_token and app_admin_role_id and not MISSING:
    status, body = request(
        'PUT', f'/tenant-admin/applications/{crud_app_id}/role-bindings', token=admin_token,
        payload={'email': DEMO_EMAIL, 'role_id': app_admin_role_id})
    bound = status in (200, 201, 204)
    if bound:
        held_bindings.append(app_admin_role_id)
    else:
        # 可能已绑定过（脚本重复执行）：核对成员角色后再决定
        status_members, members = request(
            'GET', f'/tenant-admin/applications/{crud_app_id}/members?q={DEMO_EMAIL}', token=admin_token)
        items = (members or {}).get('items') or []
        held = any(any(r['id'] == app_admin_role_id for r in item.get('roles') or [])
                   for item in items if item.get('email') == DEMO_EMAIL)
        if held:
            bound = True
        else:
            MISSING.append(f'临时绑定 app.admin 失败 HTTP {status}：{body}')

try:
    if bound:
        # 绑定会 bump auth_version：旧令牌全部失效，必须重新登录
        demo_token = login(DEMO_EMAIL, DEMO_PASSWORD)
        if not demo_token:
            MISSING.append('提权后重新登录失败，无法继续攻击矩阵')

        # 1) 前端守卫数据源：capabilities 只含本人应用
        if demo_token:
            status, caps = request('GET', '/auth/me/capabilities', token=demo_token)
            reachable = [str(entry.get('application_id'))
                         for tenant_entry in (caps.get('tenants') or [])
                         for entry in (tenant_entry.get('applications') or [])]
            leak = target_app_id in reachable
            has_own = crud_app_id in reachable
            results.append((
                '前端守卫数据源：capabilities 含本人应用且不含目标应用',
                f'含 crud-demo，不含 {target_label}',
                f'可见 {len(reachable)} 个应用' + (f'（含 {target_label}！）' if leak else ''),
                has_own and not leak,
                '路由守卫与菜单读同一数据：目标应用无条目即不可达',
            ))

        # 2) 后端拦截矩阵
        status, _ = request('GET', f'/tenant-admin/applications/{target_app_id}/roles', token=demo_token)
        check(f'跨应用读角色（{target_label}）', 404, status, '防枚举：无权应用一律 404「应用不存在」')

        status, _ = request('POST', f'/tenant-admin/applications/{target_app_id}/roles',
                            token=demo_token, payload={'key': 'isolation-probe', 'name': '隔离探测'})
        check(f'跨应用建角色（{target_label}）', 404, status, '写操作同样在判权层被 404 拦截')

        status, _ = request('GET', f'/tenant-admin/applications/{target_app_id}/members', token=demo_token)
        check(f'跨应用读成员（{target_label}）', 404, status, '成员列表同样按应用判权')

        # 平台角色目录：L2/L3 可读管理范围内租户的角色目录（rbac.role.read 设计口径，非 L1 强制范围过滤）
        status, roles = request('GET', '/admin/roles', token=demo_token)
        status_app = None
        for app in request('GET', '/admin/applications', token=admin_token)[1] or []:
            if app.get('client_id') == 'crud-demo':
                status_app = app.get('tenant_id')
        foreign = [r['tenant_id'] for r in (roles or []) if r.get('tenant_id') != status_app] if status == 200 else []
        results.append((
            '平台角色目录 /admin/roles（L2 可读 + 租户范围过滤）',
            f'200 且无租户外角色（范围={status_app and status_app[:8]}…）',
            f'{status}，租户外角色 {len(foreign)} 条',
            status == 200 and not foreign,
            '设计口径：rbac.role.read 允许 L2/L3 读管理范围内租户的目录，跨租户被范围过滤拦截',
        ))

        # 对照正路径：本人应用必须放行（隔离不误伤）
        status, _ = request('GET', f'/tenant-admin/applications/{crud_app_id}/roles', token=demo_token)
        check('对照：本应用（CRUD Demo）读角色', 200, status, 'L2 钉住本应用：正常访问放行')

    # ---- L4 维度：零管理码角色访问平台角色目录必须 403 ----
    # 先解绑 app.admin（否则 L2 门禁仍生效），再临时绑 app.member
    if held_bindings and app_admin_role_id in held_bindings:
        status, _ = request(
            'DELETE', f'/tenant-admin/applications/{crud_app_id}/members/{demo_user_id}/roles/{app_admin_role_id}',
            token=admin_token)
        if status in (200, 204):
            held_bindings.remove(app_admin_role_id)
            print('[恢复] 已解绑 app.admin（为 L4 检查让位）')
    if admin_token and crud_app_id:
        status, roles = request('GET', f'/tenant-admin/applications/{crud_app_id}/roles', token=admin_token)
        member_role_id = next((r['id'] for r in (roles or []) if r.get('key') == 'app.member'), None) \
            if status == 200 else None
        if member_role_id:
            status, _ = request(
                'PUT', f'/tenant-admin/applications/{crud_app_id}/role-bindings', token=admin_token,
                payload={'email': DEMO_EMAIL, 'role_id': member_role_id})
            if status in (200, 201, 204):
                held_bindings.append(member_role_id)
                demo_token = login(DEMO_EMAIL, DEMO_PASSWORD)
                if demo_token:
                    status, _ = request('GET', '/admin/roles', token=demo_token)
                    check('平台角色目录 /admin/roles（L4 零管理码）', 403, status,
                          'ensure_roles 仅认 L2/L3：app.member 无管理角色 → 403')
            else:
                MISSING.append(f'临时绑定 app.member 失败 HTTP {status}，跳过 L4 检查')
        else:
            MISSING.append('CRUD Demo 应用下未找到 app.member 角色，跳过 L4 检查')
finally:
    # 恢复原状：解绑全部临时角色（app.admin + app.member）
    for role_id in held_bindings:
        status, _ = request(
            'DELETE', f'/tenant-admin/applications/{crud_app_id}/members/{demo_user_id}/roles/{role_id}',
            token=admin_token)
        if status not in (200, 204):
            print(f'[警告] 解绑角色 {role_id} 失败 HTTP {status}——请人工在 CRUD Demo 应用移除 {DEMO_EMAIL} 的该绑定')
        else:
            print(f'[恢复] 已解绑临时角色 {role_id[:8]}…，数据还原')
    # 清理临时创建的探测应用
    if probe_app_created and target_app_id:
        status, _ = request('DELETE', f'/admin/applications/{target_app_id}', token=admin_token)
        print(f'[恢复] 临时探测应用删除 HTTP {status}' if status in (200, 204)
              else f'[警告] 临时探测应用 {target_app_id} 删除失败 HTTP {status}——请人工删除 {PROBE_CLIENT_ID}')

# ---- 汇总 ----
print('=' * 86)
print('角色作用域隔离实测（L2 应用管理员 → 其他应用 / 平台路由）')
print('=' * 86)
for item in MISSING:
    print(f'[前置失败] {item}')
if not results:
    print('无可执行检查项。')
passed = 0
for label, expected, actual, ok, note in results:
    mark = 'PASS' if ok else 'FAIL'
    passed += ok
    print(f'[{mark}] {label}')
    print(f'       期望 {expected} / 实际 {actual} —— {note}')
print('-' * 86)
print(f'结果：{passed}/{len(results)} 通过' + ('' if passed == len(results) else '（存在 FAIL，见上）'))
print('口径说明：跨应用资源访问返回 404 为防枚举设计（无权即不可见），强于 403；'
      '403 保留给「资源可见但操作被拒」。前端路由守卫与菜单读 capabilities 同源数据，')
print(f'无目标应用条目即不可达；UI 级深链拦截可登录该账号后访问 /applications/{target_app_id} 复验。')
