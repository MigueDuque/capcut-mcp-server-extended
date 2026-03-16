Agrega texto animado al draft de CapCut activo usando los presets de tipografía y animación definidos en el proyecto.

## Parámetros

Solicita al usuario los que no haya proporcionado:

- draft_id (requerido): ID del draft activo
- text (requerido): contenido del texto
- start (requerido): tiempo de inicio en segundos
- end (requerido): tiempo de fin en segundos
- position_x (opcional, default: 0.5): posición horizontal 0.0-1.0
- position_y (opcional, default: 0.85): posición vertical 0.0-1.0
- typography_style (opcional, default: defaultTypeWhite): defaultTypeWhite | defaultTypeBlack | defaultTypeRed
- animation_in (opcional, default: popInUpper): popInUpper | ninguna

## Presets disponibles (definidos en src/presets/)

**Estilos de tipografía** (`src/presets/typography.ts`):
- `defaultTypeWhite`: #ecebeb, Poppins_Bold, stroke negro thickness=40, shadow negro alpha=25% blur=23 dist=10 angle=-70°
- `defaultTypeBlack`: #000000, Poppins_Bold, sin stroke, sin shadow
- `defaultTypeRed`: #aa1a1a, Poppins_Bold, sin stroke, sin shadow

**Animaciones** (`src/presets/animations.ts`):
- `popInUpper`: cae desde 0.05 unidades arriba con fade-in, 13 frames (≈433ms a 30fps)

## Ejecución

Llama el tool MCP `capcut_add_animated_text` con los parámetros recibidos.
El tool aplica automáticamente todos los parámetros del estilo (stroke, shadow completo)
y la animación con keyframes — no es necesario especificarlos manualmente.

Confirma el resultado mostrando:

```
✓ Texto agregado
──────────────────────
Draft:      {draft_id}
Texto:      "{text}"
Estilo:     {typography_style}
Animación:  {animation_in}
Timing:     {start}s → {end}s
Posición:   x={position_x}, y={position_y}
```
