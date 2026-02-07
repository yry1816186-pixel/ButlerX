from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import logging
import os
import tempfile
import wave
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

try:  # optional local ASR backends
    from faster_whisper import WhisperModel as FasterWhisperModel
except ImportError as e:
    logger.warning(f"faster_whisper not available: {e}")
    FasterWhisperModel = None
except Exception as e:
    logger.error(f"Error importing faster_whisper: {e}")
    FasterWhisperModel = None

try:  # optional local ASR backend
    import whisper as OpenAIWhisper
except ImportError as e:
    logger.warning(f"whisper not available: {e}")
    OpenAIWhisper = None
except Exception as e:
    logger.error(f"Error importing whisper: {e}")
    OpenAIWhisper = None

try:  # optional local ASR backend
    from vosk import KaldiRecognizer as VoskRecognizer
    from vosk import Model as VoskModel
except ImportError as e:
    logger.warning(f"vosk not available: {e}")
    VoskRecognizer = None
    VoskModel = None
except Exception as e:
    logger.error(f"Error importing vosk: {e}")
    VoskRecognizer = None
    VoskModel = None


def decode_audio_input(audio: Any) -> Optional[bytes]:
    if audio is None:
        return None
    if isinstance(audio, dict):
        if isinstance(audio.get("base64"), str):
            return _decode_base64(audio["base64"])
        if isinstance(audio.get("url"), str):
            return _download(audio["url"])
        if isinstance(audio.get("path"), str):
            return _read_file(audio["path"])
        if isinstance(audio.get("data"), str):
            return _decode_base64(audio["data"])
        return None
    if isinstance(audio, str):
        if audio.startswith("http://") or audio.startswith("https://"):
            return _download(audio)
        if os.path.isfile(audio):
            return _read_file(audio)
        return _decode_base64(audio)
    return None


def _decode_base64(value: str) -> Optional[bytes]:
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        return None


def _download(url: str) -> Optional[bytes]:
    try:
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content
    except (httpx.HTTPError, httpx.TimeoutException, httpx.ConnectError):
        return None


