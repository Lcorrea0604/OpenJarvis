# JARVIS — Avance y pasos a seguir

_Última actualización: viernes 30 de octubre de 2026, mañana (Lima)._

## Resumen en una línea

Jarvis conversa en español por texto y por voz, se activa diciendo "Jarvis" sin tocar nada, muestra un HUD animado estilo Iron Man, abre apps y webs, controla el volumen, lee el estado de tu PC y recuerda lo que le cuentas. Usa Gemini gratis como cerebro y corre en tu laptop con Windows.

## Estado por fase

| Fase | Qué es | Estado | PR |
|---|---|---|---|
| 1 | Chat por texto en español, personalidad de Jarvis, búsqueda web y calculadora | ✅ en `main` | #1 |
| — | Cerebro gratis con Gemini (`jarvis-es-gratis`) y plan de migración a Ollama | ✅ en `main` | #2, #3 |
| 2 | Voz: Whisper (oído local) + Edge TTS (voz peruana) + fecha y hora | ✅ en `main` | #4 |
| 2.1 | Arreglos de voz: Whisper en CPU, reintentos de voz, contexto de Perú | ✅ en `main` | #7 |
| 3a | Manos libres con "Jarvis" (reconoce "ya lo viste"), acceso directo y arranque con Windows | ✅ en `main` | #7, #8, #9 |
| 3b | HUD animado estilo Iron Man | ✅ en `main` | #7 |
| 4 | Herramientas de Windows: abrir apps, webs y carpetas; estado del PC; volumen y música | ✅ en `main` | #7 |
| 5 | Memoria y perfil del usuario (`USER.md` y `MEMORY.md`, solo en tu PC) | ✅ en `main` | #7 |
| 4b | Trello por voz: resumen de tableros, vencimientos, crear, mover y comentar tarjetas | 🟡 PR abierto | #10 |
| 4c | Gmail y Google Calendar | 📋 siguiente | — |
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

1. **Acepta el PR nocturno (#7)** en https://github.com/Lcorrea0604/OpenJarvis/pull/7 → **Merge pull request** → **Confirm merge**. Incluye todo lo de los PR #5 y #6; al aceptarlo, esos quedan cerrados solos. No aceptes el #5 ni el #6 por separado.
2. En PowerShell, dentro de `Desktop\Jarvis`, pega esta línea completa:
   ```powershell
   git pull; uv sync --extra inference-cloud --extra inference-google --extra speech --extra voice-edge; uv run jarvis init --preset jarvis-es-gratis --force
   ```
3. Crea los accesos directos (una sola vez). Quita `-AlIniciar` si no quieres que arranque con Windows:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\windows\instalar-accesos.ps1 -AlIniciar
   ```
4. Doble clic en el ícono **JARVIS** del escritorio. Se abren dos ventanas: la consola de Jarvis y el HUD. Di: **"Jarvis, ¿qué hora es?"**
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

## Trello (30 de octubre)

Jarvis ya puede trabajar con tus tableros de Trello: "Jarvis, ¿qué tengo vencido esta semana?", "Jarvis, mueve la tarjeta del switch a En curso". Para activarlo, acepta el PR #10, haz `git pull` y sigue la sección 9 de `JARVIS-ES.md`: sacar la API Key y el token, y correr `scripts\windows\configurar-trello.ps1`. Antes de crear, mover, comentar o completar una tarjeta, Jarvis siempre te pide confirmación.

## Novedades del trabajo nocturno

Todo esto está en el **PR #7 (nocturno)**. Lo probé con 51 tests nuevos, y además comparé toda la batería de tests contra tu `main` original: tiene las mismas 26 fallas que ya existían (vienen del entorno de pruebas) y ninguna nueva. Lo que no pude probar aquí es el micrófono, los parlantes ni abrir apps de verdad: eso solo se ve en tu laptop.

### 1. HUD animado estilo Iron Man
- Es un reactor con anillos giratorios, la hora y lo último que dijeron tú y Jarvis.
- **Cian** cuando espera o te escucha: las barras se mueven con tu voz. **Dorado** cuando piensa. **Blanco** cuando habla. **Rojo** si falla algo.
- Lo abre el ícono **JARVIS**, o `uv run jarvis chat --hands-free --hud`. Es una página local (`http://127.0.0.1:8765`) que solo se ve en tu PC.

### 2. Control del PC por voz
| Dile… | Qué hace |
|---|---|
| "Jarvis, abre YouTube" / "abre Gmail" / "abre sunat.gob.pe" | Abre la web |
| "Jarvis, abre Excel" / "la calculadora" / "Spotify" / "configuración del wifi" | Abre la app (también busca en el menú Inicio) |
| "Jarvis, abre mis descargas" | Abre la carpeta |
| "Jarvis, ¿cómo está la batería?" / "¿cuánta RAM estoy usando?" | Lee el estado del PC |
| "Jarvis, sube el volumen" / "silencia" / "pausa la música" / "siguiente canción" | Volumen y música |

Por seguridad, Jarvis **no** ejecuta comandos ni borra archivos: solo abre lo que ya tienes instalado, webs y tus carpetas.

### 3. Memoria
- Prueba: *"Jarvis, recuerda que me llamo Russo y trabajo en soporte TI en Lima."* La próxima vez que lo abras ya lo sabrá.
- Se guarda solo en tu PC (`C:\Users\LENOVO\.openjarvis\USER.md` y `MEMORY.md`), nunca en GitHub.
- No guarda contraseñas ni datos bancarios.

### 4. Manos libres más afinado
- Reconoce "Jarvis" aunque Whisper escriba "Yarvis" o "Harvis".
- "Jarvis, apágate" lo cierra. Si preguntas "¿cómo se dice adiós en inglés?", no se apaga.
- Después de cada respuesta tienes 8 segundos para seguir hablando sin repetir su nombre.

### Qué probar primero (checklist)
1. "Jarvis, ¿qué hora es?" → el HUD pasa a dorado y luego a blanco, y te responde con voz.
2. "Jarvis, abre YouTube" → se abre en el navegador.
3. "Jarvis, sube el volumen" → sube unos 10 %.
4. "Jarvis, ¿cómo está la batería?"
5. "Jarvis, recuerda que me llamo Russo." Luego "Jarvis, apágate", ábrelo de nuevo y pregúntale "¿cómo me llamo?".

Si algo falla, copia el texto de la ventana de Jarvis y pégamelo.

### Ideas para la siguiente sesión
- **Gmail y Calendar:** que lea tus correos y tu agenda del día. OpenJarvis ya trae los conectores; solo falta conectarlos (`jarvis connect gdrive`).
- **Resumen matutino:** que al encender la PC te salude con la hora, el clima, el tipo de cambio y tu agenda.
- **Voz más rápida:** que empiece a hablar mientras todavía genera la respuesta.
- **Whisper en GPU:** instalar CUDA para transcribir más rápido con tu NVIDIA.
- **Ollama:** probar `qwen3.5:9b` local con tus 24 GB de RAM y comparar contra Gemini.

### Nota de privacidad
En manos libres, el micrófono está siempre abierto, pero el audio se procesa **solo en tu PC** con Whisper. A Gemini únicamente se envía lo que dices después de "Jarvis".
