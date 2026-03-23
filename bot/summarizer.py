import os
import requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct-q6_K")

SESSION_PROMPT = """Eres el cronista de una campaña de rol de mesa (Vampiro: La Edad Oscura).
Genera un documento interno para el MASTER. Sigue la estructura exacta sin agregar
ni omitir secciones. Cita timestamps con el formato → [HH:MM:SS] referenciando
el transcript de roleplay.

---

# Sesión — {session_name}

## Resumen de sesión
Narra el arco general de la sesión con voz de cronista vampírico — tono oscuro, formal y cargado
de tensión política. Escribe en tercera persona, como si fuera una entrada en los anales de la ciudad.
Qué ocurrió, qué fuerzas se movieron, cómo cerró la noche.

## Timeline
Lista cronológica de los eventos importantes de la sesión.
- Evento → `[HH:MM:SS]`

## Líneas abiertas
Tramas, conflictos o preguntas sin resolver al cierre de la sesión.
- Línea abierta → `[HH:MM:SS]`

## Lo que saben los jugadores
Información que el grupo conoce colectivamente al final de la sesión.
- Hecho conocido → `[HH:MM:SS]`

## Puntos ciegos por personaje
Para cada personaje, qué información relevante ignora específicamente.
- **[Nombre del personaje]**: Lo que no sabe → `[HH:MM:SS]`

## Notas para el master
Oportunidades narrativas para la próxima sesión. Qué pueden explotar los jugadores
sin saberlo, qué hilos pueden tensarse, qué NPCs tienen agenda propia.

---

El formato de cada línea es `[HH:MM:SS] username: texto`. El username es el jugador real.
Usa el username como identificador principal de cada personaje. Si en el texto aparece un nombre
de personaje distinto al username, puedes usarlo, pero NUNCA inventes nombres que no aparezcan
explícitamente en la transcripción. Si no hay nombre, usa el username.
No agregues secciones adicionales ni omitas ninguna.

TRANSCRIPCIÓN DE ROLEPLAY:
{transcript}
"""

MESA_PROMPT = """Eres un asistente técnico de una campaña de rol de mesa (Vampiro: La Edad Oscura — DA20/V20).
Genera un informe técnico interno para el MASTER. Sigue la estructura exacta sin agregar
ni omitir secciones. Cita timestamps con el formato → [HH:MM:SS].

Solo incluye información relevante en cada sección. Si no hay contenido para una sección,
escribe "Ninguna" en lugar de inventar entradas.

---

# Informe de Mesa — {session_name}

## Dudas sin resolver
Preguntas sobre reglas o mecánicas que surgieron durante la sesión y no obtuvieron
una respuesta clara o definitiva.
- Duda → `[HH:MM:SS]`

## Inconsistencias detectadas
Situaciones donde se usaron habilidades, disciplinas o mecánicas de forma incorrecta
o contradictoria con el sistema DA20/V20.
- Inconsistencia → `[HH:MM:SS]`

## Pendientes para el master
Puntos que deben consultarse en el manual o resolverse antes de la próxima sesión.
- Pendiente

---

El formato de cada línea es `[HH:MM:SS] username: texto`. El username es el jugador real.
Usa el username como identificador principal. NUNCA inventes nombres que no aparezcan
explícitamente en la transcripción.
Usa los términos exactos del sistema DA20/V20.
No agregues secciones adicionales ni omitas ninguna.

TRANSCRIPCIÓN DE MESA:
{transcript}
"""


def _call_ollama(prompt: str) -> str:
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        },
        timeout=600,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


def summarize_session(transcript_path: str) -> str:
    """Lee el transcript de roleplay y genera wiki/<session>_sesion.md"""
    base = os.path.splitext(os.path.basename(transcript_path))[0]
    session_name = base.replace("_roleplay", "").replace("_full", "")

    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = f.read()

    print(f"[ollama] Generando wiki de sesión con {OLLAMA_MODEL}...")
    content = _call_ollama(SESSION_PROMPT.format(transcript=transcript, session_name=session_name))

    os.makedirs("wiki", exist_ok=True)
    out_path = os.path.join("wiki", f"{session_name}_sesion.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[ollama] Wiki guardado en {out_path}")
    return out_path


