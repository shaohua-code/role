# 归档：权限编码页（已下线）

原路径：`frontend/src/views/permissions/PermissionCatalog.vue`
下线原因：后端权限模型改为「菜单→按钮」节点树（menu.* / button.*），管理面 27 个接口码删除，
`menu.permissions` / `button.permissions.manage` 已从契约移除；权限编码页与侧栏入口下线，
旧深链 `/permissions` 重定向到 `/roles`。目录维护改由「平台角色 → 配置权限」承担。
源码保留备查，勿再挂回导航。
