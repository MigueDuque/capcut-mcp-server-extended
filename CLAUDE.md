# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**capcut-mcp-server-extended** is a Model Context Protocol (MCP) server that bridges AI assistants
(Claude, etc.) with CapCut Pro video editing via a VectCutAPI backend. It is a fork of
`atx-guy/capcut-mcp-server` extended toward a professional video automation tool, with a focus on
**talking head / reels content**: vertical 1080×1920 videos, auto-subtitles, animated text, and
composable presets that collapse multi-step workflows into a single tool call.

The end goal is to let an AI assistant produce a fully-edited short video by issuing a handful of
MCP tool calls — no manual CapCut interaction required.

---

## Commands

```bash
# Build (compile TypeScript → dist/, make dist/index.js executable)
npm run build

# Development (watch mode, recompiles on change)
npm run dev

# Run the compiled server
npm start
```

No test scripts are configured. The server starts and communicates over stdio (default) or HTTP.
Always run `npm run build` after every code change and confirm zero errors before committing.

---

## Architecture

**Transport modes** (set via `TRANSPORT` env var):
- `stdio` (default) — for Claude Desktop / local MCP clients
- `http` — listens on `PORT` (default 3000)

**Key env vars**: `CAPCUT_API_URL` (default `http://localhost:9001`), `PORT`, `TRANSPORT`

**VectCutAPI backend**: runs at `http://localhost:9001`. Useful endpoints:
- `GET /get_font_types` — returns the full list of supported font names
- `POST /create_draft`, `/add_video`, `/add_text`, `/add_keyframe`, `/save_draft`, etc.

### Data flow

```
MCP Client
  → src/tools/index.ts          (tool registration + Zod validation)
  → src/tools/presets.ts        (high-level composite tools — Phase 3+)
  → src/services/api-client.ts  (axios singleton, 60 s timeout)
  → VectCutAPI backend          (http://localhost:9001)
```

### Source layout

| File / Dir | Role |
|---|---|
| `src/index.ts` | Entry point; stdio/HTTP transport setup — **do not modify** |
| `src/tools/index.ts` | All 13 MCP tool definitions; `formatResponse` / `handleError` helpers |
| `src/tools/presets.ts` | High-level composite tools (Phase 3+) |
| `src/schemas/index.ts` | Zod schemas for every base tool input |
| `src/services/api-client.ts` | Singleton `apiClient`; maps tool calls → POST endpoints — **do not modify** |
| `src/types.ts` | TypeScript interfaces (`DraftConfig`, `VideoTrack`, `ResponseFormat`, …) |
| `src/constants.ts` | `API_BASE_URL`, defaults, supported formats, effects, transitions |
| `src/presets/typography.ts` | **[Phase 1 ✅]** Three named text styles; font = `Poppins_Bold` |
| `src/presets/animations.ts` | **[Phase 2 ✅]** Keyframe animation sequences (`popInUpper`) |
| `src/utils/validators.ts` | **[Phase 5]** Path validation, Windows↔Unix helpers |
| `utils_py/transcribe_audio.py` | Whisper word-level transcription; outputs JSON word list |
| `utils_py/inspect_draft.py` | Reads `draft_content.json`; extracts audio path, duration, fps |
| `utils_py/validate_project.py` | Checks that all media files referenced in a draft exist |

### 13 MCP tools

```
capcut_create_draft
  → capcut_add_video / capcut_add_audio / capcut_add_text
  → capcut_add_image / capcut_add_subtitle / capcut_add_keyframe
  → capcut_add_effect / capcut_add_sticker
  → capcut_save_draft

capcut_get_duration          (read-only — queries media metadata)
capcut_add_animated_text     (add_text + keyframe animation in one call)
capcut_edit_draft_words      (full pipeline: create draft → add video → add words → save)
```

All tools accept `response_format: 'markdown' | 'json'`.
Markdown uses `formatResponse()` for human-readable output; JSON returns `structuredContent`.

---

## Code Conventions

- **TypeScript strict mode** — `strict: true`, `noUnusedLocals`, `noUnusedParameters`,
  `noImplicitReturns` are all enabled in `tsconfig.json`. Avoid `any`; use typed generics or
  `unknown` + type guards when the shape is truly dynamic.
- **ESM modules** — `"type": "module"` in package.json. All local imports must include the `.js`
  extension (even for `.ts` source files). Example: `import { foo } from './bar.js'`.
