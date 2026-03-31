# CHANGELOG

> 本项目遵循 [语义化版本控制](https://semver.org/lang/zh-CN/)

> [**戳这里给插件 GitHub 项目点点 Star 喵！点点 Star 谢谢喵！**](https://github.com/Hakuin123/astrbot_plugin_uni_nickname)

## 最新版本

## v1.3.0

feat: 新增 LLM 工具，赋予 LLM 在自然对话中为当前用户设置昵称的能力
feat: 新增呢称审核功能，支持开启基于自定义提示词的 AI 昵称审核

---

## 历史更新记录

### v1.2.2

fix: 优化 system_replace 中的文本替换规则，适配部分无法检测用户原昵称的平台 ([#7](https://github.com/Hakuin123/astrbot_plugin_uni_nickname/pull/7), Thanks to **[@olozhika](https://github.com/olozhika)**!)

### v1.2.1

fix: `system_replace` 兼容非纯数字用户 ID 避免匹配失败

fix: 平台昵称为空时不再提前退出处理流程，`global_replace` 仍可继续替换正文与历史记录

change: 未检测到 `<system_reminder>` 时`system_replace` 将停止工作；`global_replace` 继续工作并提醒检查 AstrBot 是否开启用户识别

refactor: 重命名 smart_replace 为 system_replace

### v1.2.0

feat: 增加 system_replace 模式，当开启时仅替换系统提醒中的昵称，不替换用户消息中的昵称 ([#3](https://github.com/Hakuin123/astrbot_plugin_uni_nickname/pull/3), Thanks to **[@olozhika](https://github.com/olozhika)**!)

feat: 自动迁移旧版本配置

docs: 新增 CHANGELOG.md

### v1.1.1

feat: 修改了更强硬的提示词，也许可以缓解提示词模式下认错“群昵称强烈指向别人名字”的成员的问题 ([#2](https://github.com/Hakuin123/astrbot_plugin_uni_nickname/pull/2), Thanks to **[@NickWoluff](https://github.com/NickWoluff)**!)

debug: 将部分日志级别从 info更改为 debug，以减少日志输出

### v1.1.0

feat: 新增原始昵称缓存机制，优化历史记录昵称替换功能

### ~~v1.0.4~~（已撤版）

### v1.0.3

fix: 处理偶现的神秘TypeError

### v1.0.2

feat: 实现并集成映射表缓存机制

chore：规范prompt模式命名

### v1.0.1

feat: 新增提示词注入模式与全局替换模式切换

### v1.0.0

基本功能实现
