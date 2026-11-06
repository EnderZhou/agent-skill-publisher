首个公开版本：将技能生成、WorkBuddy 专家制作与跨 Agent 分发经验整理为可安装技能和离线工具。

- WorkBuddy 技能元数据、专家格式与 15 字名称兼容检查。
- Trae、Codex、Claude Code、Cursor、GitHub Copilot、Hermes 适配指南。
- ZIP 根结构、资源链接、重复字段、二进制完整性与版本哈希检查。
- 单 Agent 专家构建器；保留独立技能与专家不同的目录规则。

下载 `_WorkBuddy_skill.zip` 用于 WorkBuddy 技能入口；`_Trae_skill.zip` 用于 Trae 导入；`_AgentSkills_folder.zip` 用于按目录发现技能的客户端；`_standard.zip` 为根入口通用资源包。

运行脚本需要 Python 3.10+ 与 PyYAML 6.x。所有发行包已做离线结构检查；目标客户端导入、实际调用和市场审核尚未验证。来源、边界、测试与示例见仓库 README。
