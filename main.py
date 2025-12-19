from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.provider import ProviderRequest


@register("uni_nickname", "Hakuin123", "统一昵称插件 - 使用管理员配置的映射表统一用户昵称", "1.0.0")
class UniNicknamePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._mappings_cache = self._parse_mappings()
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
    async def replace_nickname_in_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """在LLM请求前根据配置的模式处理昵称（使用内存缓存）"""
        try:
            sender_id = event.get_sender_id()
            
            # 直接使用内存缓存，避免每次请求都进行字符串解析
            mappings = self._mappings_cache
            
            if sender_id in mappings:
                custom_nickname = mappings[sender_id]
                original_nickname = event.get_sender_name()
                
                # 安全性检查：如果原始昵称不存在或为空字符串，跳过处理，防止 replace("", "...") 引发 Bug
                if not original_nickname:
                    logger.warning(f"无法获取用户 {sender_id} 的原始昵称，跳过映射处理。")
                    return

                working_mode = self.config.get("working_mode", "safe")
                
                if working_mode == "safe":
                    # 安全模式：通过 System Prompt 引导 AI，不修改原始文本
                    # 这样可以避免 "I will" 变成 "I Boss" 的语义问题
                    instruction = f"\n[System Note: The current user '{original_nickname}' (ID: {sender_id}) should be addressed as '{custom_nickname}'. Please use this custom nickname when responding to them.]\n"
                    if req.system_prompt:
                        req.system_prompt += instruction
                    else:
                        req.system_prompt = instruction
                    logger.debug(f"安全模式：向 System Prompt 注入昵称引导 ({original_nickname} -> {custom_nickname})")
                
                elif working_mode == "global":
                    # 全局替换模式：高风险
                    logger.warning(f"全局替换模式激活：正在修改用户 {sender_id} 的原始请求文本内容。")
                    
                    if req.prompt:
                        req.prompt = req.prompt.replace(original_nickname, custom_nickname)
                    
                    # 仅在用户显式开启时才修改历史记录
                    if self.config.get("enable_session_replace", False):
                        if hasattr(req, 'session') and req.session:
                            for msg in req.session:
                                if hasattr(msg, 'content') and isinstance(msg.content, str):
                                    msg.content = msg.content.replace(original_nickname, custom_nickname)
                            logger.debug("历史记录替换已执行")
                
        except Exception as e:
            logger.error(f"处理昵称时出错: {e}")


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
