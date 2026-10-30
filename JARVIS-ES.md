# JARVIS en español

Este fork de [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) es un asistente personal en español con la personalidad de Jarvis. Se puede usar por texto y por voz.

## Hoja de ruta

| Fase | Qué incluye | Estado |
|---|---|---|
| 1 | Chat por texto en español, personalidad de Jarvis y búsqueda web | ✅ listo |
| 2 | Voz completa: micrófono → Whisper → cerebro → voz peruana (Edge TTS), y conoce la fecha y la hora | ✅ listo |
| 3 | Palabra de activación "Jarvis" y HUD animado estilo Iron Man | ⏳ |
| 4 | Herramientas de Windows: abrir apps, archivos, Gmail y Calendar | ⏳ |
| 5 | Memoria de largo plazo y perfil del usuario | ⏳ |
| — | Migración a modelo local con Ollama | 📋 planificada (ver abajo) |

## Elige el cerebro

Jarvis puede funcionar con tres cerebros distintos. La personalidad y las herramientas son las mismas en los tres; solo cambia quién piensa.

| Preset | Cerebro | Costo | Privacidad | Calidad en español |
|---|---|---|---|---|
| `jarvis-es-gratis` | Gemini Flash-Lite (Google) | Gratis, aprox. 500 consultas al día | Google puede usar los chats del plan gratis | Muy buena |
| `jarvis-es` | Claude Sonnet (Anthropic) | De pago, aprox. USD 0,01–0,03 por pregunta | No se usan para entrenar | Excelente |
| `jarvis-es-local` | Qwen 3.5 en Ollama (tu PC) | Gratis | Total: nada sale de tu PC | Aceptable; depende de tu hardware |

**Preset actual en uso: `jarvis-es-gratis`.**

Cambiar de cerebro es un solo comando, `uv run jarvis init --preset <nombre> --force`, y luego hay que reiniciar Jarvis.

## Instalación en Windows

