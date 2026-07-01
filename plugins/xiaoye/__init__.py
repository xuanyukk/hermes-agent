# -*- coding: utf-8 -*-
"""
薄代理层 — 将 Hermes 插件调用转发到 xiaoye 独立包。
这是 hermes-agent 仓库中唯一需要的小夜相关文件。
"""
import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger("xiaoye.proxy")

# 优先使用环境变量，回退到相对于 hermes-agent 的兄弟目录
_XIAOYE_PKG = Path(os.environ.get(
    "XIAOYE_HOME",
    str(Path(__file__).resolve().parent.parent.parent.parent.parent / "xiaoye"),
))
if _XIAOYE_PKG.is_dir() and str(_XIAOYE_PKG) not in sys.path:
    sys.path.insert(0, str(_XIAOYE_PKG))
    logger.debug("xiaoye package added to sys.path: %s", _XIAOYE_PKG)


def register(ctx):
    """转发到 xiaoye 包的 register()"""
    import xiaoye
    xiaoye.register(ctx)
