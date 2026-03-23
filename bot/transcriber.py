import os
import subprocess
import tempfile
import zipfile
from datetime import timedelta
from faster_whisper import WhisperModel

_model: WhisperModel | None = None

AUDIO_EXTENSIONS = (".aac", ".wav", ".flac", ".ogg", ".mp3")


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        model_size = os.getenv("WHISPER_MODEL", "large-v3")
        print(f"[whisper] Cargando modelo {model_size} en CUDA...")
        _model = WhisperModel(model_size, device="cuda", compute_type="float16")
        print("[whisper] Modelo listo.")
    return _model


def release_model() -> None:
    """Libera Whisper de VRAM antes de cargar el siguiente modelo."""
    global _model
    if _model is not None:
        del _model
        _model = None
        try:
            import torch
            torch.cuda.empty_cache()
        except ImportError:
            pass
        print("[whisper] Modelo liberado de VRAM.")


def fmt_time(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def get_audio_duration(filepath: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", filepath],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def transcribe_zip(zip_path: str, time_offset: float = 0.0) -> list[tuple[float, str, str]]:
    """Transcribe un ZIP y devuelve lista de (tiempo_absoluto, usuario, texto).

    time_offset: segundos a sumar a cada timestamp (para alinear con el inicio de sesión).
    """
    model = get_model()
    all_segments = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        audio_names = sorted([
            n for n in zf.namelist()
            if any(n.endswith(ext) for ext in AUDIO_EXTENSIONS)
            and not n.startswith("__MACOSX")
        ])

        if not audio_names:
            raise ValueError("No se encontraron pistas de audio en el ZIP.")

        for name in audio_names:
            suffix = os.path.splitext(name)[-1]
            username = name.split("-", 1)[-1].rsplit(".", 1)[0] if "-" in name else name.rsplit(".", 1)[0]

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(zf.read(name))
                tmp_path = tmp.name

            try:
                print(f"[whisper] Transcribiendo {username}...")
                segments, info = model.transcribe(
                    tmp_path,
                    language=None,
                    beam_size=5,
                    vad_filter=True,
                )
                print(f"[whisper] {username} — idioma: {info.language}")
                for seg in segments:
                    all_segments.append((seg.start + time_offset, username, seg.text.strip()))
            finally:
                os.unlink(tmp_path)

    all_segments.sort(key=lambda x: x[0])
    return all_segments


def transcribe_session(zip_path: str, session_name: str) -> str:
    """Transcribe un ZIP de Craig sin modificarlo.
    Guarda el resultado en transcript/<session_name>.txt"""
    print(f"[whisper] Procesando {os.path.basename(zip_path)}...")
    all_segments = transcribe_zip(zip_path)

    if not all_segments:
        raise ValueError("No se extrajo texto de los audios.")

    all_segments.sort(key=lambda x: x[0])

    lines = [f"[{fmt_time(t)}] {user}: {text}" for t, user, text in all_segments]
    transcript = "\n".join(lines)

    os.makedirs("transcript", exist_ok=True)
    out_path = os.path.join("transcript", f"{session_name}.txt")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    print(f"[whisper] Guardado en {out_path}")
    return out_path
