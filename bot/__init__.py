import glob
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from main import run_pipeline

load_dotenv()

MASTER_USER = os.getenv("MASTER_USER", "")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_master(ctx: commands.Context) -> bool:
    return ctx.author.name == MASTER_USER


def _latest_wiki(pattern: str) -> str | None:
    """Devuelve el archivo wiki más reciente que coincida con el patrón glob."""
    files = sorted(glob.glob(os.path.join("wiki", pattern)), reverse=True)
    return files[0] if files else None


def _latest_wiki_for_player(username: str) -> str | None:
    return _latest_wiki(f"*_{username}.md")


async def _send_file(ctx: commands.Context, path: str | None, label: str, dm: bool = False):
    """Envía un archivo como adjunto. Si dm=True lo manda por DM."""
    if not path or not os.path.exists(path):
        await ctx.send(f"No hay {label} disponible aún. Usa `!procesar` primero.")
        return
    dest = ctx.author if dm else ctx
    try:
        await dest.send(file=discord.File(path))
    except discord.Forbidden:
        await ctx.send(f"No pude enviarte DM. Activa los mensajes directos del servidor.")


# ── Eventos ──────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"[bot] Conectado como {bot.user} — comandos slash sincronizados")


# ── Comandos ─────────────────────────────────────────────────────────────────

@bot.command(name="procesar")
async def cmd_procesar(ctx: commands.Context):
    """Solo el master puede lanzar el pipeline."""
    if not _is_master(ctx):
        await ctx.send("Solo el master puede usar este comando.")
        return

    tmp_dir = "tmp"
    if not os.path.isdir(tmp_dir) or not any(f.endswith(".zip") for f in os.listdir(tmp_dir)):
        await ctx.send("No hay archivos ZIP en `tmp/` para procesar.")
        return

    try:
        await ctx.send("Iniciando pipeline... **Paso 1:** Transcribiendo audios con Whisper")
        full_transcript, roleplay_path, mesa_path, sesion_wiki, mesa_wiki, player_wikis = await run_pipeline(tmp_dir)
        await ctx.send("**Paso 2:** Clasificando con mistral... completado")
        await ctx.send("**Paso 3:** Generando documentos con qwen2.5... completado")
        await ctx.send(f"**Pipeline completado.** Sesión `{os.path.basename(full_transcript)}` lista. Usa `!resumen_gm`, `!mesa` o pide a los jugadores que usen `!mi_resumen`.")
    except Exception as e:
        await ctx.send(f"Error durante el procesamiento: `{e}`")
        raise


@bot.command(name="resumen_gm")
async def cmd_resumen_gm(ctx: commands.Context):
    """Wiki completo de sesión — solo master, enviado por DM."""
    if not _is_master(ctx):
        await ctx.send("Solo el master puede usar este comando.")
        return
    path = _latest_wiki("*_sesion.md")
    await _send_file(ctx, path, "resumen de sesión", dm=True)


@bot.command(name="mesa")
async def cmd_mesa(ctx: commands.Context):
    """Informe técnico de reglas — solo master, enviado por DM."""
    if not _is_master(ctx):
        await ctx.send("Solo el master puede usar este comando.")
        return
    path = _latest_wiki("*_mesa.md")
    await _send_file(ctx, path, "informe de mesa", dm=True)


@bot.command(name="mi_resumen")
async def cmd_mi_resumen(ctx: commands.Context):
    """Reporte personal del jugador — enviado por DM."""
    username = ctx.author.name
    path = _latest_wiki_for_player(username)

    # Excluir archivos _sesion y _mesa del match
    if path and (path.endswith("_sesion.md") or path.endswith("_mesa.md")):
        path = None

    await _send_file(ctx, path, f"reporte personal de {username}", dm=True)


@bot.command(name="estado")
async def cmd_estado(ctx: commands.Context):
    """Muestra qué sesión está procesada y qué documentos están disponibles."""
    wikis = sorted(glob.glob(os.path.join("wiki", "*.md")), reverse=True)
    transcripts = sorted(glob.glob(os.path.join("transcript", "*_full.txt")), reverse=True)

    if not wikis and not transcripts:
        await ctx.send("No hay sesiones procesadas aún. Usa `!procesar`.")
        return

    lines = ["**Estado del sistema**"]

    if transcripts:
        sesion = os.path.basename(transcripts[0]).replace("_full.txt", "")
        lines.append(f"Última sesión procesada: `{sesion}`")

    if wikis:
        lines.append("Documentos disponibles:")
        for w in wikis[:8]:
            lines.append(f"  • `{os.path.basename(w)}`")

    await ctx.send("\n".join(lines))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN no está definido en el entorno.")
    bot.run(token)