- **Tool naming** — all MCP tools use `snake_case` with the `capcut_` prefix.
- **Schema-first** — every tool input must have a matching Zod schema exported from
  `src/schemas/index.ts` (base tools) or co-located with the preset file (preset tools).
- **Preset exports** — each preset file exports:
  1. A `const` object with the preset values (e.g. `TYPOGRAPHY_STYLES`).
  2. A Zod schema derived from those values (e.g. `TypographyStyleNameSchema`).
  3. The inferred TypeScript type (e.g. `type TypographyStyleName`).
- **Comments in English** — all inline comments, JSDoc, and commit messages in English.
- **No modification of stable files** — `src/index.ts` and `src/services/api-client.ts` are
  stable; do not touch them unless there is a breaking backend change.
- **Build gate** — `npm run build` must pass with zero errors after every change.

### Adding a new base tool

1. Add types to `src/types.ts` if needed.
2. Add a Zod schema + inferred type to `src/schemas/index.ts`.
3. Add the API method to `src/services/api-client.ts`.
4. Register the tool inside `registerTools()` in `src/tools/index.ts`.
5. Run `npm run build`.

### Adding a new preset/composite tool

1. Define the preset data in the appropriate `src/presets/*.ts` file.
2. Add its Zod schema and TypeScript type there too.
3. Register the tool in `src/tools/presets.ts` (create the file if needed).
4. Import and call `registerPresetTools(server)` from `src/index.ts` if not already done.
5. Run `npm run build`.

---

## Sistema de tipografía y animaciones

Cuando el usuario pida agregar texto a un clip, SIEMPRE usar
`capcut_add_animated_text` en lugar de `capcut_add_text`.

### Estilos disponibles (`typography_style`)

Definidos en `src/presets/typography.ts`. Los tres usan `Poppins_Bold` como fuente.

| Nombre | Color | Stroke | Shadow | Cuándo usarlo |
|---|---|---|---|---|
| `defaultTypeWhite` | `#ecebeb` | negro, thickness=40 | sí | Uso general — fondo oscuro |
| `defaultTypeBlack` | `#000000` | no | no | Fondos claros |
| `defaultTypeRed` | `#aa1a1a` | no | no | Énfasis, alertas, labels |

Si el usuario no especifica estilo, usar `defaultTypeWhite`.

### Fuentes soportadas por la API

La lista completa se obtiene con `GET http://localhost:9001/get_font_types`.
Fuentes recomendadas para contenido en español (latinas, bien legibles en reels):

| Uso | Fuente |
|---|---|
| Título / palabra bold | `Poppins_Bold`, `Sora_Bold`, `Inter_Black`, `Kanit_Black` |
| Subtítulo / body | `Poppins_Regular`, `Sora_Regular`, `Nunito` |
| Display / impacto | `Thunder`, `Staatliches_Regular`, `Bungee_Regular` |

`Montserrat-Bold` **no está soportada** por la API — usar `Poppins_Bold` como equivalente.

### Animaciones disponibles (`animation_in`)

Definidas en `src/presets/animations.ts`.

| Nombre | Descripción | Duración |
|---|---|---|
| `popInUpper` | Cae desde ligeramente arriba (offset +0.05) con fade in | 13 frames (≈433 ms a 30 fps) |

**Dirección**: en el espacio de keyframes de CapCut, el eje Y positivo apunta hacia ARRIBA en
pantalla. El offset `+0.05` hace que el elemento empiece 0.05 unidades más arriba y "caiga" a
su posición final — efecto de entrada descendente suave.

Si el usuario no especifica animación, aplicar `popInUpper` por defecto para texto principal.

### Parámetros por defecto para talking head

| Parámetro | Valor | Motivo |
|---|---|---|
| `position_x` | `0.5` | Centrado horizontal |
| `position_y` | `0.85` | Texto animado principal (near top); subtítulos → usar `0.10` |
| `start` / `end` | según timing del clip indicado | — |

**Convención Y**: `0 = fondo de pantalla`, `1 = tope de pantalla` (positivo = hacia arriba).

---

## Python utilities (`utils_py/`)

Scripts auxiliares que se llaman desde Claude Code con el Python del sistema
(`/c/Users/Migue/AppData/Local/Programs/Python/Python311/python`).
Siempre ejecutar con `PYTHONUTF8=1` para evitar errores de encoding en Windows.

### `transcribe_audio.py`

