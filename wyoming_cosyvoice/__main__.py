"""Main entry point for Wyoming Kokoro TTS server."""

import argparse
import asyncio
import logging
import socket
import tarfile
import urllib.request
import urllib.error
from pathlib import Path
from functools import partial
from urllib.parse import urlparse

from wyoming.info import TtsVoice, TtsVoiceSpeaker, TtsProgram, Attribution, Info
from wyoming.server import AsyncServer
from zeroconf import IPVersion, ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

from . import __version__
from .handler import KokoroEventHandler

_LOGGER = logging.getLogger(__name__)

# Kokoro model - ghfast.top GitHub mirror (verified working, fast in China)
KOKORO_MODEL_URL = "https://ghfast.top/github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2"
KOKORO_MODEL_DIR = "kokoro-multi-lang-v1_0"


async def download_model(model_path: str) -> None:
    """Download Kokoro model if not exists with resume support."""
    model_dir = Path(model_path)
    downloaded_flag = model_dir / "downloaded"
    model_subdir = model_dir / KOKORO_MODEL_DIR

    if downloaded_flag.exists() and model_subdir.exists():
        _LOGGER.info("Model already exists, skipping download")
        return

    _LOGGER.info("=" * 60)
    _LOGGER.info("Downloading Kokoro model from GitHub...")
    _LOGGER.info("This may take several minutes (~500MB)")
    _LOGGER.info("=" * 60)

    try:
        model_dir.mkdir(parents=True, exist_ok=True)
        tar_path = model_dir / "kokoro.tar.bz2"

        # Download model with progress (run in thread pool)
        def _download_with_progress():
            import shutil
            
            # Check if partial download exists
            existing_size = tar_path.stat().st_size if tar_path.exists() else 0
            
            req = urllib.request.Request(KOKORO_MODEL_URL)
            if existing_size > 0:
                req.add_header('Range', f'bytes={existing_size}-')
                _LOGGER.info(f"Resuming download from {existing_size} bytes")
            
            try:
                with urllib.request.urlopen(req, timeout=300) as response:
                    total_size = int(response.headers.get('Content-Length', 0)) + existing_size
                    
                    mode = 'ab' if existing_size > 0 else 'wb'
                    with open(tar_path, mode) as f:
                        downloaded = existing_size
                        block_size = 8192
                        last_percent = 0
                        
                        while True:
                            buffer = response.read(block_size)
                            if not buffer:
                                break
                            f.write(buffer)
                            downloaded += len(buffer)
                            
                            if total_size > 0:
                                percent = int(downloaded * 100 / total_size)
                                if percent >= last_percent + 10:
                                    _LOGGER.info(f"Download progress: {percent}%")
                                    last_percent = percent
            except urllib.error.HTTPError as e:
                if e.code == 416:  # Range not satisfiable - file complete
                    _LOGGER.info("Download already complete")
                else:
                    raise
            
            # Extract archive
            _LOGGER.info("Extracting model files...")
            with tarfile.open(tar_path, "r:bz2") as tar:
                tar.extractall(model_dir)
            
            # Cleanup tar file to save space
            tar_path.unlink()
            _LOGGER.info("Cleaned up temporary files")

        await asyncio.to_thread(_download_with_progress)

        # Verify extraction
        if not model_subdir.exists():
            raise FileNotFoundError(f"Model extraction failed: {model_subdir} not found")
        
        # Create downloaded flag
        downloaded_flag.touch()
        _LOGGER.info("[OK] Kokoro model downloaded and verified successfully")
        _LOGGER.info("=" * 60)

    except Exception as e:
        _LOGGER.error(f"Failed to download model: {e}", exc_info=True)
        raise


