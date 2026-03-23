import asyncio
import json
import os

import aiohttp

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "mistral")

BATCH_SIZE = 30
OVERLAP = 5
MAX_PARALLEL = 4

VALID_CATS = {"roleplay", "mesa", "off-topic"}

SYSTEM_PROMPT = """Eres un clasificador de transcripciones de sesiones de rol de mesa (Vampiro: La Edad Oscura).

Clasifica cada línea en una de estas categorías:
- "roleplay": todo lo relacionado con el juego en sí — narración del master describiendo escenas, ambientes o personajes; diálogo en personaje; descripción de acciones, eventos o consecuencias dentro del mundo del juego; resúmenes narrativos de lo ocurrido
- "mesa": intervenciones fuera del juego — preguntas de reglas, mecánicas, tiradas de dados, clarificaciones al master sobre cómo funciona algo del sistema, coordinación de turnos o de la sesión
- "off-topic": conversación sin ninguna relación con la sesión — chistes, temas personales, pausas, problemas técnicos

En caso de duda entre "roleplay" y "mesa", clasifica como "roleplay".

Devuelve ÚNICAMENTE un objeto JSON con esta estructura exacta:
{"classifications": [{"id": 0, "cat": "roleplay"}, {"id": 1, "cat": "mesa"}, ...]}

Incluye una entrada por cada línea numerada, en el mismo orden."""


