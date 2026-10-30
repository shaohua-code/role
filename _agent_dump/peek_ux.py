from pathlib import Path
ROOT=Path(r'D:\project\role')
# audit page head
ap=ROOT/'frontend/src/views/audit/AuditLogPage.vue'
t=ap.read_text(encoding='utf-8-sig')
print('AUDIT LEN', len(t))
print(t[:1500])
print('---tabs---', 'a-tabs' in t, '登录' in t, '操作' in t)
# roles tab head for alert insert point
rt=ROOT/'frontend/src/views/application-workspace/tabs/RolesTab.vue'
print('ROLESTAB', 'a-alert' in rt.read_text(encoding='utf-8-sig'))
print(rt.read_text(encoding='utf-8-sig')[:800])
# app workspace template alert area
aw=ROOT/'frontend/src/views/application-workspace/index.vue'
awt=aw.read_text(encoding='utf-8-sig')
i=awt.find('<template>')
print('AW template snippet', awt[i:i+900])
# 配权说明书 first 40 lines
doc=ROOT/'docs'/'配权说明书.md'
print('DOC', doc.read_text(encoding='utf-8-sig')[:1200])
