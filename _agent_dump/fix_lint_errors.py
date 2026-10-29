from pathlib import Path

# 1) App.vue: remove duplicate local onThemePreferenceChange (composable already provides it)
app_path = Path(r"D:\project\role\frontend\src\App.vue")
app = app_path.read_text(encoding="utf-8")
dup = (
    "function onThemePreferenceChange(): void {\n"
    "  localStorage.setItem('iam-theme', themePreference.value); "
    "localStorage.setItem('iam-primary-color', primaryColor.value); "
    "localStorage.setItem('iam-density', density.value)\n"
    "}\n\n"
)
if dup in app:
    app = app.replace(dup, "", 1)
    print("removed duplicate onThemePreferenceChange")
else:
    # try multiline variant
    import re
    new, n = re.subn(
        r"function onThemePreferenceChange\(\): void \{\n"
        r"  localStorage\.setItem\('iam-theme', themePreference\.value\); "
        r"localStorage\.setItem\('iam-primary-color', primaryColor\.value\); "
        r"localStorage\.setItem\('iam-density', density\.value\)\n"
        r"\}\n\n",
        "",
        app,
        count=1,
    )
    if n:
        app = new
        print("removed duplicate via regex")
    else:
        print("DUP NOT FOUND")
        idx = app.find("function onThemePreferenceChange")
        print(repr(app[idx:idx+220]))

# also avoid unused DEFAULT_PRIMARY warning
app2 = app.replace(
    "  onThemePreferenceChange,\n  bindAppearanceListeners,\n  disposeAppearanceListeners,\n  DEFAULT_PRIMARY,\n} = useShellAppearance()",
    "  onThemePreferenceChange,\n  bindAppearanceListeners,\n  disposeAppearanceListeners,\n} = useShellAppearance()",
    1,
)
if app2 != app:
    app = app2
    print("dropped unused DEFAULT_PRIMARY from destructure")
else:
    print("DEFAULT_PRIMARY destructure pattern not matched")

app_path.write_text(app, encoding="utf-8", newline="\n")

# 2) theme.ts: avoid no-control-regex while keeping same validation
theme_path = Path(r"D:\project\role\frontend\src\styles\theme.ts")
theme = theme_path.read_text(encoding="utf-8")
old = "  if (!raw || raw.startsWith('//') || /[\\u0000-\\u001f\\u007f\"'<>\\\\]/.test(raw)) return ''"
# Use code-point scan instead of control-char regex class
new = """  if (!raw || raw.startsWith('//')) return ''
  for (let i = 0; i < raw.length; i += 1) {
    const code = raw.charCodeAt(i)
    if (code <= 0x1f || code === 0x7f || '\"\\'<>\\\\'.includes(raw[i]!)) return ''
  }"""
# Careful with escaping in the source file - write exact JS
new = (
    "  if (!raw || raw.startsWith('//')) return ''\n"
    "  for (let i = 0; i < raw.length; i += 1) {\n"
    "    const code = raw.charCodeAt(i)\n"
    "    if (code <= 0x1f || code === 0x7f || \"\\\"'<>\\\\\".includes(raw[i]!)) return ''\n"
    "  }"
)
if old in theme:
    theme = theme.replace(old, new, 1)
    theme_path.write_text(theme, encoding="utf-8", newline="\n")
    print("theme.ts control-regex replaced")
else:
    print("theme old line not found")
    for i, line in enumerate(theme.splitlines(), 1):
        if "startsWith('//')" in line or "u0000" in line or "001f" in line:
            print(i, repr(line))
