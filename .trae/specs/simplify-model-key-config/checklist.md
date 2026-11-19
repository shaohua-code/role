# Checklist

- [x] `model_channel.py` 第 1 行恢复为原 docstring 首行，无残留 `.env` 粘贴文本（ast 解析 OK；test_model_channel.py 导入该模块并 15/15 通过，即导入成功）
- [x] `tests/test_model_channel.py` 15/15 passed
- [x] `compose.yaml` api 服务含 `env_file: - ./.env` 块；`docker compose config` 未运行（本终端无 Docker CLI），以 PyYAML 静态解析校验通过并按预案记录「未运行」
- [x] 既有 `DEEPSEEK_API_KEY` 显式透传行保留，显式 `environment` 优先级语义未变（PyYAML 校验字段仍在）
- [x] `.env` 注释含「新增供应商只改本文件 + 重建容器」说明
- [x] `ai/04-模块导航/模型用量/导航.md` 配置说明已同步（新增「供应商密钥注入」条目）
- [x] `CHANGELOG.md` 已追加本次事实记录（运行过的验证与未运行项分别写明）
- [x] 目标环境验证：容器内可见新密钥变量——**未运行**（本终端无 Docker CLI），已在 CHANGELOG 明确记录并附用户侧完整操作步骤（.env 加 MOONSHOT_API_KEY → docker compose up -d api → 管理台建模型 → 测试台探针）
