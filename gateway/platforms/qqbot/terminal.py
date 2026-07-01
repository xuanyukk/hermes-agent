"""
QQ Bot 终端显示模块 — 真寻 Bot 风格的流式终端输出。

在网关前台运行时，以彩色框线格式实时显示消息收发，
借鉴绪山真寻 Bot 的终端输出风格。

用法:
    from gateway.platforms.qqbot.terminal import QQTerminal

    term = QQTerminal(app_id="102xxxxx")
    term.on_receive(user_name="小明", chat_type="group", chat_name="摸鱼群", content="你好")
    term.on_reply_start(user_name="小明", chat_type="group", chat_name="摸鱼群")
    term.on_reply_chunk("你好呀！")
    term.on_reply_chunk("有什么可以帮你的吗？")
    term.on_reply_done()
"""

from __future__ import annotations

import shutil
import sys
import time
from datetime import datetime
from typing import Optional

# colorama 已在项目依赖中(Windows 平台)
try:
    from colorama import Fore, Style, init as colorama_init
    # wrap=True 启用完整 ANSI 转义序列转换(含光标控制),
    # autoreset 不需要 -- 代码中已手动使用 Style.RESET_ALL
    colorama_init(wrap=True)
    _COLORAMA = True
except ImportError:
    _COLORAMA = False
    # 回退: 空字符串占位
    class _NoColor:
        def __getattr__(self, name: str) -> str:
            return ""
    Fore = _NoColor()
    Style = _NoColor()

# ── 终端宽度 ─────────────────────────────────────────────
_TERM_WIDTH = min(shutil.get_terminal_size().columns, 100)


def _timestamp() -> str:
    """简短时间戳，如 22:14:32"""
    return datetime.now().strftime("%H:%M:%S")


def _truncate(text: str, max_len: int = 60) -> str:
    """截断过长文本"""
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _wrap_text(text: str, width: int, indent: str = "│ ") -> str:
    """将长文本按终端宽度折行, 每行带缩进前缀"""
    lines = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.rstrip()
        if not paragraph:
            lines.append(f"{indent}")
            continue
        # 按宽度折行
        avail = width - len(indent) - 2  # 预留右侧 │
        while len(paragraph) > avail:
            # 找合适断点
            cut = avail
            for sep in ("，", "。", "！", "？", " ", ",", ".", "!", "?"):
                pos = paragraph.rfind(sep, 0, avail)
                if pos > avail // 2:
                    cut = pos + 1
                    break
            lines.append(f"{indent}{paragraph[:cut].rstrip()}")
            paragraph = paragraph[cut:].lstrip()
        if paragraph:
            lines.append(f"{indent}{paragraph}")
    return "\n".join(lines)


