# Changelog

## [Unreleased]

## [2.0.0] - 2026-11-07

### Added
- 接管 TTS：文字回复照常分段，语音回复合并为一整条
- 触发词机制：命中则必发语音，绕开概率
- 会话开关联动：遵守 `/语音关`
- 配置项：`probability` / `keywords` / `keep_text` / `keyword_keep_text` /
  `respect_session_switch` / `keyword_ignore_session_switch`

## [1.0.0] - 2026-11-06

### Added
- 初版：被要求说话时强制发语音（`on_decorating_result` 早于 TTS 执行）