from pathlib import Path
ROOT=Path(r'D:\project\role')
for rel in [
 'frontend/src/views/application-workspace/tabs/RolesTab.vue',
 'frontend/src/views/application-workspace/tabs/PermissionsTab.vue',
 'frontend/src/views/application-workspace/tabs/MenuTab.vue',
 'frontend/src/views/roles/RoleManagement.vue',
 'frontend/src/views/permissions/PermissionCatalog.vue',
 'frontend/src/views/applications/ApplicationManagement.vue',
]:
 t=(ROOT/rel).read_text(encoding='utf-8-sig')
 print('====', rel, 'alert', t.count('a-alert'), '高级', '高级' in t, '工作台' in t)
 # find first alert
 i=t.find('<a-alert')
 if i>=0: print(t[i:i+350].replace('\n',' '))