def _read_file(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def fingerprint_audio(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _detect_audio_suffix(audio_bytes: bytes) -> str:
    if _is_wav(audio_bytes):
        return ".wav"
    if len(audio_bytes) >= 4 and audio_bytes[:4] == b"OggS":
        return ".ogg"
    if len(audio_bytes) >= 4 and audio_bytes[:4] == b"fLaC":
        return ".flac"
    if len(audio_bytes) >= 3 and audio_bytes[:3] == b"ID3":
        return ".mp3"
    if len(audio_bytes) >= 2 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0:
        return ".mp3"
    if len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
        return ".m4a"
    if len(audio_bytes) >= 4 and audio_bytes[:4] == b"\x1A\x45\xDF\xA3":
        return ".webm"
    return ".bin"


def _write_temp_audio(audio_bytes: bytes, suffix: Optional[str] = None) -> str:
    suffix = suffix or _detect_audio_suffix(audio_bytes)
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        handle.write(audio_bytes)
        handle.flush()
    finally:
        handle.close()
    return handle.name


def _cleanup_temp(path: Optional[str]) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except (FileNotFoundError, PermissionError, OSError):
        return


def _is_wav(audio_bytes: bytes) -> bool:
    return len(audio_bytes) > 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE"


def _error(code: str, detail: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"error": code}
    if detail:
        payload["detail"] = detail
    return payload


class _FasterWhisperProvider:
    def __init__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        download_dir: str,
        beam_size: int,
    ) -> None:
        if FasterWhisperModel is None:
            raise RuntimeError("faster_whisper_not_installed")
        download_root = download_dir or None
        self.model = FasterWhisperModel(
            model_name,
            device=device or "cpu",
            compute_type=compute_type or "int8",
            download_root=download_root,
        )
        self.beam_size = max(int(beam_size or 5), 1)

    def transcribe(self, audio_bytes: bytes, language: Optional[str], prompt: Optional[str]) -> Dict[str, Any]:
        path = _write_temp_audio(audio_bytes)
        try:
            segments, info = self.model.transcribe(
                path,
                language=language or None,
                initial_prompt=prompt or None,
                beam_size=self.beam_size,
            )
            texts = []
            seg_payload = []
            for seg in segments:
                text = seg.text or ""
                texts.append(text)
                seg_payload.append({"start": seg.start, "end": seg.end, "text": text})
            text_out = "".join(texts).strip()
            return {
                "text": text_out,
                "raw": {
                    "language": getattr(info, "language", None),
                    "duration": getattr(info, "duration", None),
                    "segments": seg_payload,
                },
            }
        finally:
            _cleanup_temp(path)


class _OpenAIWhisperProvider:
    def __init__(self, model_name: str) -> None:
        if OpenAIWhisper is None:
            raise RuntimeError("openai_whisper_not_installed")
        self.model = OpenAIWhisper.load_model(model_name or "base")

    def transcribe(self, audio_bytes: bytes, language: Optional[str], prompt: Optional[str]) -> Dict[str, Any]:
        path = _write_temp_audio(audio_bytes)
        try:
            result = self.model.transcribe(
                path,
                language=language or None,
                initial_prompt=prompt or None,
                fp16=False,
            )
        finally:
            _cleanup_temp(path)
        return {
            "text": str(result.get("text", "")).strip(),
            "raw": {
                "language": result.get("language"),
                "segments": result.get("segments"),
            },
        }


class _VoskProvider:
    def __init__(self, model_path: str) -> None:
        if VoskModel is None or VoskRecognizer is None:
            raise RuntimeError("vosk_not_installed")
        if not model_path or not os.path.isdir(model_path):
            raise RuntimeError("vosk_model_path_invalid")
        self.model = VoskModel(model_path)

    def transcribe(self, audio_bytes: bytes, language: Optional[str], prompt: Optional[str]) -> Dict[str, Any]:
        _ = language, prompt
        if not _is_wav(audio_bytes):
            return _error("vosk_requires_wav_pcm")
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            if wf.getnchannels() != 1:
                return _error("vosk_requires_mono_pcm")
            recognizer = VoskRecognizer(self.model, wf.getframerate())
            recognizer.SetWords(True)
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                recognizer.AcceptWaveform(data)
            try:
                result = json.loads(recognizer.FinalResult())
            except json.JSONDecodeError:
                result = {"text": ""}
        return {"text": str(result.get("text", "")).strip(), "raw": result}


class VoiceClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        timeout_sec: int,
        provider: str = "auto",
        local_model: str = "base",
        local_language: str = "",
        local_device: str = "cpu",
        local_compute_type: str = "int8",
        local_download_dir: str = "",
        local_beam_size: int = 5,
        vosk_model_path: str = "",
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout_sec = max(int(timeout_sec), 1)
        self.provider = (provider or "auto").lower()
        self.local_model = local_model or "base"
        self.local_language = local_language or ""
        self.local_device = local_device or "cpu"
        self.local_compute_type = local_compute_type or "int8"
        self.local_download_dir = local_download_dir or ""
        self.local_beam_size = int(local_beam_size or 5)
        self.vosk_model_path = vosk_model_path or ""
        self._local_provider = ""
        self._local_impl: Optional[object] = None

    def transcribe(
        self,
        audio: Any,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        audio_bytes = decode_audio_input(audio)
        if not audio_bytes:
            return _error("audio_invalid")

        language = language or (self.local_language or None)
        provider = self.provider

        if provider == "remote":
            return self._transcribe_remote(audio_bytes, language, prompt)

        if provider in {"faster-whisper", "whisper", "vosk"}:
            return self._transcribe_local(provider, audio_bytes, language, prompt)

        if provider == "auto":
            last_error: Optional[Dict[str, Any]] = None
            for candidate in ("faster-whisper", "whisper", "vosk"):
                result = self._transcribe_local(candidate, audio_bytes, language, prompt)
                if "error" not in result:
                    return result
                if result.get("error") not in {
                    "faster_whisper_not_installed",
                    "openai_whisper_not_installed",
                    "vosk_not_installed",
                    "vosk_model_path_invalid",
                }:
                    return result
                last_error = result
            if self.api_url and self.api_key:
                return self._transcribe_remote(audio_bytes, language, prompt)
            if last_error:
                return last_error
            return _error("no_available_asr_provider")

        return _error("asr_provider_invalid", f"unsupported provider: {provider}")

    def _transcribe_local(
        self,
        provider: str,
        audio_bytes: bytes,
        language: Optional[str],
        prompt: Optional[str],
    ) -> Dict[str, Any]:
        try:
            if self._local_impl is None or self._local_provider != provider:
                if provider == "faster-whisper":
                    self._local_impl = _FasterWhisperProvider(
                        model_name=self.local_model,
                        device=self.local_device,
                        compute_type=self.local_compute_type,
                        download_dir=self.local_download_dir,
                        beam_size=self.local_beam_size,
                    )
                elif provider == "whisper":
                    self._local_impl = _OpenAIWhisperProvider(self.local_model)
                elif provider == "vosk":
                    self._local_impl = _VoskProvider(self.vosk_model_path)
                else:
                    return _error("asr_provider_invalid", f"unsupported provider: {provider}")
                self._local_provider = provider
            impl = self._local_impl
            if impl is None:
                return _error("local_provider_not_available")
            result = impl.transcribe(audio_bytes, language, prompt)
            if "error" in result:
                return result
            result["provider"] = provider
            return result
        except RuntimeError as exc:
            return _error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            return _error("local_asr_failed", str(exc))

    def _transcribe_remote(
        self,
        audio_bytes: bytes,
        language: Optional[str],
        prompt: Optional[str],
    ) -> Dict[str, Any]:
        if not self.api_url:
            return _error("asr_api_not_configured")
        if not self.api_key:
            return _error("asr_api_key_missing")

        headers = {"Authorization": f"Bearer {self.api_key}"}
        data: Dict[str, Any] = {"model": self.model}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}

        try:
            resp = httpx.post(
                self.api_url,
                headers=headers,
                data=data,
                files=files,
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            return _error("asr_remote_failed", str(exc))

        text = payload.get("text") or payload.get("transcript")
        return {"text": text, "raw": payload, "provider": "remote"}
