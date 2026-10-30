# JARVIS en español

Este fork de [OpenJarvis](https://github.com/open-jarvis/OpenJarvis) es un asistente personal en español con la personalidad de Jarvis. Usa a Claude (Anthropic) como cerebro y se puede usar por texto y por voz.

## Hoja de ruta

| Fase | Qué incluye | Estado |
|---|---|---|
| 1 | Chat por texto en español, personalidad de Jarvis, Claude como cerebro y búsqueda web | ✅ listo |
| 2 | Voz completa: micrófono → Whisper → Claude → voz | ⏳ |
| 3 | Palabra de activación "Jarvis" y HUD animado estilo Iron Man | ⏳ |
| 4 | Herramientas de Windows: abrir apps, archivos, Gmail y Calendar | ⏳ |
| 5 | Memoria de largo plazo y perfil del usuario | ⏳ |

## Instalación en Windows (fase 1)

### 1. Instalar OpenJarvis desde este fork

Abre PowerShell en la carpeta del repo y ejecuta:

```powershell
cd $HOME\Desktop\Jarvis
irm https://astral.sh/uv/install.ps1 | iex   # instala uv (gestor de Python), solo la primera vez
```

Cierra PowerShell, ábrelo de nuevo y sigue:

```powershell
cd $HOME\Desktop\Jarvis
uv sync --extra inference-cloud
```

Este comando crea el entorno de Python e instala todo, incluido el conector con Claude (`inference-cloud`). La primera vez tarda unos minutos.

### 2. Configurar tu API key de Anthropic

Saca la clave en https://console.anthropic.com → **API Keys**. Luego, en PowerShell:

```powershell
setx ANTHROPIC_API_KEY "sk-ant-TU-CLAVE-AQUI"
```

Cierra y vuelve a abrir PowerShell para que la variable se cargue.

> La clave queda guardada solo en tu Windows. Nunca la pegues en el código ni la subas a GitHub.

### 3. Activar el preset de Jarvis en español

```powershell
cd $HOME\Desktop\Jarvis
uv run jarvis init --preset jarvis-es --force
```

Este comando copia la configuración a `C:\Users\<tu-usuario>\.openjarvis\config.toml`.

### 4. Hablar con Jarvis

```powershell
uv run jarvis chat
```

Prueba, por ejemplo:

- `Hola Jarvis, preséntate.`
- `¿Cuál es el tipo de cambio del dólar hoy en Perú?`
- `Calcula el 18 % de IGV sobre 2 450 soles.`

Para la interfaz gráfica en el navegador (necesita Node.js 22 o superior):

```powershell
uv run jarvis gui
```

## Personalizar a Jarvis

- **Personalidad:** edita `default_system_prompt` en `~\.openjarvis\config.toml`.
- **Tus datos** (cómo te llamas, a qué te dedicas, tu ciudad): crea el archivo `~\.openjarvis\USER.md` y escribe ahí lo que Jarvis debe saber de ti. Así esos datos no quedan en el repo público.
- **Modelo:** cambia `default_model`. `claude-haiku-4-5` es más rápido y barato; `claude-opus-4-6` es el más capaz.

## Traer mejoras del proyecto original

```powershell
git fetch upstream
git merge upstream/main
```

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `jarvis` no se reconoce | Antepón `uv run`: `uv run jarvis chat` |
| "No inference engine available" | Falta el conector con Claude o la clave: corre `uv sync --extra inference-cloud` y revisa `echo $env:ANTHROPIC_API_KEY` en una terminal nueva |
| `401 invalid x-api-key` | La clave está mal copiada: repite `setx` con la clave correcta |
| `uv` no se reconoce | Cierra y abre PowerShell después de instalarlo |
| Responde en inglés | Verifica que corriste `jarvis init --preset jarvis-es --force` |

Cualquier otro error: corre `uv run jarvis doctor` y comparte la salida.
