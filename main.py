import re
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.provider import ProviderRequest
import textwrap
import json

@register("uni_nickname", "Hakuin123", "统一昵称插件 - 使用管理员配置的映射表统一用户昵称", "1.2.0")
class UniNicknamePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._mappings_cache = self._parse_mappings()
        # 运行时缓存：用户ID -> 原始平台昵称
        self._original_nickname_cache: dict[str, str] = {}
        logger.info("统一昵称插件已加载，缓存已初始化")

    def _parse_mappings(self) -> dict:
        """解析配置中的昵称映射列表，返回 {用户ID: 昵称} 字典"""
        mappings = {}
        mapping_list = self.config.get("nickname_mappings", [])
        for item in mapping_list:
            if not isinstance(item, str) or "," not in item:
                continue
            parts = item.split(",", 1)
            if len(parts) == 2:
                user_id = parts[0].strip()
                nickname = parts[1].strip()
                if user_id and nickname:
                    mappings[user_id] = nickname
        return mappings

    def _save_mappings(self, mappings: dict):
        """将映射字典保存到配置文件并更新缓存"""
        mapping_list = [f"{user_id},{nickname}" for user_id, nickname in mappings.items()]
        self.config["nickname_mappings"] = mapping_list
        self.config.save_config()
        self._mappings_cache = mappings

    def _smart_replace_in_text(self, text: str, mappings: dict) -> str:
        """
        智能替换：只替换形如 <system_reminder>...User ID: 123, Nickname: 原始名 中的原始名
        如果该用户ID在 mappings 中，则将 Nickname 替换为自定义昵称
        """
        # 匹配模式：
        # 捕获组1: 从 <system_reminder> 到 "Nickname: " 之前的部分
        # 捕获组2: 用户ID
        # 捕获组3: 原始的 Nickname 值（将被替换）
        pattern = r'(<system_reminder>.*?User ID:\s*(\d+),\s*Nickname:\s*)([^\n]+)'
        
        def replacer(match):
            prefix = match.group(1)   # 包括 <system_reminder>...User ID: xxx, Nickname:
            user_id = match.group(2)  # 用户ID
            original_nick = match.group(3)  # 原始昵称
            if user_id in mappings:
                custom_nick = mappings[user_id]
                if custom_nick != original_nick:
                    logger.debug(f"[uni_nickname] 智能替换：用户 {user_id} 的 Nickname 从 '{original_nick}' 替换为 '{custom_nick}'")
                return prefix + custom_nick
            else:
                return match.group(0)  # 不替换
        
        return re.sub(pattern, replacer, text, flags=re.IGNORECASE)

    def _smart_replace_in_textpart(self, part, mappings: dict) -> bool:
        """对 TextPart 对象应用智能替换，返回是否修改"""
        if not hasattr(part, 'text') or not isinstance(part.text, str):
            return False
        new_text = self._smart_replace_in_text(part.text, mappings)
        if new_text != part.text:
            part.text = new_text
            return True
        return False

    def _replace_all_in_textpart(self, part, replace_map: dict) -> bool:
        """对 TextPart 对象应用全局替换，返回是否修改"""
        if not hasattr(part, 'text') or not isinstance(part.text, str):
            return False
        new_text = part.text
        for orig, custom in replace_map.items():
            if orig in new_text:
                new_text = new_text.replace(orig, custom)
        if new_text != part.text:
            part.text = new_text
            return True
        return False

    def _smart_replace_in_contexts(self, contexts: list, mappings: dict):
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
                new_content = self._smart_replace_in_text(content, mappings)
                if new_content != content:
                    ctx["content"] = new_content
                    replace_count += 1
                    logger.debug(f"[uni_nickname] 已智能替换历史记录第 {i} 条消息")
            elif isinstance(content, list):
                modified = False
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        new_text = self._smart_replace_in_text(text, mappings)
                        if new_text != text:
                            item["text"] = new_text
                            modified = True
                if modified:
                    replace_count += 1
                    logger.debug(f"[uni_nickname] 已智能替换历史记录第 {i} 条多模态消息")
        logger.info(f"[uni_nickname] 智能替换历史记录执行完毕，共修改 {replace_count} 条消息。")

    def _log_current_user_prompt(self, req: ProviderRequest):
        """测试用，输出当前用户看到的完整输入（合并 prompt、contexts 中的用户消息、extra_user_content_parts）"""
        try:
            all_texts = []
            
            # 从 prompt 添加
            if req.prompt:
                all_texts.append(req.prompt)
            
            # 从 contexts 添加最后一条用户消息
            if hasattr(req, 'contexts') and req.contexts:
                for ctx in reversed(req.contexts):
                    if isinstance(ctx, dict) and ctx.get("role") == "user":
                        content = ctx.get("content")
                        if content:
                            if isinstance(content, str):
                                all_texts.append(content)
                            elif isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and item.get("type") == "text":
                                        all_texts.append(item.get("text", ""))
                            else:
                                all_texts.append(str(content))
                        break  # 只取最后一条用户消息
            
            # 从 extra_user_content_parts 添加
            if hasattr(req, 'extra_user_content_parts') and req.extra_user_content_parts:
                for part in req.extra_user_content_parts:
                    if hasattr(part, 'text') and part.text:
                        all_texts.append(part.text)
            
            if all_texts:
                combined = "\n".join(all_texts)
                logger.info(f"[uni_nickname] 当前用户完整输入 (组合): {combined}")
            else:
                logger.info("[uni_nickname] 未找到用户输入")
        except Exception as e:
            logger.error(f"[uni_nickname] 日志输出失败: {e}")

    @filter.on_llm_request()
    async def replace_nickname_in_llm_request(self, event: AstrMessageEvent, req: ProviderRequest, *args, **kwargs):
        try:
            sender_id = event.get_sender_id()
            original_nickname = event.get_sender_name()
            logger.debug(f"[uni_nickname] 收到 LLM 请求拦截，发送者 ID: {sender_id}")

            mappings = self._mappings_cache

            # 更新原始昵称缓存
            if sender_id in mappings and original_nickname:
                cached_original = self._original_nickname_cache.get(sender_id)
                if cached_original != original_nickname:
                    if cached_original:
                        logger.debug(f"[uni_nickname] 检测到用户 {sender_id} 原始昵称变更: '{cached_original}' -> '{original_nickname}'，刷新缓存")
                    self._original_nickname_cache[sender_id] = original_nickname

            if sender_id in mappings:
                custom_nickname = mappings[sender_id]
                logger.info(f"[uni_nickname] 命中映射: {sender_id} -> {custom_nickname} (原始昵称: {original_nickname})")

                if not original_nickname:
                    logger.warning(f"[uni_nickname] 无法获取用户 {sender_id} 的原始昵称，跳过映射处理。")
                    return

                working_mode = self.config.get("working_mode", "prompt")
                logger.debug(f"[uni_nickname] 当前工作模式: {working_mode}")

                if working_mode == "prompt":
                    # 提示词模式
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
                    logger.debug(f"[uni_nickname] 提示词模式：向 System Prompt 注入昵称引导")

                elif working_mode == "global":
                    logger.debug(f"[uni_nickname] 全局替换模式激活")

                    smart = self.config.get("smart_replace", False)
                    enable_session = self.config.get("enable_session_replace", False)

                    # 构建传统替换映射
                    replace_map: dict[str, str] = {}
                    for uid, custom_nick in mappings.items():
                        orig_nick = self._original_nickname_cache.get(uid)
                        if orig_nick and orig_nick != custom_nick:
                            replace_map[orig_nick] = custom_nick

                    # 1. 处理 extra_user_content_parts (包含 system_reminder)
                    if hasattr(req, 'extra_user_content_parts') and req.extra_user_content_parts:
                        for part in req.extra_user_content_parts:
                            if smart:
                                self._smart_replace_in_textpart(part, mappings)
                            else:
                                self._replace_all_in_textpart(part, replace_map)

                    # 2. 处理 req.prompt
                    if smart:
                        if req.prompt:
                            req.prompt = self._smart_replace_in_text(req.prompt, mappings)
                    else:
                        if req.prompt and replace_map:
                            new_prompt = req.prompt
                            replaced_pairs = []
                            for orig_nick, custom_nick in replace_map.items():
                                if orig_nick in new_prompt:
                                    new_prompt = new_prompt.replace(orig_nick, custom_nick)
                                    replaced_pairs.append(f"'{orig_nick}' -> '{custom_nick}'")
                            if new_prompt != req.prompt:
                                req.prompt = new_prompt
                                logger.info(f"[uni_nickname] 已修改 req.prompt，替换了: {', '.join(replaced_pairs)}")

                    # 3. 处理 contexts
                    if enable_session and hasattr(req, 'contexts') and req.contexts:
                        if smart:
                            self._smart_replace_in_contexts(req.contexts, mappings)
                        else:
                            self._replace_nicknames_in_contexts(req, replace_map)

                    # 测试用，输出完整输入日志
                    #self._log_current_user_prompt(req)

            else:
                logger.debug(f"[uni_nickname] 用户 {sender_id} 不在映射表中，跳过。")

        except Exception as e:
            logger.error(f"处理昵称时出错: {e}")

    def _replace_nicknames_in_contexts(self, req: ProviderRequest, replace_map: dict):
        """在历史记录 (req.contexts) 中替换所有已知用户的昵称（传统模式）"""
        logger.info("[uni_nickname] 历史记录替换已开启，开始扫描 contexts...")
        
        if not hasattr(req, 'contexts') or not req.contexts:
            logger.debug("[uni_nickname] 未发现可替换的历史记录")
            return
        
        if not replace_map:
            logger.info("[uni_nickname] 无可替换的昵称映射")
            return
        
        replace_count = 0
        for i, ctx in enumerate(req.contexts):
            if not isinstance(ctx, dict):
                continue
            
            content = ctx.get("content")
            if content is None:
                continue
            
            if isinstance(content, str):
                new_content = content
                for orig_nick, custom_nick in replace_map.items():
                    if orig_nick in new_content:
                        new_content = new_content.replace(orig_nick, custom_nick)
                if new_content != content:
                    ctx["content"] = new_content
                    replace_count += 1
                    logger.debug(f"[uni_nickname] 已修改历史记录第 {i} 条消息")
            
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
        
        logger.info(f"[uni_nickname] 历史记录替换执行完毕，共修改 {replace_count} 条消息。")

    # 以下命令组保持不变
    @filter.command_group("nickname")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def nickname_group(self):
        pass

    @nickname_group.command("set")
    async def set_nickname(self, event: AstrMessageEvent, user_id: str, nickname: str):
        try:
            mappings = self._parse_mappings()
            mappings[user_id] = nickname
            self._save_mappings(mappings)
            yield event.plain_result(f"✅ 已设置用户 {user_id} 的昵称为: {nickname}")
            logger.info(f"管理员设置昵称映射: {user_id} -> {nickname}")
        except Exception as e:
            yield event.plain_result(f"❌ 设置失败: {str(e)}")
            logger.error(f"设置昵称映射失败: {e}")

    @nickname_group.command("setme")
    async def set_my_nickname(self, event: AstrMessageEvent, nickname: str):
        try:
            user_id = event.get_sender_id()
            mappings = self._parse_mappings()
            mappings[user_id] = nickname
            self._save_mappings(mappings)
            yield event.plain_result(f"✅ 已将您的昵称设置为: {nickname}")
            logger.info(f"管理员为自己设置昵称: {user_id} -> {nickname}")
        except Exception as e:
            yield event.plain_result(f"❌ 设置失败: {str(e)}")
            logger.error(f"设置昵称失败: {e}")

    @nickname_group.command("remove")
    async def remove_nickname(self, event: AstrMessageEvent, user_id: str):
        try:
            mappings = self._parse_mappings()
            if user_id in mappings:
                nickname = mappings[user_id]
                del mappings[user_id]
                self._save_mappings(mappings)
                yield event.plain_result(f"✅ 已删除用户 {user_id} 的昵称映射（原昵称: {nickname}）")
                logger.info(f"管理员删除昵称映射: {user_id}")
            else:
                yield event.plain_result(f"⚠️ 用户 {user_id} 没有设置昵称映射")
        except Exception as e:
            yield event.plain_result(f"❌ 删除失败: {str(e)}")
            logger.error(f"删除昵称映射失败: {e}")

    @nickname_group.command("list")
    async def list_nicknames(self, event: AstrMessageEvent):
        try:
            mappings = self._parse_mappings()
            if not mappings:
                yield event.plain_result("📋 当前没有任何昵称映射")
                return
            result = "📋 昵称映射列表:\n" + "=" * 30 + "\n"
            for i, (user_id, nickname) in enumerate(mappings.items(), 1):
                result += f"{i}. {user_id} → {nickname}\n"
            result += "=" * 30 + f"\n共 {len(mappings)} 个映射"
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
            logger.error(f"查询昵称映射失败: {e}")

    async def terminate(self):
        logger.info("统一昵称插件已卸载")