### 1. Programas base (una sola vez)

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
```

Cierra PowerShell y ábrelo de nuevo.

### 2. Descargar el repo e instalar

```powershell
cd $HOME\Desktop\Jarvis
git clone https://github.com/Lcorrea0604/OpenJarvis.git .    # solo la primera vez
git pull                                                     # para traer cambios nuevos
uv sync --extra inference-cloud --extra inference-google --extra speech --extra voice-edge
```

Los extras `speech` y `voice-edge` instalan el oído (Whisper) y la voz (Edge TTS).

### 3. Guardar la clave de API

Usa siempre este método, que te pide la clave al correrlo. Así no tienes que editar el comando:

```powershell
$k = Read-Host "Pega tu clave"
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", $k.Trim(), "User")
```

| Preset | Variable | Dónde se saca la clave |
|---|---|---|
| `jarvis-es-gratis` | `GEMINI_API_KEY` | https://aistudio.google.com → Get API key (gratis, sin tarjeta) |
| `jarvis-es` | `ANTHROPIC_API_KEY` | https://console.anthropic.com → API Keys (necesita créditos) |
| `jarvis-es-local` | ninguna | — |

Cierra PowerShell y ábrelo de nuevo. Luego verifica que la clave quedó guardada:

```powershell
echo $env:GEMINI_API_KEY.Substring(0,6)
echo $env:GEMINI_API_KEY.Length
```

Una clave de Gemini válida tiene entre 39 y 60 caracteres. Si sale 0 o da error, la clave no quedó guardada.

> Las claves quedan guardadas solo en tu Windows. Nunca las pegues en el código ni las subas a GitHub.

### 4. Activar el preset y hablar con Jarvis

```powershell
cd $HOME\Desktop\Jarvis
uv run jarvis init --preset jarvis-es-gratis --force
uv run jarvis chat
```

Prueba, por ejemplo:

- `Hola Jarvis, preséntate.`
- `¿Cuál es el tipo de cambio del dólar hoy en Perú?`
- `Calcula el 18 % de IGV sobre 2 450 soles.`

Para la interfaz gráfica en el navegador (necesita Node.js 22 o superior): `uv run jarvis gui`.

### 5. Hablar con Jarvis por voz

```powershell
uv run jarvis chat --voice
```

- Cuando aparezca `You> [type, or press Enter to speak]`, **pulsa Enter sin escribir nada** y habla.
- Jarvis deja de escuchar solo, cuando haces una pausa de un segundo y medio.
- Te responde con voz por los parlantes. También puedes seguir escribiendo como siempre.
- La primera vez tarda un poco más: descarga el modelo de Whisper (unos 460 MB para `small`).

**Cambiar la voz:** edita `voice_id` en `~\.openjarvis\config.toml`. Por ejemplo, `es-PE-CamilaNeural` para voz de mujer peruana, o `es-MX-JorgeNeural`. La velocidad se cambia en `voice_speed`.

**Si no te escucha:** en Windows ve a Configuración → Privacidad y seguridad → Micrófono, y activa el acceso para las apps de escritorio. Revisa también que el micrófono predeterminado sea el integrado (Configuración → Sistema → Sonido → Entrada).

## Migración futura a Ollama (modelo local)

Este es el plan para que Jarvis funcione sin internet ni API, con todo en tu PC. El preset `jarvis-es-local` ya está listo; solo faltan el hardware y estos pasos.

**Antes de migrar, verifica tu hardware:**

```powershell
Get-CimInstance Win32_ComputerSystem | Select-Object @{n="RAM_GB";e={[math]::Round($_.TotalPhysicalMemory/1GB)}}
Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM
```

| Tu PC | Modelo recomendado | Experiencia esperada |
|---|---|---|
| 8 GB de RAM, sin GPU | `qwen3.5:4b` | Funciona, pero tarda varios segundos por respuesta |
| 16 GB de RAM o GPU NVIDIA con 6–8 GB | `qwen3.5:9b` | Buena; recomendado |
| 32 GB o más, o GPU con 12 GB o más | `qwen3.5:35b` | Muy buena, cercana a la nube |

**Pasos:**

```powershell
winget install --id Ollama.Ollama -e
ollama pull qwen3.5:4b                # o el modelo de la tabla
uv run jarvis init --preset jarvis-es-local --force
uv run jarvis chat
```

Si eliges otro modelo, edita `default_model` en `~\.openjarvis\config.toml`.

**Qué se pierde al migrar:**

- Los modelos chicos usan peor las herramientas: a veces no buscan en la web cuando deberían.
- La voz (fase 2) también corre local y compite por la RAM. En PCs de 8 GB, usa Whisper `base` en lugar de `small`.

**Opción híbrida, para más adelante:** usar Ollama para las preguntas simples y la nube para las difíciles. OpenJarvis ya trae un enrutador (`[learning.routing]`) que lo permite. Lo evaluamos cuando el modo local funcione.

## Personalizar a Jarvis

- **Personalidad:** edita `default_system_prompt` en `~\.openjarvis\config.toml`. Ojo: si vuelves a correr `jarvis init` con otro preset, el archivo se sobrescribe.
- **Tus datos** (cómo te llamas, a qué te dedicas, tu ciudad): crea el archivo `~\.openjarvis\USER.md` y escribe ahí lo que Jarvis debe saber de ti. Así esos datos no quedan en el repo público.

## Traer mejoras del proyecto original

```powershell
git fetch upstream
git merge upstream/main
```

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `jarvis` no se reconoce | Antepón `uv run`: `uv run jarvis chat` |
| `uv` no se reconoce | `winget install --id astral-sh.uv -e` y abre una PowerShell nueva |
| "No inference engine available" | Corre `uv sync --extra inference-cloud --extra inference-google` y revisa la clave en una terminal nueva |
| `401 invalid x-api-key` (Claude) o `API key not valid` (Gemini) | La clave está mal guardada: repite el paso 3 |
| `429` o "quota exceeded" (Gemini) | Llegaste al límite gratuito; espera un minuto, o hasta el día siguiente |
| `404 NOT_FOUND ... no longer available` (Gemini) | Google retiró ese modelo. Usa el alias que siempre funciona: `uv run jarvis config set intelligence.default_model gemini-flash-lite-latest` |
| `Mic error` o "Nothing heard" | Revisa los permisos del micrófono (paso 5). Habla más cerca o más fuerte |
| `cublas64_12.dll is not found` | Whisper intentó usar la tarjeta NVIDIA sin CUDA instalado. Corre `uv run jarvis config set speech.device cpu` (los presets ya usan CPU) |
| Avisos de `symlinks` o `HF_TOKEN` al iniciar | Son solo avisos de la descarga del modelo de Whisper; no afectan |
| No se escucha la voz | Revisa que tengas internet (Edge TTS es en línea) y que el volumen no esté en silencio |
| Responde en inglés | Verifica que corriste `jarvis init --preset jarvis-es-gratis --force` |

Cualquier otro error: corre `uv run jarvis doctor` y comparte la salida.
