"""Event handler for Wyoming protocol with Kokoro integration.

Optimized for sub-second first-byte latency with:
1. Ultra-fine text splitting (max 15 chars per segment)
2. Pipeline parallel synthesis
3. Model warmup at startup
4. Speed parameter tuning
5. Short text fast path
6. Optimized async chunk sending
"""

import argparse
import asyncio
import logging
import multiprocessing
import time
import re
import numpy as np
from typing import Optional, AsyncGenerator, List
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

try:
    import sherpa_onnx
    SHERPA_ONNX_AVAILABLE = True
except ImportError:
    SHERPA_ONNX_AVAILABLE = False
    logging.error("sherpa-onnx is required but not available")

try:
    from wyoming.tts import Synthesize
    from wyoming.audio import AudioChunk, AudioStart, AudioStop
    from wyoming.event import Event
    from wyoming.info import Describe, Info
    from wyoming.server import AsyncEventHandler
except ImportError:
    _LOGGER.error("wyoming package is required but not available")


# ============================================================================
# OPTIMIZATION 1: Ultra-Fine Text Splitting
# ============================================================================

def split_for_streaming(text: str, max_chars: int = 15) -> List[str]:
    """
    Ultra-fine text splitting for minimum first-byte latency.
    
    Strategy:
    1. Split by sentence delimiters (。！？.!?)
    2. Split by clause delimiters (，、,;；:：)
    3. Force-split long segments by max_chars
    
    Target: Each segment ~10-15 chars for ~0.2-0.4s generation
    """
    if not text or not text.strip():
        return []
    
    text = text.strip()
    
    # Short text: return as-is (fast path)
    if len(text) <= max_chars:
        return [text]
    
    # Step 1: Split by sentence delimiters
    sentence_pattern = r'([。！？.!?\n]+)'
    parts = re.split(sentence_pattern, text)
    
    # Merge delimiters back
    sentences = []
    i = 0
    while i < len(parts):
        seg = parts[i].strip()
        if i + 1 < len(parts) and re.match(sentence_pattern, parts[i + 1]):
            seg += parts[i + 1]
            i += 2
        else:
            i += 1
        if seg:
            sentences.append(seg)
    
    # Step 2: Split each sentence by clause delimiters
    clause_pattern = r'([，、,;；:：]+)'
    clauses = []
    for sentence in sentences:
        if len(sentence) <= max_chars:
            clauses.append(sentence)
        else:
            sub_parts = re.split(clause_pattern, sentence)
            j = 0
            while j < len(sub_parts):
                seg = sub_parts[j].strip()
                if j + 1 < len(sub_parts) and re.match(clause_pattern, sub_parts[j + 1]):
                    seg += sub_parts[j + 1]
                    j += 2
                else:
                    j += 1
                if seg:
                    clauses.append(seg)
    
    # Step 3: Force-split long segments
    result = []
    for clause in clauses:
        if len(clause) <= max_chars:
            result.append(clause)
        else:
            # Split at word boundaries or fixed length
            words = list(clause)
            current = ""
            for char in words:
                if len(current) >= max_chars:
                    result.append(current)
                    current = char
                else:
                    current += char
            if current:
                result.append(current)
    
    # Filter empty and merge very short segments
    final = []
    buffer = ""
    for seg in result:
        seg = seg.strip()
        if not seg:
            continue
        if len(buffer) + len(seg) <= max_chars:
            buffer += seg
        else:
            if buffer:
                final.append(buffer)
            buffer = seg
    if buffer:
        final.append(buffer)
    
    return final if final else [text]


