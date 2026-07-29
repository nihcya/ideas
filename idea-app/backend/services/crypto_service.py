"""对称加密服务 — 用于用户 LLM API Key 的加密存储

使用 Fernet (AES-128-CBC + HMAC-SHA256) 加密。
密钥从环境变量 LLM_KEY_ENCRYPTION_KEY 读取。
"""
from cryptography.fernet import Fernet
from config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.llm_key_encryption_key:
            raise RuntimeError("LLM_KEY_ENCRYPTION_KEY 未设置")
        key = settings.llm_key_encryption_key
        if isinstance(key, str):
            key = key.encode()
        _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    """加密明文，返回密文（base64 字符串）。空字符串原样返回。"""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """解密密文，返回明文。空字符串或解密失败返回空。"""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""  # 解密失败返回空，让 LLM 调用走 Mock
