# CHANGELOG

> 本项目遵循 [语义化版本控制](https://semver.org/lang/zh-CN/)

## 最新版本

### v1.2.0

feat: 增加 system_replace 模式，当开启时仅替换系统提醒中的昵称，不替换用户消息中的昵称 (#3)（Thanks to **[@olozhika](https://github.com/olozhika)**！）

feat: 自动迁移旧版本配置

docs: 新增 CHANGELOG.md

## 历史更新记录

### v1.1.1

feat: 修改了更强硬的提示词，也许可以缓解提示词模式下认错“群昵称强烈指向别人名字”的成员的问题（Thanks to **[@NickWoluff](https://github.com/NickWoluff)**！）

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
