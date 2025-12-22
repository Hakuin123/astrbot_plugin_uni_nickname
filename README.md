# Uni-nickname 统一昵称插件

AstrBot 插件 - 使用管理员配置的映射表统一用户昵称，让 AI 始终使用管理员设定的昵称称呼群友

~~因为群友把我可怜的小ai给ntr掉了所以一怒之下丢给Sonnet 4.5写的插件~~

![Moe Counter](https://count.getloli.com/@astrbot_plugin_uni_nickname?name=astrbot_plugin_uni_nickname&theme=capoo-2&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

## 说明

AstrBot 在给 LLM 发送聊天记录时会携带群友的自定义昵称，但是如果群友乱改昵称可能造成 LLM 认错人~~甚至被NTR~~的情况 qwq
此插件可配置映射表，指定用户ID对应的昵称，确保 AI 始终使用设定的昵称来称呼对方（效果横跨群聊和私聊生效）

## 功能

- **自动昵称替换**：在每次 LLM 请求前自动替换用户昵称
- **WebUI 配置**：支持在 AstrBot WebUI 管理面板中配置映射表
- **管理员指令**：可通过指令管理昵称映射

> [!WARNING]
已知问题：每个新对话中，映射表中的成员需要主动发送一条消息才会替换当前会话历史聊天记录中的昵称

## 配置方法

### 方法一：通过 WebUI 配置

1. 进入 AstrBot WebUI 的插件管理页面
2. 找到"统一昵称"插件，点击配置
3. 在"昵称映射表"中添加映射项，格式：`用户ID,昵称`
4. 示例：
   ```
   123456789,张三
   987654321,李四
   555666777,王五
   ```

### 方法二：通过管理员指令配置

插件提供了以下管理员指令（需要管理员权限）：

#### 查看所有映射
```
/nickname list
```

#### 添加/更新映射
```
/nickname set <用户ID> <昵称>
```
示例：
`/nickname set 123456789 张三`

#### 为自己设置昵称
```
/nickname setme <昵称>
```
示例：
`/nickname setme 管理员`

#### 删除映射
```
/nickname remove <用户ID>
```
示例：
`/nickname remove 123456789`

## 使用示例

假设配置了以下映射：
- `123456789` → `小明`

当用户 ID 为 `123456789` 的群友（实际昵称可能是"路人甲"或其他名称）发送消息给 AI 时：
- 原始消息：`路人甲: 今天天气怎么样？`
- 发送给 LLM：`小明: 今天天气怎么样？`
- AI 回复：`小明，今天天气晴朗...`

无论该用户如何修改自己的昵称，AI 始终会称呼其为"小明"

## Changelog
### v1.0.4
fix: 增强历史记录和上下文中的昵称替换逻辑
fix: 改回动态加载缓存列表（之前会导致新对话中功能失效问题）

## v1.0.3
fix: 处理偶现的神秘TypeError

### v1.0.2
feat: 实现并集成映射表缓存机制
chore：规范prompt模式命名

### v1.0.1
feat: 新增提示词注入模式与全局替换模式切换

### v1.0.0
基本功能实现

## 注意事项

- 插件仅对管理员开放昵称管理指令
- 昵称映射仅影响发送给 LLM 的消息，不影响消息平台显示的昵称
- 用户 ID 是消息平台的唯一标识（如 QQ 号、Telegram ID 等）
- 昵称中**如需使用半角逗号，请避免歧义**（插件会按第一个逗号分割）

## 致谢
- 灵感来源：@柠檬老师 ~~就是他把我小ai牛走的~~ ~~挂人说是~~
- 参考了 [识人术](https://github.com/Yue-bin/astrbot_plugin_maskoff) 插件

## 许可证

MIT License

## 支持

- 问题反馈：[GitHub Issues](https://github.com/Hakuin123/astrbot_plugin_uni_nickname/issues)
- AstrBot 文档：[https://astrbot.app](https://astrbot.app)
