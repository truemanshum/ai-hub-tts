# AI Hub TTS

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Addon-blue.svg)](https://www.home-assistant.io/)
[![Wyoming Protocol](https://img.shields.io/badge/Wyoming-Protocol-green.svg)](https://github.com/rhasspy/wyoming)

基于 Kokoro 多语言模型的离线语音合成 Home Assistant 加载项。

## ✨ 特性

- 🔇 完全离线运行，无需联网
- 🌍 中英文自动检测和切换
- 🎤 26种高质量音色
- ⚡ CPU推理，生成速度<1秒
- 🔌 Wyoming协议，自动发现
- 💾 运行内存<500MB

## 📦 安装

### 方式一：通过仓库安装

1. 在 Home Assistant 中进入 **设置 > 加载项 > 加载项商店**
2. 点击右上角 **⋮** > **存储库**
3. 添加本仓库地址
4. 刷新后安装 **AI Hub TTS**

### 方式二：本地安装

```bash
cd /addons
git clone https://github.com/your-repo/ai-hub-tts.git ai_hub_tts
```

## 🎯 快速开始

1. 安装并启动加载项
2. 首次启动会自动下载模型（约500MB）
3. 进入 **设置 > 语音助手**
4. 选择 **AI Hub TTS** 作为 TTS 引擎

## 🔧 配置

```yaml
voice: af_heart      # 音色选择
sample_rate: 24000   # 采样率
debug: false         # 调试模式
```

## 🎤 推荐音色

| 音色 | 类型 | 语言 |
|------|------|------|
| af_heart | 女声 | 多语言 |
| am_adam | 男声 | 多语言 |
| jf_xiaoxiao | 女声 | 中文优化 |
| jf_yunjian | 男声 | 中文优化 |

[查看全部26种音色 →](DOCS.md#全部音色列表)

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| 模型大小 | ~500MB |
| 运行内存 | <500MB |
| 生成延迟 | <1秒 |
| 采样率 | 24000Hz |

## 📝 开源协议

MIT License