class KokoroEventHandler(AsyncEventHandler):
    """
    Event handler for Wyoming clients with Kokoro TTS.
    
    Optimized for <0.5s first-byte latency.
    """

    # Class-level variables - SINGLE MODEL for memory optimization
    _tts = None
    _current_lang = None
    _initialized = False
    _init_lock = asyncio.Lock()
    _model_dir = None
    _num_threads = None
    _warmed_up = False
    _speed = 1.0  # Speech speed parameter

    @classmethod
    async def initialize_models(cls, cli_args):
        """Initialize TTS at startup with warmup."""
        async with cls._init_lock:
            if cls._initialized:
                return

            _LOGGER.info("=" * 60)
            _LOGGER.info("Initializing Kokoro TTS (Ultra-Low Latency Mode)...")
            _LOGGER.info("=" * 60)

            if not SHERPA_ONNX_AVAILABLE:
                _LOGGER.error("Sherpa-ONNX is required but not available")
                raise RuntimeError("sherpa-onnx package is required")

            try:
                model_path = Path(cli_args.model_path)
                # Use standard Kokoro model
                model_dir = model_path / "kokoro-multi-lang-v1_0"
                cls._model_dir = model_dir
                
                # Store speed parameter
                cls._speed = getattr(cli_args, 'speed', 1.0)

                if not model_dir.exists():
                    raise FileNotFoundError(f"Model path not found: {model_dir}")

                # Use all CPU cores
                cls._num_threads = multiprocessing.cpu_count()
                _LOGGER.info(f"Using {cls._num_threads} CPU threads")

                # Load Chinese model (most common)
                cls._tts = cls._create_tts_instance("zh")
                cls._current_lang = "zh"

                # ============================================================
                # OPTIMIZATION 3: Model Warmup
                # ============================================================
                _LOGGER.info("Warming up model (first inference is slow)...")
                warmup_start = time.perf_counter()
                
                # Run warmup inference to trigger JIT compilation
                await asyncio.to_thread(cls._warmup_inference)
                
                warmup_time = time.perf_counter() - warmup_start
                _LOGGER.info(f"Warmup completed in {warmup_time:.2f}s")
                cls._warmed_up = True

                cls._initialized = True
                _LOGGER.info("=" * 60)
                _LOGGER.info("[OK] Kokoro TTS ready (Ultra-Low Latency Mode)")
                _LOGGER.info("=" * 60)

            except Exception as e:
                _LOGGER.error(f"Failed to initialize Kokoro: {e}", exc_info=True)
                raise

    @classmethod
    def _warmup_inference(cls):
        """Run warmup inference to trigger ONNX JIT compilation."""
        try:
            # Short warmup texts
            cls._tts.generate("你好", sid=0)
            cls._tts.generate("hello", sid=0)
            _LOGGER.debug("Warmup inference completed")
        except Exception as e:
            _LOGGER.warning(f"Warmup failed (non-critical): {e}")

    @classmethod
    def _create_tts_instance(cls, lang: str = None):
        """Create TTS instance (single instance for all languages)."""
        model_dir = cls._model_dir
        
        # Combine all lexicons for multi-language support
        lexicon_files = [
            str(model_dir / "lexicon-us-en.txt"),
            str(model_dir / "lexicon-zh.txt"),
        ]
        lexicon = ",".join(lexicon_files)

        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                    model=str(model_dir / "model.onnx"),
                    voices=str(model_dir / "voices.bin"),
                    tokens=str(model_dir / "tokens.txt"),
                    data_dir=str(model_dir / "espeak-ng-data"),
                    lexicon=lexicon,
                ),
                num_threads=cls._num_threads,
                debug=False,
                provider="cpu",
            ),
        )
        
        _LOGGER.info(f"Creating TTS instance with lexicons: {lexicon}")
        return sherpa_onnx.OfflineTts(config)

    @classmethod
    def _get_tts(cls, lang: str):
        """Get TTS instance, switching language if needed."""
        if cls._current_lang != lang:
            _LOGGER.info(f"Switching language: {cls._current_lang} -> {lang}")
            start = time.perf_counter()
            cls._tts = cls._create_tts_instance(lang)
            cls._current_lang = lang
            elapsed = time.perf_counter() - start
            _LOGGER.info(f"Language switch: {elapsed:.2f}s")
        return cls._tts

    def __init__(
        self,
        wyoming_info: Info,
        cli_args: argparse.Namespace,
        *args,
        **kwargs,
    ) -> None:
        """Initialize handler."""
        super().__init__(*args, **kwargs)
        self.cli_args = cli_args
        self.wyoming_info_event = wyoming_info.event()
        self._sample_rate = getattr(cli_args, 'sample_rate', 24000)
        self._sample_width = 2
        self._channels = 1
        self._default_voice = getattr(cli_args, 'voice', 'af_heart')

    async def handle_event(self, event: Event) -> bool:
        """Handle an event from Wyoming client."""
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            _LOGGER.debug("Sent service info")
            return True

        if Synthesize.is_type(event.type):
            synthesize = Synthesize.from_event(event)
            text = synthesize.text
            voice = synthesize.voice.name if synthesize.voice else self._default_voice

            _LOGGER.info(f"Synthesize: '{text[:30]}...' voice={voice}")

            total_start = time.perf_counter()
            first_byte_time = None
            
            try:
                # Send audio start immediately
                await self.write_event(
                    AudioStart(
                        rate=self._sample_rate,
                        width=self._sample_width,
                        channels=self._channels
                    ).event()
                )
                
                # ============================================================
                # OPTIMIZATION 2: Pipeline Parallel Synthesis
                # ============================================================
                total_bytes = 0
                segment_count = 0
                
                async for audio_chunk in self._pipeline_synthesis(text, voice):
                    if audio_chunk:
                        if first_byte_time is None:
                            first_byte_time = time.perf_counter() - total_start
                            _LOGGER.info(f"[PERF] First byte: {first_byte_time:.3f}s")
                        
                        total_bytes += len(audio_chunk)
                        segment_count += 1
                        await self._send_audio_optimized(audio_chunk)
                
                await self.write_event(AudioStop().event())
                
                total_elapsed = time.perf_counter() - total_start
                _LOGGER.info(
                    f"[OK] {total_bytes} bytes, {segment_count} segments, "
                    f"first_byte={first_byte_time:.3f}s, total={total_elapsed:.3f}s"
                )

            except Exception as e:
                _LOGGER.error(f"Synthesis error: {e}", exc_info=True)
                await self.write_event(AudioStop().event())

            return False

        return True

    async def _pipeline_synthesis(
        self, text: str, voice: str
    ) -> AsyncGenerator[bytes, None]:
        """
        Pipeline parallel synthesis for minimum latency.
        
        Uses producer-consumer pattern:
        - Producer: Generates audio segments in background
        - Consumer: Yields audio as soon as it's ready
        """
        # ============================================================
        # OPTIMIZATION 5: Short Text Fast Path
        # ============================================================
        if len(text) <= 20:
            _LOGGER.debug("Fast path: short text")
            audio = await asyncio.to_thread(
                self._run_synthesis, text, voice
            )
            if audio:
                yield audio
            return
        
        # Split into ultra-fine segments
        segments = split_for_streaming(text, max_chars=15)
        _LOGGER.info(f"Pipeline: {len(segments)} segments")
        
        if not segments:
            return
        
        # Pipeline with prefetch
        queue: asyncio.Queue = asyncio.Queue(maxsize=2)
        synthesis_done = asyncio.Event()
        
        async def producer():
            """Background producer: generates audio segments."""
            try:
                for i, segment in enumerate(segments):
                    if not segment.strip():
                        continue
                    
                    start = time.perf_counter()
                    audio = await asyncio.to_thread(
                        self._run_synthesis, segment, voice
                    )
                    elapsed = time.perf_counter() - start
                    
                    if audio:
                        _LOGGER.debug(f"Seg {i+1}: {len(segment)} chars, {elapsed:.3f}s")
                        await queue.put(audio)
                    else:
                        _LOGGER.warning(f"Seg {i+1} failed")
            finally:
                synthesis_done.set()
                await queue.put(None)  # Sentinel
        
        # Start producer
        producer_task = asyncio.create_task(producer())
        
        # Consumer: yield audio as it becomes available
        try:
            while True:
                try:
                    audio = await asyncio.wait_for(queue.get(), timeout=10.0)
                    if audio is None:
                        break
                    yield audio
                except asyncio.TimeoutError:
                    _LOGGER.warning("Queue timeout")
                    break
        finally:
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass

    def _run_synthesis(self, text: str, voice: str) -> Optional[bytes]:
        """Run synthesis synchronously with speed optimization."""
        try:
            lang = self._detect_language(text)
            tts = self.__class__._get_tts(lang)

            if tts is None:
                return None

            speaker_id = self._voice_to_speaker_id(voice)
            
            start = time.perf_counter()
            
            # ============================================================
            # OPTIMIZATION 4: Speed Parameter (slightly faster speech)
            # ============================================================
            audio = tts.generate(text, sid=speaker_id, speed=self.__class__._speed)
            
            gen_time = time.perf_counter() - start
            
            if audio is not None and len(audio.samples) > 0:
                audio_int16 = (audio.samples * 32767).astype(np.int16)
                audio_bytes = audio_int16.tobytes()
                
                duration = len(audio.samples) / self._sample_rate
                rtf = gen_time / duration if duration > 0 else 0
                _LOGGER.debug(f"Gen={gen_time:.3f}s Dur={duration:.2f}s RTF={rtf:.2f}")
                
                return audio_bytes
            return None

        except Exception as e:
            _LOGGER.error(f"Synthesis failed: {e}", exc_info=True)
            return None

    def _detect_language(self, text: str) -> str:
        """Fast language detection."""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        return "zh" if chinese_chars / max(len(text), 1) > 0.2 else "en-us"

    def _voice_to_speaker_id(self, voice: str) -> int:
        """Map voice name to speaker ID."""
        voice_map = {
            "af_heart": 0, "af_bella": 1, "am_michael": 2, "am_adam": 3,
            "bf_emma": 4, "bf_george": 5, "bm_george": 6, "bm_lewis": 7,
            "ef_dora": 8, "em_alex": 9, "ff_nicole": 10, "ff_siwu": 11,
            "fm_dora": 12, "fm_sarah": 13, "hf_alpha": 14, "hf_beta": 15,
            "hm_omega": 16, "hm_psi": 17, "if_nicole": 18, "im_siyu": 19,
            "jf_nezumi": 20, "jf_xiaobei": 21, "jf_xiaoxiao": 22,
            "jf_yunjian": 23, "jm_kumo": 24, "jf_takeru": 25,
        }
        return voice_map.get(voice, 0)

    # ============================================================
    # OPTIMIZATION 6: Optimized Async Chunk Sending
    # ============================================================
    async def _send_audio_optimized(self, audio_data: bytes) -> None:
        """Send audio with larger chunks to reduce await overhead."""
        chunk_size = 8192  # Doubled from 4096
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            await self.write_event(
                AudioChunk(
                    audio=chunk,
                    rate=self._sample_rate,
                    width=self._sample_width,
                    channels=self._channels
                ).event()
            )
