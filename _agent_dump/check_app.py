from pathlib import Path
import re
t=Path(r'D:\project\role\frontend\src\App.vue').read_text(encoding='utf-8-sig')
# remove import blocks for counting
body=re.sub(r"(?m)^import .+$","",t)
body=re.sub(r"from '@/router/loaders'[\s\S]*?\} from '@/router/loaders'","",t) # noop
# simpler: after page-registry import
idx=t.find("import { PAGE_COMPONENTS }")
rest=t[idx+200:]
for s in ['getReadiness','ReadinessError','nextTick','ApplicationManagement','OverviewPage','PermissionCatalog','ensureManagementUi','AdminColorField','FeatureLoading','LockOutlined']:
 print(s, rest.count(s), 'total', t.count(s))