class QQTerminal:
    """QQ Bot 终端显示器 — 真寻风格流式输出。

    在网关前台运行时, 将消息收发以彩色框线格式实时打印到终端.
    """

    def __init__(self, app_id: str = ""):
        self._app_id = app_id
        self._streaming = False
        self._stream_user = ""
        self._stream_chat_type = ""
        self._stream_chat_name = ""
        self._stream_start_time = 0.0
        self._stream_buffer: list[str] = []
        self._last_line_count = 0
        self._last_flush_time = 0.0
        self._throttle_interval = 0.1  # 100ms 节流间隔

    # ── 消息接收 ─────────────────────────────────────────

    def on_receive(
        self,
        user_name: str,
        chat_type: str,
        chat_name: str,
        content: str,
        *,
        image_count: int = 0,
        voice_count: int = 0,
    ) -> None:
        """打印收到的消息。

        Args:
            user_name: 发送者名称
            chat_type: 聊天类型 (c2c / group)
            chat_name: 聊天名称(群名或"私聊")
            content: 消息文本
            image_count: 图片数量
            voice_count: 语音数量
        """
        ts = _timestamp()
        chat_label = "👤 私聊" if chat_type == "c2c" else f"👥 {chat_name}"
        user_label = _truncate(user_name, 20)
        content_preview = _truncate(content, 60)

        # 附件标记
        extras = []
        if image_count:
            extras.append(f"🖼️×{image_count}")
        if voice_count:
            extras.append(f"🎤×{voice_count}")
        extra_str = " " + " ".join(extras) if extras else ""

        width = _TERM_WIDTH

        if _COLORAMA:
            print(f"{Fore.CYAN}{Style.BRIGHT}┌{'─' * (width - 2)}┐{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{Style.BRIGHT}│{Style.RESET_ALL} {Fore.YELLOW}📩 收到消息{Style.RESET_ALL}  "
                  f"{Fore.WHITE}{ts}{Style.RESET_ALL}  "
                  f"{Fore.GREEN}{chat_label}{Style.RESET_ALL}  "
                  f"{Fore.MAGENTA}{user_label}{Style.RESET_ALL}{extra_str}")
            print(f"{Fore.CYAN}{Style.BRIGHT}├{'─' * (width - 2)}┤{Style.RESET_ALL}")
            # 内容折行
            wrapped = _wrap_text(content, width)
            for line in wrapped.split("\n"):
                print(f"{Fore.CYAN}{Style.DIM}│{Style.RESET_ALL} {Fore.WHITE}{line}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{Style.BRIGHT}└{'─' * (width - 2)}┘{Style.RESET_ALL}")
        else:
            print(f"┌{'─' * (width - 2)}┐")
            print(f"│ 📩 收到消息  {ts}  {chat_label}  {user_label}{extra_str}")
            print(f"├{'─' * (width - 2)}┤")
            wrapped = _wrap_text(content, width)
            for line in wrapped.split("\n"):
                print(f"│ {line}")
            print(f"└{'─' * (width - 2)}┘")

    # ── 回复流式输出 ─────────────────────────────────────

    def on_reply_start(
        self,
        user_name: str,
        chat_type: str,
        chat_name: str,
    ) -> None:
        """开始流式回复 — 打印框线头部。

        Args:
            user_name: 接收者名称
            chat_type: 聊天类型
            chat_name: 聊天名称
        """
        self._streaming = True
        self._stream_user = user_name
        self._stream_chat_type = chat_type
        self._stream_chat_name = chat_name
        self._stream_start_time = time.time()
        self._stream_buffer = []
        self._last_line_count = 0
        self._last_flush_time = 0.0

        ts = _timestamp()
        chat_label = "👤 私聊" if chat_type == "c2c" else f"👥 {chat_name}"
        user_label = _truncate(user_name, 20)
        width = _TERM_WIDTH

        if _COLORAMA:
            print(f"{Fore.GREEN}{Style.BRIGHT}┌{'─' * (width - 2)}┐{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{Style.BRIGHT}│{Style.RESET_ALL} {Fore.YELLOW}📤 发送回复{Style.RESET_ALL}  "
                  f"{Fore.WHITE}{ts}{Style.RESET_ALL}  "
                  f"{Fore.GREEN}{chat_label}{Style.RESET_ALL}  "
                  f"{Fore.MAGENTA}{user_label}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{Style.BRIGHT}├{'─' * (width - 2)}┤{Style.RESET_ALL}")
        else:
            print(f"┌{'─' * (width - 2)}┐")
            print(f"│ 📤 发送回复  {ts}  {chat_label}  {user_label}")
            print(f"├{'─' * (width - 2)}┤")

    def on_reply_chunk(self, text: str) -> None:
        """追加流式文本块 — 实时更新终端。

        在流式模式下, 每个 chunk 追加到缓冲区.
        通过节流(100ms 间隔)减少终端刷新频率, 避免刷屏.
        """
        if not self._streaming:
            return
        self._stream_buffer.append(text)

        # 节流: 距上次刷新不足 throttle_interval 则跳过
        now = time.time()
        if now - self._last_flush_time < self._throttle_interval:
            return
        self._last_flush_time = now

        self._flush_stream()

    def _flush_stream(self) -> None:
        """将缓冲区内容刷新到终端(原地更新)."""
        full_text = "".join(self._stream_buffer)
        width = _TERM_WIDTH

        # 清除之前打印的行(用 ANSI 上移 + 清行)
        if self._last_line_count > 0:
            for _ in range(self._last_line_count):
                sys.stdout.write("\033[F")  # 上移一行
                sys.stdout.write("\033[2K")  # 清除当前行

        # 重新打印所有内容行
        wrapped = _wrap_text(full_text, width)
        lines = wrapped.split("\n")
        self._last_line_count = len(lines)

        if _COLORAMA:
            for line in lines:
                print(f"{Fore.GREEN}{Style.DIM}│{Style.RESET_ALL} {Fore.WHITE}{line}{Style.RESET_ALL}")
        else:
            for line in lines:
                print(f"│ {line}")

        sys.stdout.flush()

    def on_reply_done(self, *, success: bool = True, error: str = "") -> None:
        """结束流式回复 — 打印框线底部和耗时。

        Args:
            success: 是否发送成功
            error: 失败时的错误信息
        """
        if not self._streaming:
            return

        # 最终刷新(确保所有缓冲内容都被打印)
        self._flush_stream()

        elapsed = time.time() - self._stream_start_time
        width = _TERM_WIDTH

        if success:
            status = f"✅ 发送成功 · {elapsed:.1f}s"
            color = Fore.GREEN if _COLORAMA else ""
        else:
            status = f"❌ 发送失败 · {elapsed:.1f}s"
            color = Fore.RED if _COLORAMA else ""
            if error:
                status += f"  [{_truncate(error, 40)}]"

        if _COLORAMA:
            print(f"{color}{Style.BRIGHT}└{'─' * (width - 2)}┘{Style.RESET_ALL}")
            print(f"  {color}{status}{Style.RESET_ALL}")
        else:
            print(f"└{'─' * (width - 2)}┘")
            print(f"  {status}")

        self._streaming = False
        self._stream_buffer = []
        self._last_line_count = 0

    def on_reply_abort(self, reason: str = "") -> None:
        """中止流式回复(如被拦截或出错)."""
        if not self._streaming:
            return
        self.on_reply_done(success=False, error=reason or "已中止")

    # ── 系统事件 ─────────────────────────────────────────

    def on_connect(self) -> None:
        """网关连接成功"""
        ts = _timestamp()
        if _COLORAMA:
            print(f"  {Fore.GREEN}{Style.BRIGHT}🔗 网关已连接{Style.RESET_ALL}  "
                  f"{Fore.WHITE}{ts}{Style.RESET_ALL}  "
                  f"{Fore.CYAN}QQBot:{self._app_id}{Style.RESET_ALL}")
        else:
            print(f"  🔗 网关已连接  {ts}  QQBot:{self._app_id}")

    def on_disconnect(self, reason: str = "") -> None:
        """网关断开连接"""
        ts = _timestamp()
        msg = f"🔌 网关已断开  {ts}"
        if reason:
            msg += f"  [{reason}]"
        if _COLORAMA:
            print(f"  {Fore.YELLOW}{msg}{Style.RESET_ALL}")
        else:
            print(f"  {msg}")

    def on_startup(self) -> None:
        """网关启动"""
        ts = _timestamp()
        width = _TERM_WIDTH
        if _COLORAMA:
            print(f"{Fore.MAGENTA}{Style.BRIGHT}{'═' * width}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}{Style.BRIGHT}  🚀 小夜 QQ Bot 网关启动{Style.RESET_ALL}  "
                  f"{Fore.WHITE}{ts}{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}{Style.BRIGHT}{'═' * width}{Style.RESET_ALL}")
        else:
            print(f"{'═' * width}")
            print(f"  🚀 小夜 QQ Bot 网关启动  {ts}")
            print(f"{'═' * width}")

    def on_shutdown(self) -> None:
        """网关关闭"""
        ts = _timestamp()
        if _COLORAMA:
            print(f"  {Fore.YELLOW}👋 网关已关闭  {ts}{Style.RESET_ALL}")
        else:
            print(f"  👋 网关已关闭  {ts}")