PLAYER_PROMPT = """Eres el cronista de una campaña de rol de mesa (Vampiro: La Edad Oscura).
Genera un reporte personal para el jugador {username}. Sigue la estructura exacta
sin agregar ni omitir secciones. Cita timestamps con el formato → [HH:MM:SS]
referenciando el transcript de roleplay.

Tienes acceso a dos transcripts:
- SESIÓN COMPLETA: todo lo que ocurrió en la sesión
- INTERVENCIONES DEL JUGADOR: solo lo que dijo {username}

---

# Reporte de {username} — {session_name}

## Resumen de sesión
Narra lo que vivió el personaje durante la sesión con voz de cronista vampírico —
tono oscuro, íntimo y en tercera persona. Escribe desde la perspectiva del personaje,
no del jugador. Qué enfrentó, qué descubrió, cómo cerró su noche.

## Timeline del personaje
Lista cronológica de lo que hizo el personaje durante la sesión.
- Acción → `[HH:MM:SS]`

## Líneas abiertas
Tramas o conflictos que el personaje dejó sin resolver.
- Línea abierta → `[HH:MM:SS]`

## Información off-role
Lo que el JUGADOR escuchó en la sesión pero su PERSONAJE no debería saber
por circunstancias narrativas. Indica brevemente por qué el personaje no tiene
acceso a esa información.
- Información → `[HH:MM:SS]` — *razón*

---

El formato de cada línea es `[HH:MM:SS] username: texto`. El username es el jugador real.
Usa el username como identificador principal del personaje. Si en el texto aparece un nombre
de personaje distinto al username, puedes usarlo, pero NUNCA inventes nombres que no aparezcan
explícitamente en la transcripción. Si no hay nombre, usa el username.
No agregues secciones adicionales ni omitas ninguna.
Si no hay contenido para una sección, escribe "Ninguna".

SESIÓN COMPLETA:
{full_transcript}

INTERVENCIONES DE {username}:
{player_transcript}
"""


def summarize_player(player_transcript_path: str, full_roleplay_path: str) -> str:
    """Lee el transcript del jugador y la sesión completa, genera wiki/<session>_<username>.md"""
    base = os.path.splitext(os.path.basename(player_transcript_path))[0]
    # base = 2026-03-20_poke4342 (fecha con guiones, username separado por _)
    session_name, username = base.split("_", 1)

    with open(player_transcript_path, "r", encoding="utf-8") as f:
        player_transcript = f.read()

    with open(full_roleplay_path, "r", encoding="utf-8") as f:
        full_transcript = f.read()

    if not player_transcript.strip():
        print(f"[ollama] Sin intervenciones para {username}, omitiendo.")
        return ""

    print(f"[ollama] Generando reporte de {username} con {OLLAMA_MODEL}...")
    prompt = PLAYER_PROMPT.format(
        username=username,
        session_name=session_name,
        full_transcript=full_transcript,
        player_transcript=player_transcript,
    )
    content = _call_ollama(prompt)

    os.makedirs("wiki", exist_ok=True)
    out_path = os.path.join("wiki", f"{session_name}_{username}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[ollama] Reporte de {username} guardado en {out_path}")
    return out_path


def summarize_mesa(transcript_path: str) -> str:
    """Lee el transcript de mesa y genera wiki/<session>_mesa.md"""
    base = os.path.splitext(os.path.basename(transcript_path))[0]
    session_name = base.replace("_mesa", "").replace("_full", "")

    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = f.read()

    if not transcript.strip():
        print("[ollama] Sin contenido de mesa, omitiendo informe técnico.")
        return ""

    print(f"[ollama] Generando informe de mesa con {OLLAMA_MODEL}...")
    content = _call_ollama(MESA_PROMPT.format(transcript=transcript, session_name=session_name))

    os.makedirs("wiki", exist_ok=True)
    out_path = os.path.join("wiki", f"{session_name}_mesa.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[ollama] Informe de mesa guardado en {out_path}")
    return out_path
