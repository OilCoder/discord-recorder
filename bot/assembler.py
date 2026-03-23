import os
import zipfile
from datetime import datetime, timezone
from datetime import timedelta

from bot.transcriber import transcribe_zip


def parse_start_time(zip_path: str) -> datetime:
    """Lee info.txt dentro del ZIP y devuelve el Start time como datetime UTC."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        info = zf.read("info.txt").decode()
    for line in info.splitlines():
        if line.strip().startswith("Start time:"):
            ts = line.split(":", 1)[1].strip()
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    raise ValueError(f"No se encontró 'Start time' en info.txt de {zip_path}")


def get_sorted_zips(tmp_dir: str) -> list[tuple[datetime, str]]:
    """Devuelve lista de (start_time, zip_path) ordenada cronológicamente."""
    zips = []
    for entry in os.listdir(tmp_dir):
        if not entry.endswith(".zip"):
            continue
        full_path = os.path.join(tmp_dir, entry)
        if not os.path.isfile(full_path):
            continue
        try:
            start_time = parse_start_time(full_path)
            zips.append((start_time, full_path))
        except Exception as e:
            print(f"[assembler] Ignorando {entry}: {e}")
    zips.sort(key=lambda x: x[0])
    return zips


def fmt_time(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def assemble_session(tmp_dir: str) -> str:
    """
    Ordena todos los ZIPs de tmp_dir por Start time, transcribe cada uno
    con el offset correcto y fusiona en un único transcript.

    Devuelve la ruta del archivo transcript/<YYYY-MM-DD>_full.txt generado.
    """
    zips = get_sorted_zips(tmp_dir)
    if not zips:
        raise ValueError(f"No se encontraron ZIPs en {tmp_dir}")

    session_start, _ = zips[0]
    session_date = session_start.strftime("%Y-%m-%d")
    print(f"[assembler] Sesión: {session_date} — {len(zips)} archivo(s)")

    all_segments = []

    for start_time, zip_path in zips:
        offset = (start_time - session_start).total_seconds()
        nombre = os.path.basename(zip_path)
        print(f"[assembler] Transcribiendo {nombre} (offset {int(offset)}s)...")
        segments = transcribe_zip(zip_path, time_offset=offset)
        all_segments.extend(segments)
        print(f"[assembler] {nombre} — {len(segments)} segmentos")

    all_segments.sort(key=lambda x: x[0])

    lines = [f"[{fmt_time(t)}] {user}: {text}" for t, user, text in all_segments]
    transcript = "\n".join(lines)

    os.makedirs("transcript", exist_ok=True)
    out_path = os.path.join("transcript", f"{session_date}_full.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    print(f"[assembler] Transcript completo guardado en {out_path} ({len(lines)} líneas)")
    return out_path
