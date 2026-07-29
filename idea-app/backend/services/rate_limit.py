"""速率限制配置 — 基于 slowapi"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# 按 IP 限流
limiter = Limiter(key_func=get_remote_address)

# 预设限流规则
LOGIN_LIMIT = "10/minute"          # 登录：每分钟 10 次
REGISTER_LIMIT = "5/minute"        # 注册：每分钟 5 次
AI_LIMIT = "10/minute"             # AI 接口：每分钟 10 次
CREATE_LIMIT = "20/minute"         # 创建点子：每分钟 20 次
DEFAULT_LIMIT = "60/minute"        # 默认全局限流：每分钟 60 次
