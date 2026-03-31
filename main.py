import re
import json
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.provider import ProviderRequest
from astrbot.core.provider.func_tool_manager import FunctionToolManager
import textwrap


@register(
    "uni_nickname",
    "Hakuin123",
    "统一昵称插件 - 使用管理员配置的映射表统一用户昵称",
    "1.2.1",
)
class UniNicknamePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # 兼容老版本配置：将旧的 "global" 模式自动升级为 "global_replace"
        if self.config.get("working_mode") == "global":
            self.config["working_mode"] = "global_replace"
            self.config.save_config()
            logger.info("已将旧版 'global' 配置自动迁移至 'global_replace'")
            
        self._mappings_cache = self._parse_mappings()
        # 运行时缓存：用户ID -> 原始平台昵称
        # 用于在历史记录中替换所有已知用户的昵称
        self._original_nickname_cache: dict[str, str] = {}
        logger.info("统一昵称插件已加载，缓存已初始化")

    def _parse_mappings(self) -> dict:
        """解析配置中的昵称映射列表，返回 {用户ID: 昵称} 字典"""
        mappings = {}
        mapping_list = self.config.get("nickname_mappings", [])
        for item in mapping_list:
            if not isinstance(item, str) or "," not in item:
                continue

            # 按逗号分割，只分割第一个逗号（防止昵称中包含逗号）
            parts = item.split(",", 1)
            if len(parts) == 2:
                user_id = parts[0].strip()
                nickname = parts[1].strip()
                if user_id and nickname:
                    mappings[user_id] = nickname
        return mappings

    def _save_mappings(self, mappings: dict):
        """将映射字典保存到配置文件并更新缓存"""
        mapping_list = [
            f"{user_id},{nickname}" for user_id, nickname in mappings.items()
        ]
        self.config["nickname_mappings"] = mapping_list
        self.config.save_config()
        # 同步更新内存缓存，确保下一次 LLM 请求立即生效
        self._mappings_cache = mappings

    def _set_nickname_mapping(self, user_id: str, nickname: str) -> None:
        """写入单个昵称映射并同步缓存"""
        mappings = self._parse_mappings()
        mappings[user_id] = nickname
        self._save_mappings(mappings)

    def _remove_nickname_mapping(self, user_id: str) -> str | None:
        """删除单个昵称映射，返回被删除的昵称"""
        mappings = self._parse_mappings()
        nickname = mappings.pop(user_id, None)
        if nickname is not None:
            self._save_mappings(mappings)
        return nickname

    def _build_nickname_review_prompt(
        self,
        sender_name: str,
        nickname: str,
    ) -> str:
        """构造昵称审核提示词。"""
        template = (self.config.get("nickname_review_prompt", "") or "").strip()
        if not template:
            raise ValueError("昵称审核提示词不能为空")

        return (
            template.replace("{sender_name}", sender_name or "")
            .replace("{nickname}", nickname)
        )

    async def _review_nickname_by_ai(
        self,
        event: AstrMessageEvent,
        nickname: str,
    ) -> tuple[bool, str]:
        """调用 AI 审核昵称是否合法。"""
        if not self.config.get("enable_nickname_review", False):
            return True, "未开启昵称审核"

        if review_provider_id := (self.config.get("nickname_review_model", "") or "").strip():
            provider = self.context.get_provider_by_id(review_provider_id)
            if not provider:
                return False, f"审核失败：未找到指定审核模型提供商 ID：{review_provider_id}"
        else:
            provider = self.context.get_using_provider(event.unified_msg_origin)
            if not provider:
                return False, "审核失败：当前未找到可用对话模型"

        prompt = self._build_nickname_review_prompt(
            sender_name=event.get_sender_name() or "",
            nickname=nickname,
        )

        try:
            llm_resp = await provider.text_chat(
                prompt=prompt,
                func_tool=None,
            )
        except Exception as e:
            logger.error(f"[uni_nickname] AI 昵称审核失败: {e}")
            return False, f"审核失败：{e}"

        content = (llm_resp.completion_text or "").strip()
        if not content:
            return False, "审核失败：审核模型未返回结果"

        try:
            result = json.loads(content)
        except Exception:
            logger.warning(f"[uni_nickname] 审核结果不是合法 JSON: {content}")
            return False, "审核失败：审核模型返回格式无效"

        approved = bool(result.get("approved", False))
        reason = str(result.get("reason", "")).strip() or "未提供原因"
        return approved, reason

    def _system_replace_in_text(self, text: str, mappings: dict) -> str:
        """
        智能替换：只替换形如 <system_reminder>...User ID: 123, Nickname: 原始名 中的原始名
        """
        # 匹配模式：
        # 修改点：将 Nickname:\s* 改为 Nickname:[ \t]*，防止吞掉紧跟的换行符
        pattern = r"(<system_reminder>.*?User ID:\s*([^,\n]+),\s*Nickname:[ \t]*)([^\n<]*)"

        def replacer(match):
            prefix = match.group(1)
            user_id = match.group(2).strip()
            original_nick = match.group(3)
            
            if user_id in mappings:
                custom_nick = mappings[user_id]
                if custom_nick != original_nick:
                    logger.debug(
                        f"[uni_nickname] 智能替换：用户 {user_id} 的 Nickname 从 '{original_nick}' 替换为 '{custom_nick}'"
                    )
                return prefix + custom_nick
            else:
                return match.group(0)

        return re.sub(pattern, replacer, text, flags=re.IGNORECASE | re.DOTALL)

    def _system_replace_in_textpart(self, part, mappings: dict) -> bool:
        """对 TextPart 对象应用智能替换，返回是否修改"""
        text = self._get_textpart_text(part)
        if text is None:
            return False
        new_text = self._system_replace_in_text(text, mappings)
        if new_text != text:
            self._set_textpart_text(part, new_text)
            return True
        return False

    def _replace_all_in_textpart(self, part, replace_map: dict) -> bool:
        """对 TextPart 对象应用全局替换，返回是否修改"""
        text = self._get_textpart_text(part)
        if text is None:
            return False
        new_text = text
        for orig, custom in replace_map.items():
            if orig in new_text:
                new_text = new_text.replace(orig, custom)
        if new_text != text:
            self._set_textpart_text(part, new_text)
            return True
        return False

    def _get_textpart_text(self, part) -> str | None:
        """兼容 AstrBot 的 TextPart 对象和字典格式的文本块。"""
        if hasattr(part, "text") and isinstance(part.text, str):
            return part.text
        if isinstance(part, dict) and part.get("type") == "text":
            text = part.get("text")
            if isinstance(text, str):
                return text
        return None

    def _set_textpart_text(self, part, text: str) -> bool:
        """更新文本块内容，兼容对象和字典格式。"""
        if hasattr(part, "text") and isinstance(getattr(part, "text", None), str):
            part.text = text
            return True
        if isinstance(part, dict) and part.get("type") == "text":
            part["text"] = text
            return True
        return False

    def _request_has_identity_reminder(self, req: ProviderRequest, user_id: str) -> bool:
        """检查请求中是否已有当前用户的身份提醒。"""
        pattern = re.compile(
            rf"<system_reminder>.*?User ID:\s*{re.escape(user_id)}\s*,\s*Nickname:\s*",
            flags=re.IGNORECASE,
        )

        if req.prompt and pattern.search(req.prompt):
            return True

        if hasattr(req, "extra_user_content_parts") and req.extra_user_content_parts:
            for part in req.extra_user_content_parts:
                text = self._get_textpart_text(part)
                if text and pattern.search(text):
                    return True
        return False

    def _warn_identifier_not_enabled(self):
        """提示用户检查 AstrBot 的用户识别配置。"""
        logger.warning(
            "[uni_nickname] 未检测到 <system_reminder> 身份标签。请检查 AstrBot 设置中是否已开启用户识别（provider_settings.identifier）。"
        )

    def _system_replace_in_contexts(self, contexts: list, mappings: dict):
        """遍历 contexts，对每条消息的内容应用智能替换"""
        if not contexts:
            return
        replace_count = 0
        for i, ctx in enumerate(contexts):
            if not isinstance(ctx, dict):
                continue
            content = ctx.get("content")
            if content is None:
                continue
            if isinstance(content, str):
                new_content = self._system_replace_in_text(content, mappings)
                if new_content != content:
                    ctx["content"] = new_content
                    replace_count += 1
                    logger.debug(f"[uni_nickname] 已智能替换历史记录第 {i} 条消息")
            elif isinstance(content, list):
                modified = False
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        new_text = self._system_replace_in_text(text, mappings)
                        if new_text != text:
                            item["text"] = new_text
                            modified = True
                if modified:
                    replace_count += 1
                    logger.debug(
                        f"[uni_nickname] 已智能替换历史记录第 {i} 条多模态消息"
                    )
        logger.info(
            f"[uni_nickname] 智能替换历史记录执行完毕，共修改 {replace_count} 条消息。"
        )

    def _log_current_user_prompt(self, req: ProviderRequest):
        """测试用，输出当前用户看到的完整输入（合并 prompt、contexts 中的用户消息、extra_user_content_parts）"""
        try:
            all_texts = []

            # 从 prompt 添加
            if req.prompt:
                all_texts.append(req.prompt)

            # 从 contexts 添加最后一条用户消息
            if hasattr(req, "contexts") and req.contexts:
                for ctx in reversed(req.contexts):
                    if isinstance(ctx, dict) and ctx.get("role") == "user":
                        if content := ctx.get("content"):
                            if isinstance(content, str):
                                all_texts.append(content)
                            elif isinstance(content, list):
                                all_texts.extend(
                                    item.get("text", "")
                                    for item in content
                                    if isinstance(item, dict)
                                    and item.get("type") == "text"
                                )
                            else:
                                all_texts.append(str(content))
                        break  # 只取最后一条用户消息

            # 从 extra_user_content_parts 添加
            if (
                hasattr(req, "extra_user_content_parts")
                and req.extra_user_content_parts
            ):
                all_texts.extend(
                    part.text
                    for part in req.extra_user_content_parts
                    if hasattr(part, "text") and part.text
                )
            if all_texts:
                combined = "\n".join(all_texts)
                logger.info(f"[uni_nickname] 当前用户完整输入 (组合): {combined}")
            else:
                logger.info("[uni_nickname] 未找到用户输入")
        except Exception as e:
            logger.error(f"[uni_nickname] 日志输出失败: {e}")

    @filter.on_llm_request()
    async def replace_nickname_in_llm_request(
        self, event: AstrMessageEvent, req: ProviderRequest, *args, **kwargs
    ):
        """在LLM请求前根据配置的模式处理昵称（使用内存缓存）"""
        try:
            tool_set = req.func_tool
            if isinstance(tool_set, FunctionToolManager):
                req.func_tool = tool_set.get_full_tool_set()
                tool_set = req.func_tool

            if tool_set and not self.config.get("enable_llm_tool", False):
                tool_set.remove_tool("set_user_nickname")

            sender_id = event.get_sender_id()
            original_nickname = event.get_sender_name()
            logger.debug(f"[uni_nickname] 收到 LLM 请求拦截，发送者 ID: {sender_id}")

            # 直接使用内存缓存，避免每次请求都进行字符串解析
            mappings = self._mappings_cache

            # 更新原始昵称缓存（无论是否在映射表中）
            # 用于后续在历史记录中替换所有已知用户的昵称
            if sender_id in mappings and original_nickname:
                cached_original = self._original_nickname_cache.get(sender_id)
                if cached_original != original_nickname:
                    if cached_original:
                        logger.debug(
                            f"[uni_nickname] 检测到用户 {sender_id} 原始昵称变更: '{cached_original}' -> '{original_nickname}'，刷新缓存"
                        )
                    self._original_nickname_cache[sender_id] = original_nickname

            if sender_id in mappings:
                custom_nickname = mappings[sender_id]
                logger.info(
                    f"[uni_nickname] 命中映射: {sender_id} -> {custom_nickname} (平台获取到的原始昵称: {original_nickname})"
                )

                # 平台昵称可能为空（部分平台/场景常见），此时仅告警，不终止后续模式处理。
                if not original_nickname:
                    logger.warning(
                        f"[uni_nickname] 无法获取用户 {sender_id} 的原始昵称（Platform Name 为空），将继续执行可用的映射逻辑。"
                    )

                working_mode = self.config.get("working_mode", "system_replace")
                logger.debug(f"[uni_nickname] 当前工作模式: {working_mode}")

                if working_mode == "prompt":
                    # 提示词模式：通过 System Prompt 引导 AI，不修改原始文本
                    # 这样可以避免 "I will" 变成 "I Boss" 的语义问题
                    instruction = textwrap.dedent(f"""
                        [System Note:
                        The platform nickname "{original_nickname}" is only a display name and may contain jokes, roleplay, or references.
                        It does NOT indicate identity, relationships, or references to any real person mentioned in the nickname.
                        
                        The actual identity of the current user (ID: {sender_id}) is "{custom_nickname}".
                        You must treat this user as "{custom_nickname}" in all understanding and responses.
                        
                        If the nickname text conflicts with identity or mentions other names,
                        always ignore the nickname meaning and follow this System Note.]
                    """)
                    if req.system_prompt:
                        req.system_prompt += instruction
                    else:
                        req.system_prompt = instruction
                    logger.debug(
                        f"[uni_nickname] 提示词模式：向 System Prompt 注入昵称引导 ({original_nickname} -> {custom_nickname})"
                    )

                elif working_mode == "system_replace":
                    logger.debug("[uni_nickname] 系统标签替换模式激活")
                    if not self._request_has_identity_reminder(req, sender_id):
                        self._warn_identifier_not_enabled()
                        return
                    # 仅替换系统标签
                    if (
                        hasattr(req, "extra_user_content_parts")
                        and req.extra_user_content_parts
                    ):
                        for part in req.extra_user_content_parts:
                            self._system_replace_in_textpart(part, mappings)
                    if req.prompt:
                        req.prompt = self._system_replace_in_text(req.prompt, mappings)

                elif working_mode == "global_replace":
                    logger.debug("[uni_nickname] 全局替换模式激活")
                    if not self._request_has_identity_reminder(req, sender_id):
                        self._warn_identifier_not_enabled()
                    enable_session = self.config.get("enable_session_replace", False)

                    # 构建传统替换映射
                    replace_map: dict[str, str] = {}
                    for uid, custom_nick in mappings.items():
                        orig_nick = self._original_nickname_cache.get(uid)
                        if orig_nick and orig_nick != custom_nick:
                            replace_map[orig_nick] = custom_nick

                    # 1. 处理 extra_user_content_parts
                    if (
                        hasattr(req, "extra_user_content_parts")
                        and req.extra_user_content_parts
                    ):
                        for part in req.extra_user_content_parts:
                            self._replace_all_in_textpart(part, replace_map)

                    # 2. 处理 req.prompt
                    if req.prompt and replace_map:
                        new_prompt = req.prompt
                        replaced_pairs = []
                        for orig_nick, custom_nick in replace_map.items():
                            if orig_nick in new_prompt:
                                new_prompt = new_prompt.replace(orig_nick, custom_nick)
                                replaced_pairs.append(
                                    f"'{orig_nick}' -> '{custom_nick}'"
                                )
                        if new_prompt != req.prompt:
                            req.prompt = new_prompt
                            logger.info(
                                f"[uni_nickname] 已修改 req.prompt，替换了: {', '.join(replaced_pairs)}"
                            )

                    # 3. 处理 contexts
                    if enable_session and hasattr(req, "contexts") and req.contexts:
                        self._replace_nicknames_in_contexts(req, replace_map)

                        # 测试用，输出完整输入日志
                        # self._log_current_user_prompt(req)


            else:
                logger.debug(f"[uni_nickname] 用户 {sender_id} 不在映射表中，跳过。")

        except Exception as e:
            logger.error(f"处理昵称时出错: {e}")

    def _replace_nicknames_in_contexts(self, req: ProviderRequest, replace_map: dict):
        """在历史记录 (req.contexts) 中替换所有已知用户的昵称（传统模式）"""
        logger.info("[uni_nickname] 历史记录替换已开启，开始扫描 contexts...")

        if not hasattr(req, "contexts") or not req.contexts:
            logger.debug("[uni_nickname] 未发现可替换的历史记录")
            return

        if not replace_map:
            logger.info(
                "[uni_nickname] 原始昵称缓存为空，暂无可替换的昵称映射（用户需先发送过消息）"
            )
            return

        replace_count = 0
        for i, ctx in enumerate(req.contexts):
            if not isinstance(ctx, dict):
                continue

            content = ctx.get("content")
            if content is None:
                continue

            # 处理字符串类型的 content
            if isinstance(content, str):
                new_content = content
                for orig_nick, custom_nick in replace_map.items():
                    if orig_nick in new_content:
                        new_content = new_content.replace(orig_nick, custom_nick)
                if new_content != content:
                    ctx["content"] = new_content
                    replace_count += 1
                    logger.debug(f"[uni_nickname] 已修改历史记录第 {i} 条消息")

            # 处理列表类型的 content（多模态消息）
            elif isinstance(content, list):
                modified = False
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        new_text = text
                        for orig_nick, custom_nick in replace_map.items():
                            if orig_nick in new_text:
                                new_text = new_text.replace(orig_nick, custom_nick)
                        if new_text != text:
                            item["text"] = new_text
                            modified = True
                if modified:
                    replace_count += 1
                    logger.debug(f"[uni_nickname] 已修改历史记录第 {i} 条多模态消息")

        logger.info(
            f"[uni_nickname] 历史记录替换执行完毕，共修改 {replace_count} 条消息。"
        )

    @filter.llm_tool(name="set_user_nickname")
    async def set_user_nickname_tool(
        self,
        event: AstrMessageEvent,
        nickname: str,
    ) -> str:
        """为当前发言人设置统一称呼。

        仅当用户明确要求你以后用某个称呼称呼他/她/TA时才调用。
        该工具会把当前发言人的用户 ID 绑定到指定称呼，供后续对话持续使用。

        Args:
            nickname(string): 要为当前发言人设置的称呼。应当简短、明确，通常是用户刚刚指定你使用的名字、昵称、称谓或代号。
        """
        nickname = nickname.strip()
        if not nickname:
            return "设置失败：称呼不能为空"

        approved, reason = await self._review_nickname_by_ai(event, nickname)
        if not approved:
            logger.info(f"[uni_nickname] LLM 昵称审核未通过: nickname={nickname}, reason={reason}")
            return f"审核不通过：{reason}"

        user_id = event.get_sender_id()
        self._set_nickname_mapping(user_id, nickname)
        logger.info(f"[uni_nickname] LLM 已设置昵称映射: {user_id} -> {nickname}")
        return f"已为当前发言人设置统一称呼：{nickname}。后续对话请使用这个称呼称呼该用户"

    # 以下命令组保持不变
    @filter.command_group("nickname")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def nickname_group(self):
        """昵称管理指令组（仅管理员）"""
        pass

    @nickname_group.command("set")
    async def set_nickname(self, event: AstrMessageEvent, user_id: str, nickname: str):
        """
        设置用户昵称映射
        用法: /nickname set <用户ID> <昵称>
        """
        try:
            self._set_nickname_mapping(user_id, nickname)

            yield event.plain_result(f"✅ 已设置用户 {user_id} 的昵称为: {nickname}")
            logger.info(f"[uni_nickname] 管理员设置昵称映射: {user_id} -> {nickname}")
        except Exception as e:
            yield event.plain_result(f"❌ 设置失败: {str(e)}")
            logger.error(f"设置昵称映射失败: {e}")

    @nickname_group.command("setme")
    async def set_my_nickname(self, event: AstrMessageEvent, nickname: str):
        """
        为当前用户设置昵称
        用法: /nickname setme <昵称>
        """
        try:
            user_id = event.get_sender_id()

            self._set_nickname_mapping(user_id, nickname)

            yield event.plain_result(f"✅ 已将您的昵称设置为: {nickname}")
            logger.info(f"管理员为自己设置昵称: {user_id} -> {nickname}")
        except Exception as e:
            yield event.plain_result(f"❌ 设置失败: {str(e)}")
            logger.error(f"设置昵称失败: {e}")

    @nickname_group.command("remove")
    async def remove_nickname(self, event: AstrMessageEvent, user_id: str):
        """
        删除用户昵称映射
        用法: /nickname remove <用户ID>
        """
        try:
            nickname = self._remove_nickname_mapping(user_id)

            if nickname is not None:

                yield event.plain_result(
                    f"✅ 已删除用户 {user_id} 的昵称映射（原昵称: {nickname}）"
                )
                logger.info(f"管理员删除昵称映射: {user_id}")
            else:
                yield event.plain_result(f"⚠️ 用户 {user_id} 没有设置昵称映射")
        except Exception as e:
            yield event.plain_result(f"❌ 删除失败: {str(e)}")
            logger.error(f"删除昵称映射失败: {e}")

    @nickname_group.command("list")
    async def list_nicknames(self, event: AstrMessageEvent):
        """
        查看所有昵称映射
        用法: /nickname list
        """
        try:
            mappings = self._parse_mappings()
            if not mappings:
                yield event.plain_result("📋 当前没有任何昵称映射")
                return

            # 构建列表消息
            result = "📋 昵称映射列表:\n" + "=" * 30 + "\n"
            for i, (user_id, nickname) in enumerate(mappings.items(), 1):
                result += f"{i}. {user_id} → {nickname}\n"
            result += "=" * 30 + f"\n共 {len(mappings)} 个映射"

            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
            logger.error(f"查询昵称映射失败: {e}")

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("统一昵称插件已卸载")
