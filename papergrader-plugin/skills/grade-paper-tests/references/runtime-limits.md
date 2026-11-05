# Where PaperGrader can run

Grading needs two abilities in the same session: **seeing images** and **running
Python with PyMuPDF**. `pg doctor` tests the second, and `pg vision-check` the first.
Trust those results over this table.

| Surface | Status | Notes |
|---|---|---|
| Teacher's own PC, command line | **Tested** (Windows 10, Python 3.14) | PDF pipeline only. A person enters the judgments. |
| Codex CLI with local plugin | Manifest parse attempted; see README | Grading itself has not been run here. |
| ChatGPT desktop app, Work mode | **Untested** | OpenAI documents local plugin install through this app. |
| ChatGPT web or mobile | **Untested, may not run scripts** | OpenAI documents plugin skills there, but not whether bundled scripts execute. |

## If this surface can't run the scripts

Tell the teacher plainly, then offer the first option that applies:

1. **Attach the runtime bundle.** If a Python tool exists here but the plugin's files
   aren't reachable, the teacher can attach `papergrader-runtime.zip`. Unzip it, then
   run `python -m papergrader doctor` from that folder. This works only if the sandbox
   already has PyMuPDF, and `doctor` will say whether it does.
2. **Use the ChatGPT desktop app or Codex** with the local plugin.
3. **Grade here and build there.** Record judgments in `grading.json` in this
   conversation for the teacher to save and build on their own PC. Say clearly that
   no PDF has been made yet.

Never simulate a command, invent output, or describe files that don't exist.

## MCP fallback (not built)

If no surface can do both jobs, the smallest option would be a local stdio MCP server
wrapping this CLI, listed in `mcp.json`. It would serve the desktop app and Codex at no
cost, but not ChatGPT web, which can't reach a local process. Reaching web would need a
hosted or tunnelled server, sending student data through it: a privacy decision and
possibly a recurring cost. It needs the teacher's explicit approval first.
