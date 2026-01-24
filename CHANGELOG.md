# Changelog

All notable changes to this project will be documented in this file.

## [1.0.4] - 2026-01-24

### Added

- Configurable `speed` parameter (0.5-2.0)
- Ultra-fine text splitting for lower latency
- Pipeline parallel synthesis
- Model warmup at startup

### Changed

- Slug renamed to `ai-hub-tts` (kebab-case standard)

### Performance

- First-byte latency: ~0.3-0.5s
- Streaming synthesis for long text

---

## [1.0.3] - 2026-01-24

### Added

- Ultra-Low Latency Mode with 6 optimizations
- Short text fast path

---

## [1.0.2] - 2026-01-24

### Fixed

- Voice option uses CLI argument
- Sample rate configurable via CLI

---

## [1.0.1] - 2026-01-23

### Added

- Complete Home Assistant Addon structure
- Wyoming protocol auto-discovery (mDNS)
- 26 voice presets

---

## [1.0.0] - 2026-01-23

### Initial Release

- Basic Wyoming TTS server
- Kokoro model integration
- Chinese and English support
