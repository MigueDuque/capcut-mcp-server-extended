# CapCut MCP Server — Extended

An extended MCP (Model Context Protocol) server for automating 
CapCut video editing through Claude Code. Supports parametrized 
typography, animation presets, and full talking-head production workflows.

## Based on

This project is a fork and extension of 
[capcut-mcp-server](https://github.com/atx-guy/capcut-mcp-server) 
by [@atx-guy](https://github.com/atx-guy), licensed under MIT.

All original tools have been preserved and extended with:
- Parametrized typography system (font, size, position, color)
- Animation presets library
- Talking head production preset
- Reels/Shorts workflow preset
- Subtitle style system

## Tools

| Tool | Description |
|------|-------------|
| `capcut_create_draft` | Create a new project with custom dimensions and fps |
| `capcut_add_video` | Add video clip with timing, transitions and speed |
| `capcut_add_audio` | Add audio with volume and fade effects |
| `capcut_add_text` | Add styled text with fonts, colors and animations |
| `capcut_add_subtitle` | Import SRT subtitles with custom styling |
| `capcut_add_effect` | Apply visual effects |
| `capcut_save_draft` | Save project to CapCut drafts folder |
| `capcut_talking_head` | Full talking head preset (one command) |

## Requirements

- Node.js 18+
- Claude Code
- CapCut (Windows or Mac)

## Installation
```bash
git clone https://github.com/TU_USUARIO/capcut-mcp-server-pro
cd capcut-mcp-server-pro
npm install
npm run build
claude mcp add capcut -- node /ruta/dist/index.js
```

## Usage
```bash
claude
> Crea un proyecto talking head con el video en C:/grabacion.mp4, 
  subtítulos en blanco, fuente Montserrat 72px, y guárdalo en CapCut
```

## License

MIT — see [LICENSE](LICENSE)