def get_ip_address():
    """Get the primary IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def main() -> None:
    """Start Wyoming Kokoro TTS server."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--uri",
        default="tcp://0.0.0.0:10301",
        help="unix:// or tcp://",
    )
    parser.add_argument(
        "--model-path",
        required=True,
        help="Path to Kokoro model directory",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Log DEBUG messages",
    )
    parser.add_argument(
        "--voice",
        default="af_heart",
        help="Default voice to use (e.g., af_heart, jf_xiaobei)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=24000,
        help="Audio sample rate (default: 24000)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speech speed (1.0=normal, 1.1=faster, 0.9=slower)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.info("Starting Wyoming Kokoro TTS server")

    # Download model if not exists
    await download_model(args.model_path)

    wyoming_info = Info(
        tts=[
            TtsProgram(
                name="AI Hub TTS",
                description="Offline text-to-speech synthesis using Kokoro",
                attribution=Attribution(
                    name="Kokoro",
                    url="https://github.com/remsky/Kokoro-FastAPI",
                ),
                version=__version__,
                installed=True,
                voices=[
                    TtsVoice(
                        name="Kokoro-Multi-Lang",
                        description="Chinese and English text-to-speech model",
                        attribution=Attribution(
                            name="Kokoro",
                            url="https://github.com/remsky/Kokoro-FastAPI",
                        ),
                        version=__version__,
                        installed=True,
                        languages=["zh", "zh-CN", "en"],
                        speakers=[
                            TtsVoiceSpeaker(name="af_heart"),
                            TtsVoiceSpeaker(name="af_bella"),
                            TtsVoiceSpeaker(name="am_michael"),
                            TtsVoiceSpeaker(name="am_adam"),
                            TtsVoiceSpeaker(name="bf_emma"),
                            TtsVoiceSpeaker(name="bf_george"),
                            TtsVoiceSpeaker(name="bm_george"),
                            TtsVoiceSpeaker(name="bm_lewis"),
                            TtsVoiceSpeaker(name="ef_dora"),
                            TtsVoiceSpeaker(name="em_alex"),
                            TtsVoiceSpeaker(name="ff_nicole"),
                            TtsVoiceSpeaker(name="ff_siwu"),
                            TtsVoiceSpeaker(name="fm_dora"),
                            TtsVoiceSpeaker(name="fm_sarah"),
                            TtsVoiceSpeaker(name="hf_alpha"),
                            TtsVoiceSpeaker(name="hf_beta"),
                            TtsVoiceSpeaker(name="hm_omega"),
                            TtsVoiceSpeaker(name="hm_psi"),
                            TtsVoiceSpeaker(name="if_nicole"),
                            TtsVoiceSpeaker(name="im_siyu"),
                            TtsVoiceSpeaker(name="jf_nezumi"),
                            TtsVoiceSpeaker(name="jf_xiaobei"),
                            TtsVoiceSpeaker(name="jf_xiaoxiao"),
                            TtsVoiceSpeaker(name="jf_yunjian"),
                            TtsVoiceSpeaker(name="jm_kumo"),
                            TtsVoiceSpeaker(name="jf_takeru"),
                        ],
                    )
                ],
            )
        ],
    )

    _LOGGER.info("Starting server")
    server = AsyncServer.from_uri(args.uri)

    # Set up Zeroconf for auto-discovery (with error handling)
    zeroconf_instance = None
    service_info = None

    try:
        # Parse URI to get host and port
        parsed_uri = urlparse(args.uri)
        port = parsed_uri.port or 10301
        host = parsed_uri.hostname or "0.0.0.0"

        _LOGGER.info(f"Server will listen on {host}:{port}")

        # Register mDNS service for auto-discovery with error handling
        try:
            _LOGGER.info("Registering mDNS service for auto-discovery")
            zeroconf_instance = AsyncZeroconf(ip_version=IPVersion.V4Only)

            # Get local IP address with error handling
            local_ip = get_ip_address()
            _LOGGER.info(f"Local IP address: {local_ip}")

            # Service name must be unique and follow mDNS naming conventions
            service_name = "ai-hub-tts._wyoming._tcp.local."

            # Convert IP to bytes with error handling
            try:
                ip_bytes = socket.inet_aton(local_ip)
            except socket.error as e:
                _LOGGER.warning(f"Failed to convert IP {local_ip} to bytes: {e}")
                ip_bytes = socket.inet_aton("127.0.0.1")

            service_info = ServiceInfo(
                "_wyoming._tcp.local.",
                service_name,
                addresses=[ip_bytes],
                port=port,
                properties={
                    b"name": b"AI Hub TTS",
                    b"description": b"Offline TTS for Chinese and English",
                    b"version": __version__.encode("utf-8"),
                    b"attribution": b"Kokoro",
                },
            )

            # Register service with timeout
            await asyncio.wait_for(
                zeroconf_instance.async_register_service(service_info),
                timeout=5.0
            )
            _LOGGER.info(f"mDNS service registered: {service_name} on port {port}")
        except Exception as e:
            _LOGGER.warning(f"Failed to register mDNS service, continuing without it: {e}")

        # Log ready state
        _LOGGER.info("=" * 60)
        _LOGGER.info("[OK] Wyoming AI Hub TTS Server is READY")
        _LOGGER.info(f"[OK] Listening on: {host}:{port}")
        _LOGGER.info(f"[OK] Model path: {args.model_path}")
        _LOGGER.info("[OK] Models will be loaded and ready shortly...")
        _LOGGER.info("=" * 60)

        # Pre-load models at startup
        await KokoroEventHandler.initialize_models(args)

        # Run server (blocking call)
        await server.run(
            partial(
                KokoroEventHandler,
                wyoming_info,
                args,
            )
        )
    except KeyboardInterrupt:
        _LOGGER.info("Received keyboard interrupt")
    except Exception as e:
        _LOGGER.error(f"Server error: {e}", exc_info=True)
    finally:
        # Cleanup Zeroconf with proper error handling
        if service_info and zeroconf_instance:
            try:
                _LOGGER.info("Unregistering mDNS service")
                await asyncio.wait_for(
                    zeroconf_instance.async_unregister_service(service_info),
                    timeout=3.0
                )
                await asyncio.wait_for(
                    zeroconf_instance.async_close(),
                    timeout=3.0
                )
                _LOGGER.info("mDNS service unregistered")
            except Exception as e:
                _LOGGER.warning(f"Error cleaning up Zeroconf: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
