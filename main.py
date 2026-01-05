from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.provider import ProviderRequest
import textwrap


@register("uni_nickname", "Hakuin123", "统一昵称插件 - 使用管理员配置的映射表统一用户昵称", "1.1.0")
class UniNicknamePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
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
        mapping_list = [f"{user_id},{nickname}" for user_id, nickname in mappings.items()]
        self.config["nickname_mappings"] = mapping_list
        self.config.save_config()
        # 同步更新内存缓存，确保下一次 LLM 请求立即生效
        self._mappings_cache = mappings

    @filter.on_llm_request()
    async def replace_nickname_in_llm_request(self, event: AstrMessageEvent, req: ProviderRequest, *args, **kwargs):
        """在LLM请求前根据配置的模式处理昵称（使用内存缓存）"""
        try:
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
                        logger.debug(f"[uni_nickname] 检测到用户 {sender_id} 原始昵称变更: '{cached_original}' -> '{original_nickname}'，刷新缓存")
                    self._original_nickname_cache[sender_id] = original_nickname
            
            if sender_id in mappings:
                custom_nickname = mappings[sender_id]
                
                logger.info(f"[uni_nickname] 命中映射: {sender_id} -> {custom_nickname} (平台获取到的原始昵称: {original_nickname})")
                
                # 安全性检查：如果原始昵称不存在或为空字符串，跳过处理，防止 replace("", "...") 引发 Bug
                if not original_nickname:
                    logger.warning(f"[uni_nickname] 无法获取用户 {sender_id} 的原始昵称（Platform Name 为空），跳过映射处理。")
                    return

                working_mode = self.config.get("working_mode", "prompt")
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
                    logger.debug(f"[uni_nickname] 提示词模式：向 System Prompt 注入昵称引导 ({original_nickname} -> {custom_nickname})")
                
                elif working_mode == "global":
                    # 全局替换模式：高风险
                    logger.debug(f"[uni_nickname] 全局替换模式激活：正在处理用户 {sender_id} ({original_nickname}) 的请求内容。")
                    
                    # 在 prompt 中替换所有已知用户的昵称（包括历史记录中的）
                    # 注意：历史记录通常被格式化进 req.prompt 中，所以需要在 prompt 级别替换
                    if req.prompt:
                        self._replace_all_nicknames_in_prompt(req, mappings)
                    
                    # 仅在用户显式开启时才修改历史记录 (req.contexts)
                    if self.config.get("enable_session_replace", False):
                        self._replace_nicknames_in_contexts(req, mappings)
                
            else:
                logger.debug(f"[uni_nickname] 用户 {sender_id} 不在映射表中，跳过。")
                
        except Exception as e:
            logger.error(f"处理昵称时出错: {e}")

    def _replace_all_nicknames_in_prompt(self, req: ProviderRequest, mappings: dict):
        """在 req.prompt 中替换所有已知用户的昵称（包括历史记录中的）"""
        # 构建替换映射：原始昵称 -> 自定义昵称
        replace_map: dict[str, str] = {}
        for user_id, custom_nickname in mappings.items():
            original_nickname = self._original_nickname_cache.get(user_id)
            if original_nickname and original_nickname != custom_nickname:
                replace_map[original_nickname] = custom_nickname
        
        if not replace_map:
            logger.info("[uni_nickname] 原始昵称缓存为空，暂无可替换的昵称映射（用户需先发送过消息）")
            return
        
        logger.debug(f"[uni_nickname] 准备在 prompt 中替换以下昵称: {replace_map}")
        
        old_prompt = req.prompt
        new_prompt = req.prompt
        replaced_pairs = []
        
        for orig_nick, custom_nick in replace_map.items():
            if orig_nick in new_prompt:
                new_prompt = new_prompt.replace(orig_nick, custom_nick)
                replaced_pairs.append(f"'{orig_nick}' -> '{custom_nick}'")
        
        if new_prompt != old_prompt:
            req.prompt = new_prompt
            logger.info(f"[uni_nickname] 已修改 req.prompt，替换了: {', '.join(replaced_pairs)}")
        else:
            logger.debug("[uni_nickname] req.prompt 中未发现可替换的原始昵称")

    def _replace_nicknames_in_contexts(self, req: ProviderRequest, mappings: dict):
        """在历史记录 (req.contexts) 中替换所有已知用户的昵称"""
        logger.info("[uni_nickname] 历史记录替换已开启，开始扫描 contexts...")
        
        if not hasattr(req, 'contexts') or not req.contexts:
            logger.debug("[uni_nickname] 未发现可替换的历史记录 (req.contexts 为空或不存在)")
            return
        
        # 构建替换映射：原始昵称 -> 自定义昵称
        # 只替换已知的原始昵称（已在缓存中记录过的用户）
        replace_map: dict[str, str] = {}
        for user_id, custom_nickname in mappings.items():
            original_nickname = self._original_nickname_cache.get(user_id)
            if original_nickname and original_nickname != custom_nickname:
                replace_map[original_nickname] = custom_nickname
        
        if not replace_map:
            logger.info("[uni_nickname] 原始昵称缓存为空，暂无可替换的昵称映射（用户需先发送过消息）")
            return
        
        logger.debug(f"[uni_nickname] 准备替换以下昵称映射: {replace_map}")
        
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
        
        logger.info(f"[uni_nickname] 历史记录替换执行完毕，共修改 {replace_count} 条消息。")

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
            # 获取当前映射
            mappings = self._parse_mappings()
            
            # 添加或更新映射
            mappings[user_id] = nickname
            
            # 保存配置
            self._save_mappings(mappings)
            
            yield event.plain_result(f"✅ 已设置用户 {user_id} 的昵称为: {nickname}")
            logger.info(f"管理员设置昵称映射: {user_id} -> {nickname}")
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
            
            # 获取当前映射
            mappings = self._parse_mappings()
            
            # 添加或更新映射
            mappings[user_id] = nickname
            
            # 保存配置
            self._save_mappings(mappings)
            
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
            # 获取当前映射
            mappings = self._parse_mappings()
            
            if user_id in mappings:
                nickname = mappings[user_id]
                del mappings[user_id]
                
                # 保存配置
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
            result = "📋 昵称映射列表:\n"
            result += "=" * 30 + "\n"
            for i, (user_id, nickname) in enumerate(mappings.items(), 1):
                result += f"{i}. {user_id} → {nickname}\n"
            result += "=" * 30 + "\n"
            result += f"共 {len(mappings)} 个映射"
            
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 查询失败: {str(e)}")
            logger.error(f"查询昵称映射失败: {e}")

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("统一昵称插件已卸载")
