# 简化模型密钥配置 Spec

## Why
当前新增一个模型供应商需要同时改两处文件：根 `.env` 写密钥 + `compose.yaml` 手动加环境变量透传行，容易遗漏且步骤繁琐。用户要求：**只需在 `.env` 配置密钥即可**，其余零改动。

## What Changes
- `compose.yaml` 的 `api` 服务新增 `env_file: - ./.env`，把根 `.env` 整文件注入 API 容器环境（Docker Compose 语义：显式 `environment` 优先于 `env_file`，现有全部显式映射行为不变）
- 此后新增供应商密钥只改 `.env` 一处 + `docker compose up -d api` 重建容器；`compose.yaml` 不再需要为新供应商加行
- 保留既有 `DEEPSEEK_API_KEY` 显式透传行（冗余但向后兼容，避免任何优先级歧义）
- **修复**：`backend/app/services/model_channel.py` 第 1 行被误粘贴了一行 `.env` 内容（`MOONSHOT_API_KEY=sk-你的真实key`），导致 Python 语法损坏、模块无法导入——恢复原 docstring 首行（此为用户误操作修正，非回滚有意改动）
- 同步：`.env` 注释补充说明、`ai/04-模块导航/模型用量/导航.md` 配置说明、`CHANGELOG.md` 事实记录

## Impact
- Affected specs: 无既有 spec 依赖模型密钥注入方式
- Affected code:
  - `compose.yaml`（api 服务 environment 区，加 env_file 块）
  - `backend/app/services/model_channel.py`（仅第 1 行误粘贴修复）
  - `.env`（注释）、`ai/04-模块导航/模型用量/导航.md`、`CHANGELOG.md`

## 安全边界（不变式）
- 明文密钥仍只存在于部署环境（根 `.env` → 容器环境变量），数据库/审计/日志/UI 均不落密钥
- `env_file: .env` 注入的变量集与现有显式透传高度重合（IAM_SMTP_*、DEEPSEEK_API_KEY 等本就已进容器），敏感面无实质扩大
- `.env` 中 `IAM_POSTGRES_PASSWORD`、`IAM_JWT_SECRET` 本就经 `environment` 注入 postgres/api 容器，不新增暴露路径

## ADDED Requirements

### Requirement: 供应商密钥单文件配置
系统 SHALL 支持仅通过编辑根 `.env` 完成新供应商密钥的部署注入，无需修改 `compose.yaml`。

#### Scenario: 新增供应商密钥
- **WHEN** 用户在根 `.env` 追加 `XXX_API_KEY=<真实密钥>` 并执行 `docker compose up -d api`
- **THEN** API 容器环境变量中存在 `XXX_API_KEY`，无需改动 `compose.yaml`

#### Scenario: 管理台建模型直连新供应商
- **WHEN** 用户在模型治理新建模型：供应商标识填已内置默认端点的 provider（如 `moonshot`）、API 地址留空、密钥只填环境变量名 `XXX_API_KEY`
- **THEN** 测试台连接探针可解析到密钥并完成外呼验证

### Requirement: 现有行为零回归
显式 `environment` 映射 SHALL 继续优先于 `env_file` 注入，现有 DeepSeek 通道与全部 IAM_* 配置行为不变。

#### Scenario: DeepSeek 通道不受影响
- **WHEN** 使用已配置的 deepseek 模型发起测试台对话
- **THEN** 凭证解析、流式对话、用量落账行为与改造前一致

## MODIFIED Requirements
（无）

## REMOVED Requirements
（无）
