from pathlib import Path
ROOT=Path(r'D:\project\role')
doc=ROOT/'docs'/'配权说明书.md'
print('DOC len', doc.stat().st_size)
print(doc.read_text(encoding='utf-8-sig')[:2000])
print('==== PT')
pt=ROOT/'frontend/src/views/application-workspace/tabs/PermissionsTab.vue'
print('PT len', pt.stat().st_size)
print(pt.read_text(encoding='utf-8-sig')[:1500])
print('==== RM header')
rm=ROOT/'frontend/src/views/roles/RoleManagement.vue'
t=rm.read_text(encoding='utf-8-sig')
i=t.find('<template>')
print(t[i:i+800])
print('==== PC header')
pc=ROOT/'frontend/src/views/permissions/PermissionCatalog.vue'
t=pc.read_text(encoding='utf-8-sig')
i=t.find('<template>')
print(t[i:i+800])
