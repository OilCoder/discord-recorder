# Plan: Session Processing Pipeline

## Problema
Las sesiones de rol se graban en múltiples ZIPs separados (una grabación por escena).
Las conversaciones mezclan roleplay, preguntas de mesa y charla off-topic.
El pipeline actual procesa un solo ZIP y genera un wiki sin filtrar el contenido.

## Pipeline nuevo

```
tmp/ (N ZIPs de la misma sesión)
  │
  ▼
[1. ASSEMBLER] — bot/assembler.py
  • Lee info.txt de cada ZIP → extrae Start time
  • Ordena ZIPs cronológicamente por Start time
  • Transcribe cada uno con Whisper (via transcriber.py)
  • Fusiona transcripts ajustando timestamps a tiempo absoluto
  • Output: transcript/<fecha>_full.txt

  │
  ▼
[2. CLASSIFIER] — bot/classifier.py
  • Envía lotes de ~30 líneas individuales a mistral vía Ollama
  • Solapamiento de 5 líneas entre lotes para dar contexto en los bordes
  • Clasifica CADA línea individualmente (no el lote completo)
  • Lotes enviados en paralelo con asyncio (OLLAMA_NUM_PARALLEL=4)
  • Usa format:json forzado → garantiza JSON válido siempre
  • Schema: [{"id": 0, "cat": "roleplay"}, {"id": 1, "cat": "off-topic"}, ...]
  • Categorías: roleplay | mesa | off-topic
  • Output: transcript/<fecha>_roleplay.txt (solo líneas roleplay)
  • Output: transcript/<fecha>_mesa.txt (solo líneas mesa)

  │
  ▼
[3. SUMMARIZER] — bot/summarizer.py (modificar para dos modos)
  • Modo sesión: recibe <fecha>_roleplay.txt → wiki narrativo para el master
    - Resumen general
    - Cronología de eventos
    - Decisiones de los jugadores
    - Hilos abiertos
    - Notas para el master
    - Output: wiki/<fecha>_sesion.md
  • Modo mesa: recibe <fecha>_mesa.txt → informe técnico de mecánicas
    - Dudas de reglas surgidas
    - Decisiones mecánicas
    - Output: wiki/<fecha>_mesa.md
```

## Archivos a crear/modificar

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `bot/assembler.py` | Crear | Ordena ZIPs por Start time, transcribe y fusiona |
| `bot/classifier.py` | Crear | Clasifica líneas individuales en lotes con solapamiento, usando mistral |
| `bot/transcriber.py` | Modificar mínimo | Devolver segmentos con offset de tiempo absoluto |
| `main.py` | Modificar | Orquestar el nuevo flujo completo |
| `bot/summarizer.py` | Modificar | Dos modos: sesión (roleplay→wiki narrativo) y mesa (mesa→informe técnico) |

## Convenciones

- `info.txt` dentro de cada ZIP contiene el `Start time` en formato ISO 8601
- Los timestamps del transcript son relativos al inicio de cada grabación → se ajustan a tiempo absoluto al fusionar
- El nombre de la sesión se deriva de la fecha del primer ZIP: `YYYY-MM-DD`
- Ollama corre en `http://host.docker.internal:11434` (accesible desde Docker)
- Modelo clasificador: `mistral` (rápido, tarea simple)
- Modelo summarizer: `qwen2.5:14b` (calidad, 128k context)

## Configuración Ollama (Windows PowerShell)

```powershell
$env:OLLAMA_NUM_PARALLEL=2; $env:OLLAMA_HOST="0.0.0.0"; ollama serve
```

- `OLLAMA_HOST=0.0.0.0` — accesible desde WSL y Docker
- `OLLAMA_NUM_PARALLEL=2` — procesa 2 lotes simultáneos (safe con 4080 16GB + mistral 4.1GB)