Transcribe un archivo de audio/video con Whisper y retorna una lista JSON de palabras con
timestamps. Aplica corrección automática de solapamientos: si `word[i].start < word[i-1].end`,
ajusta `word[i].start = word[i-1].end + 0.01`.

```bash
python utils_py/transcribe_audio.py "path/to/video.mov" --lang es --model base
# Output: [{ "word": "...", "start": 0.44, "end": 0.88 }, ...]
```

Modelos disponibles: `tiny` | `base` | `small` | `medium` | `large`

### `inspect_draft.py`

Lee un `draft_content.json` de CapCut y extrae `audio_path`, `duration_sec` y `fps`.

```bash
python utils_py/inspect_draft.py "path/to/draft_content.json"
```

### `validate_project.py`

Verifica que todos los archivos de media referenciados en el draft existan en disco.

```bash
python utils_py/validate_project.py "path/to/draft_content.json"
# Output: { "valid": true/false, "missing": [...] }
```

### `group_words.py`

Agrupa una lista de palabras con timestamps en frases/subtítulos completos. Rompe la frase
cuando se supera el máximo de caracteres, hay una pausa larga, o la palabra termina con `.?!…`.

```bash
python utils_py/group_words.py words.json --max-chars 35 --max-gap 0.5
# Input:  [{"word":"Hola","start":0.5,"end":0.8}, {"word":"mundo","start":0.8,"end":1.2}]
# Output: [{"text":"Hola mundo","start":0.5,"end":1.2}]
```

Parámetros:
- `--max-chars` (default: 35) — máximo de caracteres por frase
- `--max-gap` (default: 0.5s) — pausa máxima para mantener palabras en la misma frase

### `calc_subtitle_y.py`

Agrupa palabras en frases y asigna un `position_y` específico a cada frase según su
número estimado de líneas visuales. Usa internamente `group_words`.

**Convención de ejes**: `0 = fondo de pantalla`, `1 = tope`. Valores bajos = más abajo.

```bash
python utils_py/calc_subtitle_y.py words.json --base_y 0.10
# Output: [{"text":"Compramos la Mazda","start":0.58,"end":2.3,"position_y":0.16}, ...]
```

Parámetros:
- `--base_y` (default: 0.10) — Y del centro de una frase de 1 línea
- `--line_height` (default: 0.06) — unidades Y por línea adicional
- `--chars_per_line` (default: 20) — caracteres estimados por línea visual (~3 palabras)
- `--max-chars` (default: 35) — máx caracteres por frase
- `--max-gap` (default: 0.5s) — pausa máxima para mantener palabras juntas

**Fórmula**: `position_y = base_y + (n_lines − 1) × line_height`
→ frases de 2 líneas suben el centro para que el borde inferior quede en `base_y`.

Este módulo es **importado automáticamente** por `edit_draft_pipeline.py` cuando se
usa el modo `--no-word-by-word --no-buildup` (modo frases). No es necesario llamarlo directamente.

### `edit_draft_pipeline.py` ⭐ script principal

Pipeline unificado con llamadas API **paralelas** (ThreadPoolExecutor, 8 workers).
Hace todo en una sola ejecución: preparar entradas → crear draft temp →
agregar elementos en paralelo → merge en draft existente.

**Modos disponibles**:
- `--word-by-word` (default) — una palabra por elemento, centrada, `position_y` fijo
- `--no-word-by-word --no-buildup` — una frase completa por elemento, `position_y` ajustado por líneas
- `--no-word-by-word --buildup` — layout horizontal acumulativo por frase (legado)

```bash
python utils_py/edit_draft_pipeline.py \
  --draft "C:/path/to/draft_content.json" \
  --words words.json \
  --style defaultTypeWhite --animation popInUpper \
  --position_y 0.10
# Output: {"entries_added":25,"source_words":25,"text_tracks_merged":25,"mode":"word_by_word",...}
```

Archivos temporales: usar siempre `C:/smart_cut/tmp/` como directorio intermedio.

**Rendimiento**: para 25 palabras hace ~75 llamadas API en paralelo.
Tiempo estimado: 3-6s.

### `add_words_to_draft.py`

Agrega subtítulos de palabras o frases directamente a un `draft_content.json` EXISTENTE, sin
crear un nuevo proyecto. Usa VectCutAPI para generar los elementos de texto y luego hace un
merge del JSON resultante al draft original.

