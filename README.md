# astrbot-plugin-voice-control

> 接管 AstrBot 的 TTS：**文字回复照常分段成短气泡，语音回复永远是一整条**；用户明确要求说话时必发语音。

[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.24-blue)](https://github.com/AstrBotDevs/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

---

## 它解决什么

AstrBot 原生 TTS 有两个让人别扭的地方：

**① 一条回复会变成好几条碎语音**

原生处理顺序是「先分段 → 再逐段 TTS」：

```
on_decorating_result (插件钩子)
        ↓
segmented_reply       ← 按句号切开成 2~3 段
        ↓
TTS                   ← 每段单独合成 → 2~3 条语音
```

而且分段阈值的语义是反的：`if len(text) > words_count_threshold: 不分段` —— **阈值越大越容易分段**。

**② "叫她说话"和"默认低概率发语音"互相打架**

`trigger_probability` 是全局随机概率。设低了日常不吵，但用户明确说"说句话"时也照样按概率——可能连说三次都不发。

---

## 方案：把 TTS 从概率里接管过来

```python
全局 provider_tts_settings.trigger_probability = 0    # 关掉原生 TTS
```

然后由本插件在 `on_decorating_result`（**早于分段与 TTS**）自己决定：

```
要发语音 → 先把所有纯文本段合并成一句 → 合成 1 条 Record
         → 此时链里已无 Plain，分段阶段无内容可切 → 一条语音
不发语音 → 什么都不做 → 分段阶段正常把文字切短气泡
```

结果：

| 场景 | 效果 |
|---|---|
| 普通回复（默认 97%） | 文字，**照常分段**成多条短气泡 |
| 普通回复（默认 3%） | **一整条语音**，不碎 |
| 用户说"说句话 / 发语音 / 念一下" | **必定一整条语音**（100%，无视概率） |
| 用户发 `/语音关` 后 | 彻底不发语音（可配置是否让触发词越权） |

---

## 安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/<you>/astrbot-plugin-voice-control.git astrbot_plugin_voice_control
```

> 目录名必须是 `astrbot_plugin_voice_control`。安装后**先把全局触发概率设为 0**：
> 面板 → 配置 → 语音合成（`provider_tts_settings.trigger_probability = 0`），否则两套逻辑会叠加（小概率双发）。

---

## 配置

| 配置项 | 默认 | 说明 |
|---|---|---|
| `enable` | `true` | 插件总开关 |
| `probability` | `0.03` | 普通回复发语音的概率 |
| `keywords` | 见下 | 命中即必发语音（逗号分隔） |
| `keep_text` | `false` | 概率命中时是否也附文字 |
| `keyword_keep_text` | `false` | 叫她说时是否也附文字 |
| `respect_session_switch` | `true` | 遵守会话级语音开关（`/语音关`） |
| `keyword_ignore_session_switch` | `false` | 触发词是否能越过 `/语音关` |

默认触发词：

```
说句话,发语音,来一句,念一下,念给我听,听你声音,听听你的声音,
语音条,叫一声,喊我一声,说给我听,用语音,发条语音
```

---

## 和其他语音相关配置的关系

| 配置 | 谁在用 | 说明 |
|---|---|---|
| `provider_tts_settings.enable` | AstrBot 原生 | 需要保持 `true`（用来提供 TTS provider 实例） |
| `provider_tts_settings.trigger_probability` | AstrBot 原生 | **必须设 0**，把决定权交给本插件 |
| `provider_tts_settings.dual_output` | AstrBot 原生 | 设 `false`，否则语音后面又跟一条原文 |
| `segmented_reply.words_count_threshold` | AstrBot 原生 | 保持你想要的文字分段效果即可；语音不受影响 |
| 本插件 `probability` | 本插件 | 真正的"日常语音概率" |

会话级开关（`/语音开` `/语音关`）由别的插件或内置指令维护，本插件只读它。

---

## 已知边界

- 语音合成失败时**回落为文字**，不会静默失败
- 合并多段时用 `"".join()` 直接拼接；如果段与段之间需要标点，请让人格本身带标点（片段是带标点切出来的，通常不缺）
- 本插件只处理**纯文本段**；图片/表情等非文本元素原样保留
- 依赖 `on_decorating_result` 早于 TTS 执行这一顺序；AstrBot 若调整管线顺序需复核

---

## Design

- 单一职责：只决定"这条回复要不要语音、语音多长"，不管音色、不管额度
- 无状态：不在磁盘留任何东西
- 可降级：没有 TTS provider 时什么都不做，文字照常发

---

## License

MIT

---

## English (short)

Take over AstrBot's TTS so that **text replies still split into short bubbles while voice replies are always a single clip**. Also guarantees 100% voice when the user explicitly asks to speak, regardless of the global probability.

Set `provider_tts_settings.trigger_probability = 0` after installing; this plugin performs its own roll and merges text segments before synthesising.