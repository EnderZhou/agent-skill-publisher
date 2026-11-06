# Agent Skill Publisher · Agent 技能与专家发布助手

把实际工作经验整理成可复用技能，生成 **WorkBuddy 技能与专家**，并为 **Trae、Codex、Claude Code、Cursor、GitHub Copilot、Hermes** 准备合适的技能目录或导入包。

本项目将技能编写、客户端适配、专家展示信息、包验证和 GitHub 发布经验集中维护。首版包含 2026-11-05 WorkBuddy 专家名称“17 字、上限 15 字”解析失败案例，以及技能包元数据、资源层级和版本管理经验。

**版本：v1.0.2 · 许可证：MIT · 维护者：周鹏（EnderZhou）**

## 能做什么

- 从经验提炼技能，划清适用范围，按需组织参考资料与脚本。
- 创建 WorkBuddy 单 Agent 专家，内置完整技能，检查中英文名称、角色信息、卡片文案与推荐问题。
- 从同一源码生成根入口包、WorkBuddy 市场包和标准技能目录包，避免污染通用 frontmatter。
- 检查实际 ZIP 的路径、大小写冲突、重复字段、常见本地链接、图片尺寸和明显凭据风险。
- 管理技能/专家独立版本、SHA256、更新和回滚，按用户授权发布 GitHub。

这是独立维护的工具与经验技能，无平台官方背书。包结构通过检查不等于在客户端完成导入、运行或市场审核。当前发行包记录的这些客户端阶段均为 **未验证**。

## 下载与安装

从 [最新 Release](https://github.com/EnderZhou/agent-skill-publisher/releases/latest) 下载：

| 文件后缀 | 用途 |
| --- | --- |
| `_WorkBuddy_expert.zip` | WorkBuddy **专家**上传入口，内置完整技能 |
| `_WorkBuddy_skill.zip` | WorkBuddy **技能**上传入口，包含专用市场元数据 |
| `_Trae_skill.zip` | Trae 技能上传候选包，根目录 SKILL.md |
| `_AgentSkills_folder.zip` | 将其中 `agent-skill-publisher` 文件夹放入已确认的客户端 skills 目录 |
| `_standard.zip` | 根入口通用源码资源包，供自行安装或再适配 |

目录包常用安装位置见 [客户端矩阵](skill/agent-skill-publisher/references/platforms.md)。如使用 Codex 当前官方目录，可解压到 `~/.agents/skills/` 或项目 `.agents/skills/`；已有客户端以实际发现路径为准，避免重复安装。同一份目录包可用于多个支持标准目录的客户端，不需要仅改文件名生成多个假适配包。

安装后可说：

> 使用 agent-skill-publisher，把我的经验整理为技能，为 WorkBuddy 生成技能和专家包，并检查是否满足上传要求。

在 Codex 可显式调用 `$agent-skill-publisher`。不必先连接 GitHub 才能离线制作与检查。创建仓库和发布仅在用户授权时执行。

## 命令行

Python 3.10+，依赖 PyYAML 6.x；打包工具不会自动安装依赖或访问网络。

```bash
python -m pip install -r requirements.txt
python skill/agent-skill-publisher/scripts/publish.py check skill/agent-skill-publisher
python skill/agent-skill-publisher/scripts/publish.py package skill/agent-skill-publisher out/skill.zip --profile workbuddy --metadata skill/agent-skill-publisher/assets/workbuddy-market.json
python skill/agent-skill-publisher/scripts/publish.py check out/skill.zip --profile workbuddy
```

创建专家时，先复制并编辑 [专家配置示例](skill/agent-skill-publisher/assets/expert-config.example.json)、[角色正文示例](skill/agent-skill-publisher/assets/expert-body.example.md)，准备自己的 512×512 PNG/JPEG 头像。示例作者与邮箱必须替换；图片不随示例伪造。

```bash
python skill/agent-skill-publisher/scripts/publish.py expert my-expert.json agent-body.md avatar.png out/expert.zip --skill skill/agent-skill-publisher
python skill/agent-skill-publisher/scripts/publish.py check out/expert.zip --profile expert
```

工具保留资源字节，对 WorkBuddy 独立技能的深层资源报错，要求先在适配副本中修正引用和加载器。专家内置技能不受独立技能两段路径 profile 的约束。不会自动执行输入技能代码、安装到客户端或上传平台。

## 项目布局

```text
skill/agent-skill-publisher/   可安装技能与工具
tests/                       行为与包完整性测试
tools/build_release.py       生成本项目发行包与校验清单
.github/workflows/ci.yml      Linux/Windows 自动检查
```

```bash
python -m unittest discover -s tests -v
python tools/build_release.py
```

`dist/` 内包含版本化 ZIP、逐包检查报告、SHA256SUMS 和发行清单。发布后应下载资产比对哈希；本地安装和目标客户端验证需分别记录。

## 验证边界与来源

本工具覆盖有限的静态 schema 与常见 Markdown 内联链接，不能检查脚本动态路径、所有 YAML 扩展或客户端真实能力。凭据模式检查不能替代发布者复核；图片尺寸检查不代表内容已过审。完整边界见 [打包指南](skill/agent-skill-publisher/references/packaging.md)。

指南依据官方资料和维护者实际反馈编写，区分官方规范与上传器观察。名称 15 字限制及独立技能两段目录规则的证据见 [案例记录](skill/agent-skill-publisher/references/lessons.md)；链接与核对日期见 [来源记录](skill/agent-skill-publisher/assets/source-records.json)。代码独立实现，未嵌入其他技能代码或企业业务资料。

欢迎通过 [Issues](https://github.com/EnderZhou/agent-skill-publisher/issues) 提交导入报错和适配反馈。请附脱敏包结构、目标客户端版本、实际错误与期望结果；不要提交令牌、原始企业日志或私有业务文件。
