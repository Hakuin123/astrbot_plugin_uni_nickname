# Uni-nickname 统一昵称插件

AstrBot 插件 - 使用映射表统一用户昵称，让AI始终使用设定的昵称称呼群友

~~因为群友把我可怜的小ai给ntr掉了所以一怒之下丢给 Sonnet 4.5 写的插件~~

![Moe Counter](https://count.getloli.com/@astrbot_plugin_uni_nickname?name=astrbot_plugin_uni_nickname&theme=capoo-2&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

## 介绍

AstrBot 在给 LLM 发送聊天记录时会携带群友的自定义昵称，但是如果群友乱改昵称可能造成 LLM 认错人~~甚至被NTR~~的情况qwq

此插件可配置映射表，指定用户ID对应的昵称，确保 AI 始终使用设定的昵称来称呼对方（效果横跨群聊和私聊生效）

## 主要功能

- **自动昵称替换**：在每次 LLM 请求前自动替换用户昵称
- **管理员指令**：可通过指令管理昵称映射
- **工具调用**：赋予 LLM 在自然对话中为当前用户设置昵称的能力
- **昵称审核**：支持开启基于自定义提示词的 AI 昵称审核

## 插件配置

### 方法一：通过 WebUI 配置

1. 进入 AstrBot WebUI 的插件管理页面
2. 找到"统一昵称"插件，点击配置
3. 在"昵称映射表"中添加映射项，格式：`用户ID,昵称`
   示例：
   ```
   123456789,凯尔希
   2854208913,阿米娅
   1145140721,博士
   ```
4. 按照说明选择一个合适的配置模式（参考下文**工作原理**）

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

示例：`/nickname set 123456789 凯尔希`

#### 为自己设置昵称

```
/nickname setme <昵称>
```

示例：`/nickname setme 普瑞赛斯`

#### 删除映射

```
/nickname remove <用户ID>
```

示例：`/nickname remove 123456789`

## 使用示例

假如配置了以下映射：

- `987654321` → `刀客塔`

当用户 ID 为 `987654321` 的群友（实际昵称"可露希尔"）发送消息给 bot 时：

- 原始消息：`可露希尔: 我是谁？`
- 发送给 LLM：`刀客塔: 我是谁？`
- bot 回复：`你是刀客塔！`

> [!NOTE]
> `system_replace`和`global_replace`配置都可以实现上述效果，区别在于如果你的消息里面提到了你的昵称，`system_replace`不会替换它，而`global_replace`会，详细区别请参见下方**工作原理**

## 注意事项

> [!NOTE]
>
> - 昵称管理指令默认仅对管理员开放，如需修改请前往 `AstrBot WebUI`→`插件`→`管理行为` 设置（需要 AstrBot v4.10 及以上版本）
> - 昵称中若使用半角逗号需避免歧义（插件会按第一个逗号分割昵称）
> - 在 global_replace 模式且启用历史记录替换时，映射表中的成员**需先发送至少一条消息**使插件缓存其原始昵称，之后其在历史记录或@消息中的昵称才会被替换

## 工作原理

插件使用 `@filter.on_llm_request()` 钩子在每次 LLM 请求前介入：

1. **匹配身份**：获取发送者 ID，查找映射表。
2. **模式执行**（可在配置项 `working_mode` 中切换）：
   - **prompt (提示词引导)**：插件会在系统提示词 (`system_prompt`) 中追加一条身份声明指令，不修改用户发送的正文文本。
   - **system_replace (系统标签替换)**：使用正则表达式查找并修改 AstrBot 注入发给 LLM 的 `<system_reminder>` 系统身份标签，**不修改**聊天正文。既能保证 LLM 认对人，又杜绝了因昵称是常用词而导致语义被误伤替换的问题。
   - **global_replace (全局替换)**：通过 Python 的 `replace` 方法直接在用户的正文 (`req.prompt`) 中全文搜索并替换旧昵称。如果开启了 `enable_session_replace`，还会改写 `req.contexts` 中的历史记录（插件会自动缓存用户的原始平台昵称，用于替换所有已知用户的昵称）。

## Changelog

参见[CHANGELOG.md](./CHANGELOG.md)

## 致谢

- 灵感来源：@柠檬老师 ~~就是他把我小ai牛走的~~ ~~挂人说是~~
- 参考了 [识人术](https://github.com/Yue-bin/astrbot_plugin_maskoff) 插件

## 许可证

MIT License

## 支持

- 问题反馈：[GitHub Issues](https://github.com/Hakuin123/astrbot_plugin_uni_nickname/issues)
- AstrBot 文档：[https://astrbot.app](https://astrbot.app)