**Ventaja**: preserva todos los tracks existentes (video, B-roll, audio, efectos).

```bash
python utils_py/add_words_to_draft.py \
  --draft  "C:/path/to/draft_content.json" \
  --words  '[{"word":"Hola","start":0.5,"end":1.0}, ...]' \
  --style  defaultTypeWhite \
  --animation popInUpper \
  --position_x 0.5 \
  --position_y 0.85
# Output: {"temp_draft_id":"...","entries_added":25,"text_tracks_merged":25,...}
```

También acepta frases (clave `"text"` en lugar de `"word"`):
```bash
python utils_py/group_words.py words.json | python utils_py/add_words_to_draft.py \
  --draft "C:/path/to/draft_content.json" --words -
```
*(pasar `-` como `--words` no está implementado; guardar a archivo intermedio primero)*

Crea backup automático en `draft_content.json.bak_words` (solo si no existe).

---

## Flujo típico: subtítulos sobre proyecto EXISTENTE

Para agregar subtítulos a un proyecto CapCut ya existente (preservando B-roll, efectos, etc.):

```bash
# 1. Transcribir audio
python utils_py/transcribe_audio.py "video.mov" --lang es --model medium

# 2. Agrupar palabras en frases (opcional, recomendado)
python utils_py/group_words.py words.json --max-chars 35 > phrases.json

# 3. Agregar al draft existente
python utils_py/add_words_to_draft.py \
  --draft "C:/Users/.../draft_content.json" \
  --words phrases.json \
  --style defaultTypeWhite \
  --animation popInUpper
```

## Flujo alternativo: draft completo nuevo

El tool `capcut_edit_draft_words` ejecuta el pipeline completo en una sola llamada
(crea un proyecto NUEVO, útil cuando no existe draft previo):

1. `POST /create_draft` — crea draft 1080×1920 al fps indicado
2. `POST /add_video` — agrega el video principal (full duration)
3. `POST /add_text` × N + `POST /add_keyframe` × N — una entrada por llamada con animación
4. `POST /save_draft` — guarda; luego `publishDraftToCapcut()` lo copia a la carpeta de CapCut

**Nota**: timestamps solapados en la transcripción de Whisper causan error `New segment overlaps`.
El script ya los corrige automáticamente, pero si se construye la lista manualmente, asegurarse
de que `word[i].start >= word[i-1].end`.

---

## Roadmap

### FASE 1 — Parametric typography system ✅
`src/presets/typography.ts` — tres estilos base (`defaultTypeWhite`, `defaultTypeBlack`,
`defaultTypeRed`), todos con `Poppins_Bold`, font_size 15, configurables en color/stroke/shadow.

### FASE 2 — Animation library ✅
`src/presets/animations.ts` — `popInUpper`: cae desde ligeramente arriba (offset +0.05) con
fade in. Dirección corregida: en keyframe space CapCut, y positivo = más alto en pantalla.
`resolveKeyframes()` convierte la definición en llamadas a `apiClient.addKeyframe`.

### FASE 3 — Word-by-word pipeline tool ✅
`capcut_edit_draft_words` en `src/tools/index.ts` — pipeline completo: crea draft, agrega
video, agrega cada entrada como texto animado, guarda y publica a CapCut vía `publishDraftToCapcut()`.
`utils_py/edit_draft_pipeline.py` — modo por defecto `--word-by-word`: una palabra por elemento,
centrada, sin agrupación. Modos alternativos: `--no-word-by-word --no-buildup` (frases),
`--no-word-by-word --buildup` (layout acumulativo legado).
`utils_py/add_words_to_draft.py` — agrega subtítulos a un proyecto existente (merge directo).

### FASE 4 — Enhanced subtitle tool
Extender `capcut_add_subtitle` para soportar:
- Estilos predefinidos: `"reels"`, `"youtube"`, `"minimal"`, `"bold"`
- `word_highlight` — resaltar palabras clave en otro color
- `auto_position` — `"top"` | `"center"` | `"bottom"`

### FASE 5 — Validation & utilities
`src/utils/validators.ts`:
- Validar que `video_path` exista antes de enviar a la API
- Validar que `draft_folder` sea una ruta válida de CapCut
- Helper para convertir rutas Windows ↔ Unix

---

## Do Not Touch (for now)

- `src/index.ts` — stable entry point
- `src/services/api-client.ts` — functional API client
- The 13 existing tools — extend only, never modify existing behavior
