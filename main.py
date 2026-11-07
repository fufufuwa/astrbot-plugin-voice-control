"""语音总控（接管 AstrBot 的 TTS，实现"文字照常分段 / 语音只发一整条"）。

设计：
- 全局 `provider_tts_settings.trigger_probability` 设为 0，让 AstrBot 原生 TTS 永不触发；
- 本插件在 `on_decorating_result`（早于分段与 TTS）里自己决定：
  1) 用户消息命中触发词 → 必定语音（受会话开关约束，可配）
  2) 否则按 `probability` 掷骰子
- 要发语音时：把所有纯文本段**合并成一句**再合成，链里只留 1 个 Record
  → 一条回复 = 一整条语音，文字不再被切段（因为没有 Plain 了）
- 不发语音时：什么都不做，AstrBot 照常按 `segmented_reply` 切气泡 → 文字回复保持多条气泡
"""

import random
import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Plain, Record
from astrbot.core.star.session_llm_manager import SessionServiceManager


@register(
    "astrbot_plugin_voice_control",
    "anonymous",
    "语音总控：文字照常分段，语音只发一整条；叫她说则必语音",
    "2.0.0",
    "local",
)
class VoiceControlPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}

    # ---------- 配置读取 ----------
    def _cfg(self) -> dict:
        return self.config or {}

    def _keywords(self) -> list[str]:
        raw = self._cfg().get("keywords") or ""
        parts = re.split(r"[,，\n]+", raw) if isinstance(raw, str) else list(raw)
        return [p.strip() for p in parts if p.strip()]

    def _probability(self) -> float:
        try:
            p = float(self._cfg().get("probability", 0.03))
        except (TypeError, ValueError):
            p = 0.03
        return max(0.0, min(p, 1.0))

    @filter.on_decorating_result()
    async def control_voice(self, event: AstrMessageEvent):
        if not self._cfg().get("enable", True):
            return

        result = event.get_result()
        if not result or not result.is_llm_result():
            return

        try:
            user_text = event.message_str or ""
        except Exception:
            user_text = ""

        kws = self._keywords()
        hit = any(k in user_text for k in kws) if user_text else False

        # 会话级开关（/语音关 时不发语音）
        session_on = True
        if self._cfg().get("respect_session_switch", True):
            try:
                session_on = await SessionServiceManager.is_tts_enabled_for_session(
                    event.unified_msg_origin
                )
            except Exception:
                session_on = True

        if not session_on and not (hit and self._cfg().get("keyword_ignore_session_switch", False)):
            return

        if not hit and random.random() >= self._probability():
            return  # 不语音：交给 AstrBot 正常分段发文字

        # ---- 要发语音：先把所有文本段合并 ----
        texts = []
        kept = []
        for comp in result.chain:
            if isinstance(comp, Plain):
                if comp.text.strip():
                    texts.append(comp.text.strip())
            else:
                kept.append(comp)
        merged = "".join(texts)
        if not merged:
            return

        tts = await self.context.get_using_tts_provider_async(event.unified_msg_origin)
        if not tts:
            logger.warning("[voice_control] 需要语音但没有可用的 TTS provider，回落文字")
            return

        try:
            audio_path = await tts.get_audio(merged)
        except Exception as e:
            logger.error(f"[voice_control] 合成失败，回落文字: {e}")
            return
        if not audio_path:
            logger.warning("[voice_control] 合成返回空，回落文字")
            return

        new_chain = list(kept)
        new_chain.append(Record(file=audio_path, url=audio_path, text=merged))
        if self._cfg().get("keep_text", False) or hit and self._cfg().get("keyword_keep_text", False):
            new_chain.append(Plain(merged))
        result.chain = new_chain
        logger.info(
            f"[voice_control] 语音发送（{'命中触发词' if hit else '概率命中'}），"
            f"合并 {len(texts)} 段为 1 条，长度 {len(merged)}"
        )