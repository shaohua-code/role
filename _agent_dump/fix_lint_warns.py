from pathlib import Path

# Fix easy unused-vars warnings on main path
fixes = []

# useReadinessPoll.ts - unused Ref import
p = Path(r'D:\project\role\frontend\src\composables\useReadinessPoll.ts')
t = p.read_text(encoding='utf-8')
nt = t.replace("import { onUnmounted, ref, type Ref } from 'vue'", "import { onUnmounted, ref } from 'vue'")
nt = nt.replace("import { onUnmounted, ref, Ref } from 'vue'", "import { onUnmounted, ref } from 'vue'")
if nt != t:
    p.write_text(nt, encoding='utf-8', newline='\n'); fixes.append('useReadinessPoll Ref')

# ResourceIcon SolutionOutlined
p = Path(r'D:\project\role\frontend\src\views\application-workspace\components\ResourceIcon.vue')
t = p.read_text(encoding='utf-8')
if 'SolutionOutlined' in t:
    # remove from import list carefully
    import re
    nt = re.sub(r',?\s*SolutionOutlined', '', t, count=1)
    nt = nt.replace('{\n}', '{}')  # just in case
    if nt != t:
        p.write_text(nt, encoding='utf-8', newline='\n'); fixes.append('ResourceIcon SolutionOutlined')

# RoleResourceGrantModal requestSequence
p = Path(r'D:\project\role\frontend\src\views\application-workspace\components\RoleResourceGrantModal.vue')
t = p.read_text(encoding='utf-8')
if 'requestSequence' in t:
    nt = t.replace('const requestSequence', 'const _requestSequence').replace('requestSequence.value', '_requestSequence.value').replace('requestSequence++', '_requestSequence++')
    # also let requestSequence = 
    nt = nt.replace('let requestSequence', 'let _requestSequence')
    if 'requestSequence' in nt and '_requestSequence' in nt:
        # leftover bare name - show context
        pass
    p.write_text(nt, encoding='utf-8', newline='\n'); fixes.append('RoleResourceGrantModal requestSequence')

# PermissionCatalog PERMISSION_SCOPES and unused label
p = Path(r'D:\project\role\frontend\src\views\permissions\PermissionCatalog.vue')
t = p.read_text(encoding='utf-8')
nt = t
# common pattern: import { ..., PERMISSION_SCOPES, ...}
import re
nt2 = re.sub(r',\s*PERMISSION_SCOPES\b|\bPERMISSION_SCOPES\s*,\s*', '', nt, count=1)
if nt2 != nt:
    nt = nt2; fixes.append('PC PERMISSION_SCOPES')
# unused label arg
if 'label' in nt:
    nt3 = nt.replace('(label)', '(_label)').replace('(label,', '(_label,').replace(', label)', ', _label)').replace(', label,', ', _label,')
    # too broad - find specific line 233 area
    lines = nt.splitlines()
    if len(lines) >= 233:
        print('PC L233:', lines[232])
    # only replace in filter callbacks if exact
    nt = re.sub(r'\(([a-zA-Z0-9_]*),\s*label\)', r'(\1, _label)', nt)
    nt = re.sub(r'\(label:\s*string\)', '(_label: string)', nt)
    p.write_text(nt, encoding='utf-8', newline='\n')

# TenantAccessManagement
p = Path(r'D:\project\role\frontend\src\views\tenant-admin\TenantAccessManagement.vue')
t = p.read_text(encoding='utf-8')
nt = t.replace("import { computed, reactive, ref", "import { computed, ref").replace("import { reactive, computed, ref", "import { computed, ref")
# activeOrganizationOptions
nt = nt.replace('const activeOrganizationOptions', 'const _activeOrganizationOptions')
if nt != t:
    p.write_text(nt, encoding='utf-8', newline='\n'); fixes.append('TenantAccessManagement')

print('fixes:', fixes)
