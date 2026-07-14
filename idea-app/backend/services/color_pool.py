"""色彩池 — 后端唯一颜色分配源"""
import random

# 15色池（明度饱和度都有变化）
COLOR_POOL: list[str] = [
    "#FF6B6B", "#FF8E72", "#FFB347", "#FFE66D", "#C5E8A0",
    "#7FD6A1", "#4ECDC4", "#6EC5E9", "#83A6ED", "#B5A8E8",
    "#C9B1FF", "#FFB6C1", "#FF9EBB", "#D4A5A5", "#A8D8D8",
]


def random_color() -> str:
    """从 COLOR_POOL 真随机分配一个颜色。

    重要：禁止按内容哈希分配，会导致同色=同类的伪分类。
    """
    return random.choice(COLOR_POOL)
