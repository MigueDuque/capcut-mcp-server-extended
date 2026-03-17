Edita un proyecto CapCut existente agregando subtítulos al PROYECTO ORIGINAL.

## Parámetros

Solicita los que no haya proporcionado:

- draft_path (requerido): ruta a la carpeta del draft
- typography_style (opcional, default: defaultTypeWhite): defaultTypeWhite | defaultTypeBlack | defaultTypeRed
- animation_in (opcional, default: popInUpper): popInUpper | ninguna
- position_y (opcional, default: -0.4): Y del subtítulo en coordenadas transform; -1=fondo, 0=centro, 1=tope
- position_x (opcional, default: 0.0): X del subtítulo; -1=izquierda, 0=centro, 1=derecha
- screen_type (opcional, default: mobile):
    mobile  → 1080×1920
    desktop → 1920×1080
    custom  → preguntar screen_width y screen_height
- whisper_model (opcional, default: base): tiny | base | small | medium | large
- confirm_transcription (opcional, default: true)
- fade_duration (opcional, default: 0.2): duración del fade de entrada en segundos. 0.167 = 5 frames a 30fps (rápido, ideal subtítulos), 0.4 = medio, 1.5 = lento
- align (opcional, default: center): alineación horizontal de las palabras — left | center

## Variables

```
PYTHON=/c/Users/Migue/AppData/Local/Programs/Python/Python311/python
TMP_DIR=C:/smart_cut/tmp
WORDS_TMP={TMP_DIR}/capcut_words_$$.json
DRAFT_JSON={draft_path}/draft_content.json

# Resolución según screen_type
screen_type=mobile  → SCREEN_WIDTH=1080  SCREEN_HEIGHT=1920
screen_type=desktop → SCREEN_WIDTH=1920  SCREEN_HEIGHT=1080
screen_type=custom  → preguntar al usuario
```

---

## Pasos

### Paso 0 — Crear directorio temporal

```bash
mkdir -p "{TMP_DIR}"
```

(No usar /tmp ni C:/Windows/Temp — solo C:/smart_cut/tmp)

### Paso 1 — Inspeccionar + validar (en paralelo)

```bash
PYTHONUTF8=1 {PYTHON} utils_py/inspect_draft.py "{DRAFT_JSON}"
PYTHONUTF8=1 {PYTHON} utils_py/validate_project.py "{DRAFT_JSON}"
```

Extrae `audio_path`, `duration_sec`, `fps`. Abortar si `valid: false` o no hay audio.

### Paso 2 — Transcribir

```bash
PYTHONUTF8=1 {PYTHON} utils_py/transcribe_audio.py "{audio_path}" \
  --lang es --model {whisper_model} > {WORDS_TMP}
```

### Paso 3 — Confirmar transcripción (si confirm_transcription es true)

Leer `{WORDS_TMP}`, mostrar palabras numeradas con tiempos, esperar correcciones del usuario.
Aplicar correcciones y sobreescribir `{WORDS_TMP}` con la lista corregida.

### Paso 4 — Pipeline completo (palabra por palabra + merge)

```bash
PYTHONUTF8=1 {PYTHON} utils_py/edit_draft_pipeline.py \
  --draft          "{DRAFT_JSON}" \
  --words          "{WORDS_TMP}" \
  --style          {typography_style} \
  --animation      {animation_in_or_none} \
  --position_x     {position_x} \
  --position_y     {position_y} \
  --screen_width   {SCREEN_WIDTH} \
  --screen_height  {SCREEN_HEIGHT} \
  --fade_duration  {fade_duration} \
  --align          {align} \
  --word-by-word
```

- Si animation_in es "ninguna" → pasar `--animation none`
- `--word-by-word` (default): una palabra por elemento, centrada, `position_y` fijo — NO agrupar en frases
- Este script hace todo: API calls paralelos + merge in-place + backup
- No crear drafts nuevos, no llamar otros tools MCP

### Paso 5 — Resumen

```
✓ Subtítulos agregados
──────────────────────────────
Proyecto:  {draft_path}
Frases:    {phrases_added}  (de {source_words} palabras)
Duración:  {duration_sec}s
Estilo:    {typography_style}
Animación: {animation_in}
```

Recordar al usuario cerrar y reabrir CapCut para ver los cambios.

### Paso 6 — Limpiar archivos temporales

```bash
rm -f "{WORDS_TMP}"
```