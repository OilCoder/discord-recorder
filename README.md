# Discord Recorder — Vampiro: La Edad Oscura

Bot de Discord que graba sesiones de rol de mesa, las transcribe automáticamente y genera documentos wiki para el master y los jugadores.

## ¿Qué hace?

Al terminar una sesión, el master ejecuta `!procesar` y el bot:

1. **Transcribe** los audios con [Faster Whisper](https://github.com/SYSTRAN/faster-whisper) (large-v3)
2. **Clasifica** cada línea en `roleplay`, `mesa` u `off-topic` usando un LLM local (Mistral vía Ollama)
3. **Genera documentos** con otro LLM (Qwen 2.5 vía Ollama):
   - Wiki de sesión completa (para el master)
   - Informe técnico de reglas y mecánicas
   - Reporte personal por jugador

Todo corre localmente — no se envía audio ni texto a servicios externos.

## Comandos del bot

| Comando | Quién | Descripción |
|---------|-------|-------------|
| `!procesar` | Master | Lanza el pipeline completo sobre los ZIPs en `tmp/` |
| `!resumen_gm` | Master | Recibe por DM la wiki de sesión |
| `!mesa` | Master | Recibe por DM el informe de reglas |
| `!mi_resumen` | Jugador | Recibe por DM su reporte personal |
| `!estado` | Cualquiera | Muestra la última sesión procesada y documentos disponibles |

## Requisitos

- Docker + Docker Compose
- GPU NVIDIA (para Whisper)
- [Ollama](https://ollama.com/) corriendo en el host con los modelos `mistral` y `qwen2.5`

## Configuración

Crea un archivo `.env` en la raíz del proyecto:

```env
DISCORD_TOKEN=tu_token_de_discord
MASTER_USER=tu_usuario_de_discord          # acepta varios separados por coma
OLLAMA_HOST=http://host.docker.internal:11434
CLASSIFIER_MODEL=mistral
```

## Instalación y uso

```bash
# 1. Clona el repositorio
git clone https://github.com/OilCoder/discord-recorder.git
cd discord-recorder

# 2. Crea el .env con tus credenciales
cp .env.example .env   # edita con tus valores

# 3. Levanta el bot
docker compose up --build
```

Una vez activo, graba tu sesión con [Craig](https://craig.chat/) u otro bot de grabación, descarga los ZIPs de audio y colócalos en la carpeta `tmp/`. Luego escribe `!procesar` en Discord.

## Estructura

```
discord-recorder/
├── bot/
│   ├── __init__.py      # Bot de Discord y comandos
│   ├── assembler.py     # Ensambla y transcribe los audios
│   ├── classifier.py    # Clasifica líneas con Ollama
│   ├── summarizer.py    # Genera wikis con Ollama
│   └── transcriber.py   # Interfaz con Faster Whisper
├── main.py              # Pipeline principal
├── run_bot.py           # Entry point del bot
├── transcript/          # Transcripciones generadas
├── wiki/                # Documentos generados
└── tmp/                 # ZIPs de audio (entrada)
```

## Stack

- **Python 3.11+** · discord.py · aiohttp
- **Faster Whisper large-v3** — transcripción de voz
- **Ollama** — LLM local para clasificación y generación
- **Docker** con soporte GPU NVIDIA
