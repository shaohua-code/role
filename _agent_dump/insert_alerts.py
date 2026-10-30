from pathlib import Path

pc = Path(r"D:\project\role\frontend\src\views\permissions\PermissionCatalog.vue")
t = pc.read_text(encoding="utf-8")
marker = '  <div class="permission-page">\n    <!-- P395'
banner = (
    '  <div class="permission-page">\n'
    '    <a-alert type="info" show-icon class="mb-3" '
    'message="高级列表：全局权限编码目录。编码裁剪菜单；接口鉴权看角色挂码。按应用维护请到「应用工作台 → 权限编码」。" />\n'
    '    <!-- P395'
)
if '高级列表：全局权限编码目录。编码裁剪菜单' in t and '<a-alert type="info" show-icon class="mb-3"' in t[: t.find("AdminListPage") + 1 if False else 800]:
    # check specifically near top
    head = t[t.find("<template>"): t.find("AdminListPage")]
    if '<a-alert type="info" show-icon class="mb-3" message="高级列表：全局权限编码目录' in head:
        print("PC already has banner")
    elif marker in t:
        pc.write_text(t.replace(marker, banner, 1), encoding="utf-8", newline="\n")
        print("PC banner inserted")
    else:
        print("PC marker missing")
elif marker in t:
    pc.write_text(t.replace(marker, banner, 1), encoding="utf-8", newline="\n")
    print("PC banner inserted")
else:
    print("PC marker missing")
    i = t.find('<div class="permission-page">')
    print(repr(t[i:i+180]))

rm = Path(r"D:\project\role\frontend\src\views\roles\RoleManagement.vue")
t = rm.read_text(encoding="utf-8")
marker2 = "  <!-- P397 作用域统计卡带：点击卡片即筛选（与权限编码页统计带同语言） -->\n  <AdminStatBand"
banner2 = (
    '  <a-alert type="info" show-icon class="mb-3" '
    'message="高级列表：完整角色 CRUD。日常按应用配权优先用「应用工作台」。码管菜单、角色管接口。" />\n'
    "  <!-- P397 作用域统计卡带：点击卡片即筛选（与权限编码页统计带同语言） -->\n"
    "  <AdminStatBand"
)
head = t[t.find("<template>"): t.find("AdminListPage")]
if 'message="高级列表：完整角色 CRUD。日常按应用配权优先用「应用工作台」。码管菜单、角色管接口。"' in head:
    print("RM already has banner")
elif marker2 in t:
    rm.write_text(t.replace(marker2, banner2, 1), encoding="utf-8", newline="\n")
    print("RM banner inserted")
else:
    print("RM marker missing")
    print(repr(head[:300]))