def _extract_json(raw: str) -> any:
    """Intenta parsear JSON desde la respuesta, manejando texto extra o markdown."""
    raw = raw.strip()
    # Intentar directo
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Buscar bloque JSON entre ``` o extraer primer objeto/array
    import re
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Buscar primer { o [ hasta su cierre
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = raw.find(start_char)
        end = raw.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError(f"No se pudo extraer JSON de la respuesta: {raw[:200]}")


def _parse_response(raw: str, batch_size: int) -> list[dict]:
    """Parsea la respuesta JSON del modelo. Devuelve lista de {id, cat}."""
    data = _extract_json(raw)

    # Acepta {"classifications": [...]} o directamente [...]
    if isinstance(data, list):
        classifications = data
    elif isinstance(data, dict):
        classifications = data.get("classifications", data.get("result", []))
    else:
        raise ValueError(f"Formato inesperado: {type(data)}")

    # Validar y sanitizar entradas
    result = []
    for item in classifications:
        idx = item.get("id")
        cat = item.get("cat", "").lower().strip()
        if idx is None or not isinstance(idx, int):
            continue
        if cat not in VALID_CATS:
            cat = "off-topic"
        result.append({"id": idx, "cat": cat})

    # Rellenar entradas faltantes con "off-topic"
    found_ids = {item["id"] for item in result}
    for i in range(batch_size):
        if i not in found_ids:
            result.append({"id": i, "cat": "off-topic"})

    result.sort(key=lambda x: x["id"])
    return result


async def _classify_batch(
    session: aiohttp.ClientSession,
    batch_start: int,
    batch_lines: list[str],
    semaphore: asyncio.Semaphore,
) -> tuple[int, list[dict]]:
    """Clasifica un lote de líneas. Devuelve (batch_start, [{id, cat}, ...])."""
    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(batch_lines))
    prompt = f"Clasifica cada línea de esta transcripción:\n\n{numbered}"

    for attempt in range(3):
        async with semaphore:
            async with session.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": CLASSIFIER_MODEL,
                    "system": SYSTEM_PROMPT,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                },
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                raw = data["response"]

        try:
            classifications = _parse_response(raw, len(batch_lines))
            return batch_start, classifications
        except (ValueError, KeyError) as e:
            print(f"[classifier] Intento {attempt + 1}/3 falló para lote {batch_start}: {e}")
            print(f"[classifier] Respuesta raw: {raw[:300]}")

    # Si los 3 intentos fallan, clasificar todo como off-topic
    print(f"[classifier] Lote {batch_start} falló 3 veces, usando off-topic por defecto")
    return batch_start, [{"id": i, "cat": "off-topic"} for i in range(len(batch_lines))]


async def _classify_all(lines: list[str]) -> list[str]:
    """Clasifica todas las líneas en paralelo con solapamiento entre lotes."""
    step = BATCH_SIZE - OVERLAP
    batches = []
    for start in range(0, len(lines), step):
        end = min(start + BATCH_SIZE, len(lines))
        batches.append((start, lines[start:end]))

    semaphore = asyncio.Semaphore(MAX_PARALLEL)
    results: dict[int, str] = {}

    async with aiohttp.ClientSession() as session:
        tasks = [
            _classify_batch(session, start, batch, semaphore)
            for start, batch in batches
        ]
        batch_results = await asyncio.gather(*tasks)

    # Merge: lotes posteriores (mayor start) ganan en la zona de solapamiento
    for batch_start, classifications in sorted(batch_results, key=lambda x: x[0]):
        for item in classifications:
            global_idx = batch_start + item["id"]
            if global_idx < len(lines):
                results[global_idx] = item["cat"]

    return [results.get(i, "off-topic") for i in range(len(lines))]


async def classify_transcript(transcript_path: str) -> tuple[str, str, dict]:
    """
    Lee el transcript completo, clasifica cada línea y genera:
      - transcript/<session>_roleplay.txt
      - transcript/<session>_mesa.txt
      - transcript/<session>_<username>.txt por jugador

    Devuelve (roleplay_path, mesa_path, player_paths).
    """
    with open(transcript_path, "r", encoding="utf-8") as f:
        lines = [line.rstrip() for line in f if line.strip()]

    print(f"[classifier] Clasificando {len(lines)} líneas con {CLASSIFIER_MODEL}...")
    categories = await _classify_all(lines)

    roleplay_lines = [l for l, c in zip(lines, categories) if c == "roleplay"]
    mesa_lines = [l for l, c in zip(lines, categories) if c == "mesa"]

    base = transcript_path.replace("_full.txt", "")
    roleplay_path = f"{base}_roleplay.txt"
    mesa_path = f"{base}_mesa.txt"
    classification_path = f"{base}_classification.json"

    with open(roleplay_path, "w", encoding="utf-8") as f:
        f.write("\n".join(roleplay_lines))

    with open(mesa_path, "w", encoding="utf-8") as f:
        f.write("\n".join(mesa_lines))

    with open(classification_path, "w", encoding="utf-8") as f:
        json.dump(
            [{"id": i, "cat": c, "line": l} for i, (l, c) in enumerate(zip(lines, categories))],
            f, ensure_ascii=False, indent=2
        )
    print(f"[classifier] Clasificación guardada en {classification_path}")

    # Transcripts por jugador (solo líneas roleplay de cada uno)
    players: dict[str, list[str]] = {}
    for line, cat in zip(lines, categories):
        if cat != "roleplay":
            continue
        # Formato: [HH:MM:SS] usuario: texto
        try:
            username = line.split("] ", 1)[1].split(": ", 1)[0]
        except IndexError:
            continue
        players.setdefault(username, []).append(line)

    player_paths = {}
    for username, player_lines in players.items():
        player_path = f"{base}_{username}.txt"
        with open(player_path, "w", encoding="utf-8") as f:
            f.write("\n".join(player_lines))
        player_paths[username] = player_path
        print(f"[classifier] Jugador {username}: {len(player_lines)} líneas → {player_path}")

    total = len(lines)
    print(f"[classifier] roleplay: {len(roleplay_lines)} líneas | mesa: {len(mesa_lines)} líneas | off-topic: {total - len(roleplay_lines) - len(mesa_lines)} líneas")
    print(f"[classifier] Guardado: {roleplay_path}")
    print(f"[classifier] Guardado: {mesa_path}")

    return roleplay_path, mesa_path, player_paths
