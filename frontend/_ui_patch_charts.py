from pathlib import Path
p = Path(r"D:\project\role\frontend\src\features\overview\OverviewDashboardCharts.vue")
t = p.read_text(encoding="utf-8")
t = t.replace("primaryColor: '#7c5cff'", "primaryColor: '#5B5BD6'", 1)
t = t.replace(
    "const palette = ['#7c5cff', '#c44bff', '#6366f1', '#38bdf8', '#f472b6', '#facc15']",
    "const palette = ['#5B5BD6', '#4F4FC9', '#2563EB', '#059669', '#D97706', '#64748B']",
    1,
)
p.write_text(t, encoding="utf-8")
print("charts palette updated")
