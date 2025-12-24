# Uni-nickname 统一昵称插件

AstrBot 插件 - 使用管理员配置的映射表统一用户昵称，让 AI 始终使用管理员设定的昵称称呼群友

~~因为群友把我可怜的小ai给ntr掉了所以一怒之下丢给Sonnet 4.5写的插件~~

![Moe Counter](https://count.getloli.com/@astrbot_plugin_uni_nickname?name=astrbot_plugin_uni_nickname&theme=capoo-2&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

## 功能说明

AstrBot 在给 LLM 发送聊天记录时会携带群友的自定义昵称，但是如果群友乱改昵称可能造成 LLM 认错人~~甚至被NTR~~的情况 qwq
此插件可配置映射表，指定用户ID对应的昵称，确保 AI 始终使用设定的昵称来称呼对方（效果横跨群聊和私聊生效）

## 核心特性

- **自动昵称替换**：在每次 LLM 请求前自动替换用户昵称
- **WebUI 配置**：支持在 AstrBot WebUI 管理面板中配置映射表
- **管理员指令**：可通过指令管理昵称映射

## 配置方法

### 方法一：通过 WebUI 配置

1. 进入 AstrBot WebUI 的插件管理页面
2. 找到"统一昵称"插件，点击配置
3. 在"昵称映射表"中添加映射项，格式：`用户ID,昵称`
4. 示例：
   ```
   123456789,凯尔希
   2854208913,阿米娅
   1145140721,博士
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
`/nickname set 123456789 凯尔希`

#### 为自己设置昵称
```
/nickname setme <昵称>
```
示例：
`/nickname setme 普瑞赛斯`

#### 删除映射
```
/nickname remove <用户ID>
```
示例：
`/nickname remove 123456789`

## 使用示例

假如配置了以下映射：
- `987654321` → `刀客塔`

当用户 ID 为 `987654321` 的群友（实际昵称"可露希尔"）发送消息给 bot 时：
- 原始消息：`可露希尔: 我是谁？`
- 发送给 LLM：`刀客塔: 我是谁？`
- bot 回复：`你是刀客塔！`

## 注意事项

> [!INFO]
- 昵称管理指令默认仅对管理员开放
- 昵称中若使用半角逗号需避免歧义（插件会按第一个逗号分割昵称）
- 在 Global 模式且启用历史记录替换时，插件只会替换那些已被缓存原始昵称的成员；因此，映射表中的成员需先发送至少一条消息以让插件缓存原始昵称，之后其在历史记录（包括 @ 消息）中的昵称才会被替换。

## 工作原理

插件使用 `@filter.on_llm_request()` 钩子在每次 LLM 请求前介入：

1. **匹配身份**：获取发送者 ID，查找映射表。
2. **模式执行**：
   - **提示词模式**：插件会在 `ProviderRequest.system_prompt` 中追加一条指令（例如：`Address user 'Will' as 'Boss'`）。这样即便用户的名字本身是常用词汇，也不会发生错误的单词替换。
   - **全局模式**：通过 Python 的 `replace` 方法直接修改 `req.prompt` 中的文本。如果开启了 `enable_session_replace`，还会改写 `req.contexts` 中的历史记录（插件会自动缓存用户的原始平台昵称，用于替换所有已知用户的昵称）。

## Changelog
### v1.1.0
feat: 增加历史记录昵称替换功能，优化昵称缓存机制

#### ~~v1.0.4~~（已撤版）

### v1.0.3
fix: 处理偶现的神秘TypeError

### v1.0.2
feat: 实现并集成映射表缓存机制
chore：规范prompt模式命名

### v1.0.1
feat: 新增提示词注入模式与全局替换模式切换

### v1.0.0
基本功能实现

## 致谢
- 灵感来源：@柠檬老师 ~~就是他把我小ai牛走的~~ ~~挂人说是~~
- 参考了 [识人术](https://github.com/Yue-bin/astrbot_plugin_maskoff) 插件

## 许可证

MIT License

## 支持

- 问题反馈：[GitHub Issues](https://github.com/Hakuin123/astrbot_plugin_uni_nickname/issues)
- AstrBot 文档：[https://astrbot.app](https://astrbot.app)
