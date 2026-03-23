import asyncio
import os
import sys

from bot.assembler import assemble_session
from bot.classifier import classify_transcript
from bot.summarizer import summarize_session, summarize_mesa, summarize_player
from bot.transcriber import release_model


async def run_pipeline(tmp_dir: str = "tmp"):
    print("=" * 50)
    print("[pipeline] PASO 1 — Ensamblado y transcripción")
    print("=" * 50)
    loop = asyncio.get_event_loop()
    full_transcript = await loop.run_in_executor(None, assemble_session, tmp_dir)
    release_model()

    print()
    print("=" * 50)
    print("[pipeline] PASO 2 — Clasificación de líneas")
    print("=" * 50)
    roleplay_path, mesa_path, player_paths = await classify_transcript(full_transcript)

    print()
    print("=" * 50)
    print("[pipeline] PASO 3 — Generación de documentos")
    print("=" * 50)
    sesion_wiki = await loop.run_in_executor(None, summarize_session, roleplay_path)
    mesa_wiki = await loop.run_in_executor(None, summarize_mesa, mesa_path)

    player_wikis = {}
    for username, player_path in player_paths.items():
        wiki = await loop.run_in_executor(None, summarize_player, player_path, roleplay_path)
        if wiki:
            player_wikis[username] = wiki

    print()
    print("=" * 50)
    print("[pipeline] Completado")
    print(f"  Transcript completo : {full_transcript}")
    print(f"  Roleplay            : {roleplay_path}")
    print(f"  Mesa                : {mesa_path}")
    print(f"  Wiki sesión         : {sesion_wiki}")
    if mesa_wiki:
        print(f"  Wiki mesa           : {mesa_wiki}")
    for username, wiki in player_wikis.items():
        print(f"  Wiki {username:<15}: {wiki}")
    print("=" * 50)

    return full_transcript, roleplay_path, mesa_path, sesion_wiki, mesa_wiki, player_wikis


def main():
    tmp_dir = os.getenv("TMP_DIR", "tmp")
    if not os.path.isdir(tmp_dir):
        print(f"[error] No existe la carpeta '{tmp_dir}'")
        sys.exit(1)
    asyncio.run(run_pipeline(tmp_dir))


if __name__ == "__main__":
    main()
