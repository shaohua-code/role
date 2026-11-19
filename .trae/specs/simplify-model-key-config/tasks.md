# Tasks

- [x] Task 1: 修复 `backend/app/services/model_channel.py` 第 1 行误粘贴污染（删除行首误粘的 `MOONSHOT_API_KEY=sk-你的真实key` 文本，恢复原 docstring 首行 `"""模型测试台受控 Provider 出口（OpenAI 兼容 chat/completions，设计文档 §5）。`），并验证模块可导入
  - [x] SubTask 1.1: 编辑第 1 行去除误粘文本
  - [x] SubTask 1.2: ast 语法解析 OK；`tests/test_model_channel.py` 15/15 passed（测试导入该模块，即导入验证通过）
- [x] Task 2: `compose.yaml` api 服务新增 `env_file: - ./.env` 注入块（放在 `environment:` 之前，带注释说明「显式 environment 优先；新供应商密钥只改 .env 即可」）；既有 `DEEPSEEK_API_KEY` 显式透传行保留不动
  - [x] SubTask 2.1: 编辑 compose.yaml
  - [x] SubTask 2.2: 本终端无 Docker CLI（历史既有约束），以 PyYAML 解析静态校验替代：`env_file=['./.env']`、`DEEPSEEK_API_KEY` 显式透传仍在；`docker compose config` 未运行（已记入 CHANGELOG）
- [x] Task 3: 配置说明同步
  - [x] SubTask 3.1: `.env` 模型密钥区注释补「新增供应商只改本文件，无需改 compose.yaml；改后 docker compose up -d api 重建容器」
  - [x] SubTask 3.2: `ai/04-模块导航/模型用量/导航.md` 新增「供应商密钥注入（2026-11-19 简化）」条目
  - [x] SubTask 3.3: `CHANGELOG.md` 追加事实记录（含验证结果与未运行项及用户侧操作步骤）
- [x] Task 4: 目标环境验证（需用户本地 Docker 环境）——本终端无 Docker CLI，无法执行容器级验证；已在 CHANGELOG 明确记录「未运行」与完整用户侧操作步骤（.env 加密钥 → up -d api → 管理台建模型 → 测试台探针），未以隔离验证冒充端到端完成
  - [x] SubTask 4.1: 容器内 printenv 验证——未运行（记录于 CHANGELOG，含替代操作步骤）
  - [x] SubTask 4.2: 管理台 moonshot 模型真实外呼探针——未运行（记录于 CHANGELOG，含替代操作步骤）

# Task Dependencies
- Task 2 依赖 Task 1 完成（避免带语法损坏的代码重建镜像）
- Task 3 的 SubTask 3.3 依赖 Task 1/2 完成后记录真实验证结果
- Task 4 依赖 Task 2 完成，且需要用户本地 Docker 环境配合执行
