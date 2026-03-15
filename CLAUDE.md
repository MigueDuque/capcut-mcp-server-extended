# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Build (compile TypeScript and make dist/index.js executable)
npm run build

# Development (watch mode, recompiles on change)
npm run dev

# Run the compiled server
npm start
```

There are no test scripts configured. The server starts and communicates over stdio (default) or HTTP.

## Architecture

This is a **Model Context Protocol (MCP) server** that bridges AI assistants with CapCut Pro video editing via a VectCutAPI backend.

**Transport modes** (set via `TRANSPORT` env var):
- `stdio` (default) — for Claude Desktop / local MCP clients
- `http` — listens on `PORT` (default 3000)

**Key env vars**: `CAPCUT_API_URL` (default `http://localhost:9001`), `PORT`, `TRANSPORT`

### Data flow

```
MCP Client → tools/index.ts (tool registration + Zod validation)
           → services/api-client.ts (axios, 60s timeout)
           → VectCutAPI backend (http://localhost:9001)
```

### Source layout

| File | Role |
|------|------|
| `src/index.ts` | Entry point; stdio/HTTP transport setup |
| `src/tools/index.ts` | All 11 MCP tool definitions and `formatResponse`/`handleError` helpers |
| `src/schemas/index.ts` | Zod schemas for every tool input |
| `src/services/api-client.ts` | Singleton `apiClient`; maps tool calls to POST endpoints |
| `src/types.ts` | TypeScript interfaces (`DraftConfig`, `VideoTrack`, `ResponseFormat`, etc.) |
| `src/constants.ts` | `API_BASE_URL`, default resolution/fps, supported formats, effects, transitions |

### 11 MCP tools

`capcut_create_draft` → `capcut_add_video` / `capcut_add_audio` / `capcut_add_text` / `capcut_add_image` / `capcut_add_subtitle` / `capcut_add_keyframe` / `capcut_add_effect` / `capcut_add_sticker` → `capcut_save_draft`

`capcut_get_duration` — read-only, queries media metadata.

All tools accept a `response_format` parameter (`markdown` | `json`). Markdown uses `formatResponse()` for human-readable output; JSON returns `structuredContent`.

### Adding a new tool

1. Add types to `src/types.ts` if needed.
2. Add a Zod schema to `src/schemas/index.ts`.
3. Add the API method to `src/services/api-client.ts`.
4. Register the tool inside `registerTools()` in `src/tools/index.ts`.
5. Run `npm run build`.