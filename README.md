# Uni-nickname 统一昵称插件

AstrBot 插件 - 使用映射表统一用户昵称，让AI始终使用设定的昵称称呼群友

~~因为群友把我可怜的小ai给ntr掉了所以一怒之下丢给 Sonnet 4.5 写的插件~~

![Moe Counter](https://count.getloli.com/@astrbot_plugin_uni_nickname?name=astrbot_plugin_uni_nickname&theme=capoo-2&padding=7&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

> [**戳这里给插件 GitHub 项目点点 Star 喵！点点 Star 谢谢喵！**](https://github.com/Hakuin123/astrbot_plugin_uni_nickname)

## 介绍

AstrBot 在给 LLM 发送聊天记录时会携带群友的自定义昵称，但是如果群友乱改昵称可能造成 LLM 认错人~~甚至被NTR~~的情况qwq

此插件可配置映射表，指定用户ID对应的昵称，确保 AI 始终使用设定的昵称来称呼对方（效果横跨群聊和私聊生效）

## 主要功能

- 在每次 LLM 请求前自动替换用户昵称
- 可通过指令管理昵称映射
- LLM 可通过工具调用在自然对话中为当前用户设置昵称
- 支持开启基于自定义提示词的 AI 昵称审核

## 插件配置

Uni-nickname 插件具有以下配置项：
- **用户ID与昵称映射表**：按照 `用户ID,昵称` 的格式配置映射关系。例如：`2854208913,阿米娅`（后续重构为 KV 类型）
- **工作模式**：可选择 `prompt`、`system_replace` 或 `global_replace` 模式
- **开启历史记录替换 (仅对 global_replace 生效)**：默认关闭，控制在 `global_replace` 模式下是否修改上下文历史消息。高风险操作，可能会导致语义混乱及上下文不一致。
- **启用 LLM 昵称设置工具**：默认开启，赋予 AI 在自然对话中为当前用户设置昵称的能力
- **启用 AI 昵称审核**：默认关闭，开启后，AI 通过工具为用户设置昵称时，会先调用模型审核昵称是否合规
- **昵称审核模型 ID**：用于执行昵称审核的模型 ID。推荐使用推理能力较强的模型；留空时默认使用当前对话模型
- **昵称审核提示词**：AI 昵称审核使用的提示词，可按需修改。可使用 当前昵称`{sender_name}`、待审核昵称`{nickname}` 两个变量；请明确要求模型返回 JSON 布尔值 `true` / `false`

> [!TIP]
>
> **三种工作模式的区别:**
> - `prompt` (提示词引导)：插件会在系统提示词中追加一条身份声明指令，不修改用户发送的聊天文本。
> - `system_replace` (系统标签替换)：修改 Astrbot 发给 AI 的身份标签，需在 Astrbot 设置中开启用户识别。**不修改**聊天正文。既能保证 LLM 认对人，又杜绝了因昵称是常用词而导致语义被误伤替换的问题。
> - `global_replace` (全局替换)：直接在用户的正文中全文搜索并替换旧昵称，有语义破坏风险。如果开启了 `enable_session_replace`，还会改写聊天历史记录（插件会自动缓存用户的原始平台昵称，用于替换所有已知用户的昵称）。

## 配置昵称方式

### 方法一：通过 WebUI 配置

1. 进入 AstrBot WebUI 的插件管理页面
2. 找到 **统一昵称 Uni-Nickname** 插件，点击配置
3. 在"昵称映射表"中添加映射项，格式：`用户ID,昵称`
   示例：
   ```
   123456789,凯尔希
   2854208913,阿米娅
   1145140721,博士
   ```
4. 按照说明选择一个合适的配置模式

### 方法二：通过与 AI 对话添加（工具调用，需要启用 LLM 昵称设置工具）

和 AI 进行对话时，可以使用插件提供的工具来为当前用户设置昵称。

示例：

> **行秋**：你好~你可以用**重云**称呼我吗？
> AI 回复：咱去帮行秋记录一下喵~ (拿笔在小本本上写写画画)
> `AI 🔨 调用工具: set_user_nickname`
> AI 回复：好鸭好鸭！咱以后就叫你行秋啦~ ( '▽' )ﾉ
>
>（此时昵称已设置完成）

### 方法三：通过管理员指令配置

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

当用户 ID 为 `987654321` 的群友（实际昵称“可露希尔”）发送消息给 AI 时：

- 原始消息：`可露希尔: 我是谁？`
- 发送给 LLM：`刀客塔: 我是谁？`
- AI 回复：`你是刀客塔！`

> [!NOTE]
> `system_replace`和`global_replace`配置都可以实现上述效果，区别在于如果你的消息里面提到了你的昵称，`system_replace`不会替换它，而`global_replace`会。

## 注意事项

> [!IMPORTANT]
>
> - 昵称管理指令默认仅对管理员开放，如需修改请前往 `AstrBot WebUI`→`插件`→`管理行为` 设置（需要 AstrBot v4.10 及以上版本）
> - 昵称中若使用半角逗号需避免歧义（插件会按第一个逗号分割昵称）
> - 在 `global_replace` 模式且启用历史记录替换时，映射表中的成员**需先发送至少一条消息**使插件缓存其原始昵称，之后其在历史记录或@消息中的昵称才会被替换
> - LLM 工具**仅能修改当前发言人的昵称**，无法修改其他用户的昵称。如需修改其他人的昵称请管理员手动通过指令或 WebUI 修改。

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
