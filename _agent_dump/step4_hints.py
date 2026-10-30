from pathlib import Path
ROOT=Path(r'D:\project\role')
doc=ROOT/'docs'/'配权说明书.md'
print('DOC end:\n', doc.read_text(encoding='utf-8-sig')[-800:])

rm=ROOT/'frontend/src/views/roles/RoleManagement.vue'
t=rm.read_text(encoding='utf-8-sig')
old='subtitle="维护角色定义并把权限码挂载到角色，前端用码控制、后端只判角色。"'
new='subtitle="高级列表：完整角色 CRUD。日常按应用配权优先用「应用工作台」。码管菜单、角色管接口：挂码改变接口鉴权，菜单显隐另看权限码/资源树。"'
if old in t:
 t=t.replace(old,new,1)
 print('RM subtitle ok')
else:
 print('RM miss', 'subtitle=' in t)
hint_old='hint="授权遵循默认拒绝；数据范围按同一权限的多角色策略取并集，缺少有效策略时默认拒绝。点击行查看持码清单，点击上方卡片按作用域筛选。"'
hint_new='hint="授权默认拒绝；数据范围多角色并集。完整 CRUD 在本页；应用内挂码/资源/数据范围也可在应用工作台完成。点击行看持码，点卡片按作用域筛选。"'
if hint_old in t:
 t=t.replace(hint_old,hint_new,1)
rm.write_text(t if t.endswith('\n') else t+'\n', encoding='utf-8', newline='\n')

pc=ROOT/'frontend/src/views/permissions/PermissionCatalog.vue'
t=pc.read_text(encoding='utf-8-sig')
old='subtitle="平台权限码目录：登记稳定编码，供「角色管理」挂载。"'
new='subtitle="高级列表：全局权限编码目录。按应用维护请到「应用工作台 → 权限编码」。编码裁剪菜单；接口鉴权看角色挂码。"'
if old in t:
 t=t.replace(old,new,1); print('PC subtitle ok')
else:
 print('PC miss')
hint_old='hint="只读目录；编码不可编辑或删除，菜单显示不构成服务端授权。点击上方卡片可按「平台编码 / 应用业务编码」筛选；平台编码行的 L1 专属 / L3 起 / L2 起 标记表示该码从哪一级管理员开始持有。点击行查看引用角色。"'
hint_new='hint="目录以登记为主；菜单显示不构成服务端授权。完整目录在本页；应用域编码也可在应用工作台维护。点卡片筛选平台/应用编码；点行查看引用角色。"'
if hint_old in t:
 t=t.replace(hint_old,hint_new,1)
pc.write_text(t if t.endswith('\n') else t+'\n', encoding='utf-8', newline='\n')

# organization workspace empty dead links?
ow=ROOT/'frontend/src/views/organization-workspace/index.vue'
ot=ow.read_text(encoding='utf-8-sig')
if 'project-integration' in ot or '新项目接入' in ot:
 print('OW has dead integration refs')
else:
 print('OW clean of integration')
# App.vue dead project-integration
app=ROOT/'frontend/src/App.vue'
print('App integration', 'project-integration' in app.read_text(encoding='utf-8-sig'), '新项目接入' in app.read_text(encoding='utf-8-sig'))
