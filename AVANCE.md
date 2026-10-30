# JARVIS — Avance y pasos a seguir

_Última actualización: jueves 29 de octubre de 2026, 21:40 (Lima). Se actualiza al final de cada sesión._

## Resumen en una línea

Jarvis ya conversa en español por texto y por voz, con personalidad de mayordomo, voz peruana y modo manos libres activado con la palabra "Jarvis". Usa Gemini gratis como cerebro y corre en tu laptop con Windows.

## Estado por fase

| Fase | Qué es | Estado | PR |
|---|---|---|---|
| 1 | Chat por texto en español, personalidad de Jarvis, búsqueda web y calculadora | ✅ en `main` | #1 |
| — | Cerebro gratis con Gemini (`jarvis-es-gratis`) y plan de migración a Ollama | ✅ en `main` | #2, #3 |
| 2 | Voz: Whisper (oído local) + Edge TTS (voz peruana) + fecha y hora | ✅ en `main` | #4 |
| 2.1 | Arreglos de voz: Whisper en CPU, reintentos de voz, contexto de Perú | 🟡 PR abierto | #5 |
| 3a | Manos libres con "Jarvis", acceso directo y arranque con Windows | 🟡 PR abierto (incluye #5) | #6 |
| 3b | HUD animado estilo Iron Man | 🌙 trabajo nocturno | nocturno |
| 4 | Herramientas de Windows: abrir apps, webs y carpetas; estado del sistema | 🌙 trabajo nocturno | nocturno |
| 5 | Memoria y perfil del usuario (`USER.md`) | 🌙 trabajo nocturno | nocturno |
| — | Migración a Ollama local (tu PC tiene 24 GB de RAM, alcanza para `qwen3.5:9b`) | 📋 planificada | — |

## Cómo está configurado tu Jarvis hoy

| Pieza | Qué usa | Costo |
|---|---|---|
| Cerebro | Gemini Flash-Lite (`gemini-flash-lite-latest`), plan gratis, aprox. 500 consultas al día | Gratis |
| Oído | faster-whisper `small` en español, en CPU (tu GPU NVIDIA no tiene CUDA instalado) | Gratis, local |
| Voz | Edge TTS `es-PE-AlexNeural` (hombre peruano), velocidad 1.1 | Gratis, requiere internet |
| Configuración | `C:\Users\LENOVO\.openjarvis\config.toml` | — |
| Código | `C:\Users\LENOVO\Desktop\Jarvis` (tu fork `Lcorrea0604/OpenJarvis`) | — |
| Clave | Variable de entorno `GEMINI_API_KEY` de tu usuario de Windows | — |

## Pasos a seguir mañana (en orden)

1. **Acepta el PR nocturno** (o el #6 si el nocturno aún no existe) en https://github.com/Lcorrea0604/OpenJarvis/pulls → **Merge pull request** → **Confirm merge**. El nocturno incluye todo lo anterior (#5 y #6); al aceptarlo, esos se cierran solos.
2. En PowerShell, dentro de `Desktop\Jarvis`, pega esta línea completa:
   ```powershell
   git pull; uv sync --extra inference-cloud --extra inference-google --extra speech --extra voice-edge; uv run jarvis init --preset jarvis-es-gratis --force
   ```
3. Crea los accesos directos (una sola vez). Quita `-AlIniciar` si no quieres que arranque con Windows:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\windows\instalar-accesos.ps1 -AlIniciar
   ```
4. Doble clic en el ícono **JARVIS** del escritorio y di: **"Jarvis, ¿qué hora es?"**
5. Revisa la sección **"Novedades del trabajo nocturno"** más abajo: ahí explico lo nuevo y cómo probarlo.

## Reglas rápidas para PowerShell

- Con `You>` en pantalla le hablas a Jarvis. Con `PS C:\...>` le das comandos a Windows.
- Escribe los comandos de a uno, o pega la línea completa que ya viene unida con `;`.
- Si ves `>>` al inicio de la línea, PowerShell quedó esperando: pulsa **Ctrl + C**.
- Las comillas curvas (`”`) rompen los comandos: usa siempre comillas rectas (`"`).

## Problemas que ya resolvimos (por si vuelven)

| Síntoma | Causa | Solución |
|---|---|---|
| `uv` no se reconoce | Faltaba instalarlo | `winget install --id astral-sh.uv -e` y abre una PowerShell nueva |
| `401 invalid x-api-key` | Se guardó el texto de ejemplo en vez de la clave real | Método `Read-Host` (ver `JARVIS-ES.md`, paso 3) |
| `404 ... no longer available` | Google retiró `gemini-2.5-flash` | Usar el alias `gemini-flash-lite-latest` |
| `cublas64_12.dll is not found` | Whisper intentó usar la GPU sin CUDA | `speech.device = "cpu"` (ya viene así en el preset) |
| La voz se calla después de un corte | Fallo temporal del servicio de Microsoft | Reintentos automáticos (PR #5) |
| Tipo de cambio en pesos mexicanos | Jarvis no sabía que estás en Perú | El preset asume Lima y soles (PR #5) |

## Pendientes y decisiones abiertas

- **Cerebro:** Gemini gratis por ahora. Para más calidad, Claude (`jarvis-es`) con unos USD 5 en créditos. Para más privacidad, Ollama (`jarvis-es-local`).
- **GPU:** tu laptop tiene NVIDIA. Si instalas CUDA 12 y cuDNN, Whisper transcribe más rápido (`speech.device = "cuda"`). Es opcional.
- **Voz 100 % local:** Kokoro (`em_alex`) evita depender de internet, pero exige instalar PyTorch y espeak-ng.
- **Privacidad:** el repo es público. Tus datos personales van solo en `~\.openjarvis\USER.md`, que no se sube a GitHub.

## Novedades del trabajo nocturno

_(Esta sección se completa al terminar la sesión nocturna.)_
