from pathlib import Path
t=Path(r'D:\project\role\frontend\src\App.vue').read_text(encoding='utf-8-sig')
idx=t.find("import { PAGE_COMPONENTS }")
rest=t[idx:]
for name in ['ApplicationManagement','OverviewPage','PermissionCatalog','nextTick','getReadiness']:
 i=rest.find(name)
 print(name, i)
 if i>=0: print(repr(rest[max(0,i-40):i+80]))
