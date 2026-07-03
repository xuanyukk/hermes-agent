# hermes-agent cn-localization 分支本地化修改记录

本文件记录 `cn-localization` 分支与上游主线相比的关键修改，便于后续合并上游更新时识别并保留这些定制化内容。

> 当前记录基于合并点 `c0b1d4da6` 之后的 diff。完整对比见：
> ```bash
> git diff c0b1d4da6..HEAD -- gateway/platforms/qqbot/adapter.py hermes_cli/plugins.py config/default.yaml
> ```

---

## 1. 网关启动钩子（gateway:startup）

- **文件**: `hermes_cli/plugins.py`
- **修改**: 在 `VALID_HOOKS` 集合中新增 `"gateway:startup"` 钩子
- **作用**: 允许插件在网关所有平台连接就绪后执行初始化逻辑（例如小夜的薄代理插件可在此时加载额外组件）
- **代码逻辑**:
  ```python
  "gateway:startup",
  # Gateway startup hook. Fired once after all platforms are connected
  # and the gateway is ready to receive messages. Observers only.
  # Kwargs: gateway: GatewayRunner, platforms: list[str].
  ```

---

## 2. QQAdapter.connect 签名调整

- **文件**: `gateway/platforms/qqbot/adapter.py`
- **修改**: `connect()` 方法增加 `is_reconnect` 关键字参数
- **作用**: 兼容网关层在重连场景下的调用约定，避免 TypeError
- **代码逻辑**:
  ```python
  # 修改前
  async def connect(self) -> bool:
  # 修改后
  async def connect(self, *, is_reconnect: bool = False) -> bool:
  ```

---

## 3. QQTerminal 初始化

- **文件**: `gateway/platforms/qqbot/adapter.py`
- **修改**: 在 `QQAdapter.__init__` 末尾惰性初始化 `QQTerminal` 实例
- **作用**: 为后续消息收发、连接状态提供终端显示入口；导入失败时静默降级为 `None`
- **代码逻辑**:
  ```python
  try:
      from gateway.platforms.qqbot.terminal import QQTerminal
      self._term = QQTerminal(app_id=self._app_id)
  except Exception:
      self._term = None
  ```

---

## 4. 网关连接状态终端回调

- **文件**: `gateway/platforms/qqbot/adapter.py`
- **修改**: 在 `connect()` 成功与 `disconnect()` 中调用终端回调
- **作用**: 在网关前台运行时以真寻风格彩色框线打印 "网关已连接 / 已断开"
- **代码逻辑**:
  ```python
  # connect() 成功分支
  if self._term:
      try:
          self._term.on_connect()
      except Exception:
          pass

  # disconnect() 末尾
  if self._term:
      try:
          self._term.on_disconnect()
      except Exception:
          pass
  ```

---

## 5. 入站消息终端显示

- **文件**: `gateway/platforms/qqbot/adapter.py`
- **修改**: 在 `handle_message()` 中缓存消息 ID 后调用 `on_receive`
- **作用**: 收到 QQ 私聊/群聊消息时，实时打印 "收到消息" 彩色框线面板
- **代码逻辑**:
  ```python
  if self._term:
      try:
          self._term.on_receive(
              user_name=event.source.user_name or (event.source.user_id or "")[:12],
              chat_type=event.source.chat_type or "",
              chat_name=(event.source.chat_id or "")[:20],
              content=event.text or "",
          )
      except Exception:
          pass
  ```

---

## 6. 出站回复流式终端显示

- **文件**: `gateway/platforms/qqbot/adapter.py`
- **修改**: 在 `send()` 方法中分块发送文本时，调用 `on_reply_start / on_reply_chunk / on_reply_done`
- **作用**: AI 回复发送前打印框线头部，每个分块追加到缓冲区并节流刷新，发送结束打印底部与耗时
- **代码逻辑**:
  ```python
  # 发送开始前
  if self._term:
      try:
          self._term.on_reply_start(
              user_name="",
              chat_type=self._guess_chat_type(chat_id),
              chat_name=(chat_id or "")[:20],
          )
      except Exception:
          pass

  # 每个分块
  for chunk in chunks:
      if self._term:
          try:
              self._term.on_reply_chunk(chunk)
          except Exception:
              pass
      last_result = await self._send_chunk(chat_id, chunk, reply_to)
      if not last_result.success:
          if self._term:
              try:
                  self._term.on_reply_done(success=False, error=last_result.error or "")
              except Exception:
                  pass
          return last_result

  # 全部成功
  if self._term:
      try:
          self._term.on_reply_done(success=last_result.success)
      except Exception:
          pass
  ```

---

## 7. QQ Bot DM 会话授权兼容

- **文件**: `gateway/platforms/qqbot/adapter.py`
- **修改**: `_is_authorized_interaction_for_session()` 中对 DM 会话的校验同时接受 `"c2c"` 与 `"dm"`
- **作用**: QQ C2C 私聊在会话键中使用 `chat_type="dm"`，而内部 `_chat_type_map` 保留 `"c2c"` 作为历史键；同时接受两者可确保审批/更新提示按钮在私聊场景中正确授权
- **代码逻辑**:
  ```python
  # QQ Bot DM sessions use chat_type="dm" in the session key (see
  # build_source in _handle_c2c_message / _handle_guild_dm), while the
  # internal _chat_type_map keeps "c2c" for legacy lookups. Accept both
  # so approval/update buttons routed through DM sessions authorize
  # correctly.
  if chat_type in {"c2c", "dm"}:
      return bool(chat_id) and operator == chat_id
  ```

---

## 8. 删除重复的 config/default.yaml

- **文件**: `config/default.yaml`（已删除）
- **修改**: 删除 hermes-agent 根目录下与小夜项目重复的游戏配置文件
- **作用**: 避免用户/部署脚本在错误位置读取到过时的默认配置；小夜的正式配置仍位于 `xiaoye/config/default.yaml`，并通过部署脚本复制到 `~/.hermes/`
- **说明**: 该文件原本包含 `database`、`games`、`persona` 等小夜专属配置，不应存在于 hermes-agent 仓库中

---

## 相关文件

- `gateway/platforms/qqbot/terminal.py`：新增的真寻风格终端显示模块（本分支新增文件，独立维护）

---

## 维护建议

1. 合并上游 `main` 前，先检查 `gateway/platforms/qqbot/adapter.py` 中 `connect()`、`handle_message()`、`send()` 等核心方法是否被重构；若有大幅重构，需要重新插装 QQTerminal 回调。
2. `hermes_cli/plugins.py` 的 `VALID_HOOKS` 集合若上游有更新，注意保留 `"gateway:startup"`。
3. 若上游已原生支持类似的终端消息显示，可考虑将 `terminal.py` 的功能迁移到官方扩展点，减少分支差异。
