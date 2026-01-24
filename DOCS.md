# AI Hub TTS 用户文档

基于 Kokoro 多语言模型的离线语音合成 Home Assistant 加载项，支持中英文语音合成，兼容 Wyoming 协议。

## 特性

- 🔇 **完全离线** - 无需联网，本地推理
- 🌍 **多语言支持** - 中文、英文自动检测
- 🎤 **26种音色** - 丰富的音色选择
- ⚡ **高性能** - CPU 推理，<1秒生成
- 🔌 **Wyoming 协议** - 自动发现，即插即用
- 💾 **低内存** - 运行内存 <500MB

## 安装

1. 在 Home Assistant 中添加本仓库为加载项仓库
2. 安装 AI Hub TTS 加载项
3. 启动加载项（首次启动会自动下载模型，约500MB）
4. 在 Home Assistant 设置 > 语音助手 中配置 TTS

## 配置选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `voice` | string | `af_heart` | 音色选择 |
| `sample_rate` | int | `24000` | 采样率 |
| `debug` | bool | `false` | 调试模式 |

## 全部音色列表

Kokoro 模型提供 26 种音色，命名规则: `{语言}{性别}_{名称}`

| 前缀 | 含义 |
|------|------|
| a | American English (美式英语) |
| b | British English (英式英语) |
| e | European Mixed (欧洲混合) |
| f | French (法语) |
| h | Hindi (印地语) |
| i | Italian (意大利语) |
| j | Japanese/Asian (日语/亚洲) |
| f/m | Female/Male (女/男) |

### 多语言女声

| 音色ID | 推荐场景 |
|--------|----------|
| `af_heart` | 默认音色，温柔自然 |
| `af_bella` | 甜美活泼 |
| `bf_emma` | 英式优雅 |
| `ef_dora` | 欧式温婉 |
| `ff_nicole` | 法式柔美 |
| `ff_siwu` | 法式清新 |
| `hf_alpha` | 印式温柔 |
| `hf_beta` | 印式活力 |
| `if_nicole` | 意式甜美 |
| `jf_nezumi` | 日系可爱 |
| `jf_xiaobei` | 中文小贝 |
| `jf_xiaoxiao` | 中文晓晓 (推荐中文) |
| `jf_takeru` | 日系少女 |

### 多语言男声

| 音色ID | 推荐场景 |
|--------|----------|
| `am_michael` | 美式稳重 |
| `am_adam` | 美式磁性 (推荐英文) |
| `bf_george` | 英式绅士 |
| `bm_george` | 英式沉稳 |
| `bm_lewis` | 英式活力 |
| `em_alex` | 欧式阳光 |
| `fm_dora` | 法式温和 |
| `fm_sarah` | 法式柔和 |
| `hm_omega` | 印式低沉 |
| `hm_psi` | 印式浑厚 |
| `im_siyu` | 意式成熟 |
| `jf_yunjian` | 中文云间 (推荐中文) |
| `jm_kumo` | 日系少年 |

## Wyoming 自动发现

本加载项支持 Wyoming 协议的 mDNS 自动发现。启动后，Home Assistant 会自动检测并配置 TTS 服务。

- 服务名称: `ai_hub_tts._wyoming._tcp.local.`
- 端口: `10301`

## 技术规格

| 规格 | 数值 |
|------|------|
| 推理引擎 | sherpa-onnx |
| 模型 | Kokoro Multi-Lang v1.0 |
| 协议 | Wyoming Protocol |
| 采样率 | 24000 Hz |
| 位深 | 16-bit |
| 声道 | 单声道 |

## 故障排查

### 首次启动很慢

首次启动需要下载约500MB的模型文件，请耐心等待。日志会显示下载进度。

### 找不到TTS服务

1. 确保加载项已启动（查看日志确认 "Server is READY"）
2. 检查 Home Assistant 设置 > 集成 > Wyoming
3. 如果没有自动发现，手动添加: `localhost:10301`

### 内存不足

系统需要至少1GB可用内存。v1.0.5版本采用单模型架构，运行内存约300-400MB。

### 语音生成慢

- 检查CPU使用率，确保没有其他高负载任务
- 短句(<20字)通常在0.5秒内完成
- 长句会自动分割流式输出

## 开源协议

MIT License
