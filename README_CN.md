# Agentic A*STAR — 多智能体 Discord 模拟系统

基于 Discord 的多智能体模拟系统，完整映射 [A\*STAR](https://www.a-star.edu.sg/)（新加坡科技研究局）组织架构。每个关键岗位都是一个 AI Agent，能够接收任务、讨论决策、逐级委派、汇报结果 —— 所有交互都在 Discord 频道中实时可观察。

## 架构总览

```
你（用户）
  │
  └──▶ #task-inbox  ──▶  Liaison 联络代理  ──▶  CEO
                                                 │
                          ┌──────────────────────┼──────────────────────┐
                          ▼                      ▼                      ▼
                     DCE 研究               DCE 创新企业           DCE 公司治理
                          │                      │                      │
               ┌──────────┼──────────┐           │           ┌─────────┼─────────┐
               ▼          ▼          ▼          ...         ▼         ▼         ▼
          ACE BMRC   ACE SERC   研究所所长             ACE 企业发展  ACE 基础设施
               │          │
          9个生医所    8个工程所 + 国家中心
```

**31 个 Agent** 完整映射真实 A\*STAR 组织架构，外加 **1 个 Liaison 联络代理** 由你直接控制。

## 核心设计

| 概念 | 实现方式 |
|------|----------|
| 权限分级 | `AuthorityLevel` 枚举，5 级（Board → Centre） |
| 私人频道 | 每个 Agent 有独立的 `#private-*` 频道，可直接与用户对话 |
| 公开频道 | 按部门划分（`#bmrc-council`、`#serc-council` 等），用于观察 Agent 间交流 |
| 信封系统 | `Envelope` 消息模型，通过 `Router` 路由 —— 每条消息自动记录到 Discord |
| 任务交付 | 用户在 `#task-inbox` 发消息 → Liaison 分析 → CEO 委派 → 逐级下发 |
| 圆桌讨论 | `!roundtable <主题>` 触发高管层集体讨论 |

## 快速开始

### 1. 前置条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 包管理器
- Discord Bot Token（[Discord 开发者门户](https://discord.com/developers/applications)）
- OpenAI 兼容 API Key

### 2. 安装

```bash
cd Agentic_ASTAR

# 安装依赖（uv 已初始化）
uv sync

# 复制环境变量模板并填入你的密钥
cp .env.example .env
# 编辑 .env，填入 DISCORD_TOKEN、DISCORD_GUILD_ID、OPENAI_API_KEY
```

### 3. 创建 Discord Bot

1. 前往 [Discord 开发者门户](https://discord.com/developers/applications)
2. 新建应用 → Bot 标签页 → 复制 Token
3. 在 Privileged Gateway Intents 下开启 **Message Content Intent** 和 **Server Members Intent**
4. 生成邀请链接，勾选权限：`Manage Channels`、`Send Messages`、`Embed Links`、`Read Message History`
5. 邀请 Bot 到你的服务器
6. 右键服务器 → 复制服务器 ID → 填入 `DISCORD_GUILD_ID`

### 4. 运行

```bash
uv run astar-sim
```

首次启动时，Bot 会自动创建两个分类下的所有频道：**A\*STAR HQ**（公开）和 **Private Channels**（私人）。

## 命令

| 命令 | 说明 |
|------|------|
| `!agents` | 列出所有 Agent 及其待处理邮件数 |
| `!org` | 显示组织架构层级 |
| `!tasks` | 列出所有任务 |
| `!mail <agent_id> <消息>` | 直接给任意 Agent 发送信封 |
| `!roundtable <主题>` | 发起高管圆桌讨论 |
| `!status` | 查看模拟系统状态 |
| `!autopilot on` / `!autopilot off` | 开启或关闭持续自治讨论 |

## 从 GitHub 克隆运行

```bash
git clone https://github.com/<你的用户名>/agentic-astar.git
cd agentic-astar
cp .env.example .env   # 填入密钥，切勿提交 .env
uv sync
uv run astar-sim
```

若仓库为公开或密钥曾泄露，请在各平台轮换 API Key。

## 如何交付任务

在 **#task-inbox** 频道直接输入你的需求，例如：

> 利用基因组数据设计一个热带传染病 AI 诊断工具

Liaison 联络代理会分析请求、创建任务、发送给 CEO。CEO 会根据内容委派给对应部门。你可以在 `#executive-council`、`#bmrc-council`、`#serc-council` 等频道观察整个讨论和决策过程。

## 配置项

所有配置通过 `.env` 文件管理：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DISCORD_TOKEN` | — | Bot Token |
| `DISCORD_GUILD_ID` | 0 | 服务器 ID |
| `OPENAI_API_KEY` | — | LLM API 密钥 |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API 地址（兼容 DeepSeek 等） |
| `OPENAI_MODEL` | `gpt-4o-mini` | 模型名称 |
| `TICK_INTERVAL` | 30 | Agent 检查邮箱的间隔（秒） |
| `MAX_MEMORY` | 50 | 每个 Agent 的对话记忆条数 |
| `AGENT_COOLDOWN` | 5 | 同一 Agent 两次 LLM 调用的最小间隔（秒） |

## 完整 Agent 列表

### 董事会与管理层
- **chairman** — Prof Tan Chorh Chuan（董事长）
- **ceo** — Mr Beh Kian Teik（首席执行官）

### 副首席执行官 / 助理首席执行官
- **dce_research** — Prof Andy Hor（副首席执行官，研究）
- **dce_ie** — Prof Yeo Yee Chia（副首席执行官，创新与企业）
- **dce_corporate** — Mr Suresh Sachi（副首席执行官，公司治理与法务总顾问）
- **ace_bmrc** — Dr Lisa Ooi（助理首席执行官，生物医学研究理事会）
- **ace_serc** — Prof Lim Keng Hui（助理首席执行官，科学与工程研究理事会）
- **ace_ie** — Ms Irene Cheong（助理首席执行官，创新与企业 / 研究生院）
- **ace_corp_dev** — Mr Glen Tan（助理首席执行官，企业发展）
- **ace_infra** — Mr Haryanto Tan（助理首席执行官，基础设施）

### BMRC 生物医学研究所
- **dir_bii** — Dr Sebastian Maurer-Stroh（生物信息学研究所）
- **dir_bti** — Dr Koh Boon Tong（生物加工技术研究所）
- **dir_gis** — Dr Wan Yue（新加坡基因组研究所）
- **dir_idl** — Prof Lisa Ng（传染病实验室）
- **dir_ihdp** — Prof Johan Eriksson（人类发展与潜力研究所）
- **dir_imcb** — A/Prof Su Xinyi（分子与细胞生物学研究所）
- **dir_sign** — Prof Lam Kong Peng（新加坡免疫学网络）
- **dir_sifbi** — Dr Sze Cotte-Tan（新加坡食品与生物技术创新研究所）
- **dir_srl** — Prof Rachel Watson（皮肤研究实验室）

### SERC 科学与工程研究所
- **dir_artc** — Dr David Low（先进再制造与技术中心 / SIMTech）
- **dir_ime** — Mr Terence Gan（微电子研究所）
- **dir_ihpc** — Dr Su Yi（高性能计算研究所）
- **dir_imre** — Prof Loh Xian Jun（材料研究与工程研究所）
- **dir_isce2** — Prof Reginald Tan（化学、能源与环境可持续发展研究所）
- **dir_i2r** — Dr Sun Sumei（资讯通信研究所）
- **dir_nmc** — Prof Gregory Goh（国家计量中心）

### 国家中心
- **dir_ai_coe** — Dr Wang Wei（制造业 AI 卓越中心）
- **dir_nscc** — Dr Terence Hung（国家超级计算中心）
- **dir_eddc** — Prof Damian O'Connell（实验药物研发中心）
- **dir_catos** — Dr Yang Yinping（在线安全先进技术中心）

### 外部
- **user_liaison** — 你的个人 AI 联络代理，负责向 A*STAR 组织交付任务
