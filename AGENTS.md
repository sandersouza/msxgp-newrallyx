# Project workflow

- Before managing GitHub issues, projects, branches, or PRs, read `/Users/sandersouza/Library/Mobile Documents/com~apple~CloudDocs/obsidian/personal/codex-instructions/github-instructions.md`. Treat that note as the authoritative GitHub workflow; if unavailable, report it instead of silently substituting these summary rules.
- Keep repository documentation, issue bodies, and code in English. Discuss work with the user in their preferred language.
- Before creating any GitHub issue, write its complete body to `.github/issues/<descriptive-slug>.md`.
- Publish issue bodies with `gh issue create --body-file <path>` or an equivalent structured API. Never put long prose in shell commands. Use Markdown files for issue, PR, and comment bodies.
- When the user asks to work on an issue, use the current chat where the request was made. Do not create or fork a separate chat unless explicitly requested. Read the issue URL, scope, acceptance criteria, and relevant decisions before acting. Creating backlog issues alone does not authorize implementation.
- Never commit original ROMs, extracted assets, disassembly, or fixtures containing original game data. Keep them under ignored `references/` directories. Commit tools, documentation, metadata, and synthetic fixtures only.
- Use contributor-supplied ROMs. Tools must not download or redistribute game ROMs.
- Preserve original asset dimensions at 1:1 scale. Target 256x212 by reducing the maze viewport and rearranging the HUD/radar, while preserving world coordinates and game rules.
- Preserve original scenery colors and graphics in active builds. Ask the user before applying any new reduction in graphical quality; earlier exploratory permission does not authorize further reductions. Small, measured timing concessions are acceptable without requiring exact arcade performance.
- Prefer retaining original Z80 game logic and adapting hardware interfaces. Rendering and sound fidelity remain subject to measured feasibility.
- Keep the HUD enabled in new gameplay and performance test builds. Run HUD-off builds or comparisons only when the user explicitly requests them.
- Continue gameplay integration when sprite candidates exceed eight per scanline. Keep real hardware limits enabled and document any resulting culling; defer sprite optimization until it becomes a serious practical blocker. Preserve complete original car drawings.
- Do not push, commit, or implement backlog items unless requested. Keep unrelated user changes intact.
