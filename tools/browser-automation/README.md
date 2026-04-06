# Browser Automation — AI Agent Usage Guide

This toolkit lets an AI agent control ChatGPT, Gemini, and Claude simultaneously in real browser windows. It uploads files, submits prompts, waits for responses, and reads the full text back — all without using any API keys.

---

## How It Works

Each AI service runs in its own isolated Chrome profile stored on disk. The browser opens visibly (not headless), logs in once, and saves the session. On every subsequent run the session is reused — no login required unless the session expires.

The main script (`test_parallel.py`) launches all three browsers sequentially (to avoid driver conflicts), navigates to each site, verifies login, then runs all three interactions simultaneously using Python threads.

---

## Prerequisites

**Python 3.10+** must be installed. Then install dependencies:

```bash
pip install seleniumbase pyautogui
```

SeleniumBase auto-downloads the correct Chrome driver on first run. No manual driver setup needed.

---

## Chrome Profiles

Three isolated Chrome profiles are used — completely separate from the user's personal Chrome:

| Profile | Path | Service |
|---|---|---|
| Profile 1 | `C:\Users\chris\PROJECTS\chrome-automation-profile` | ChatGPT |
| Profile 2 | `C:\Users\chris\PROJECTS\chrome-automation-profile-2` | Gemini |
| Profile 3 | `C:\Users\chris\PROJECTS\chrome-automation-profile-3` | Claude |

These are created automatically on first run. Sessions (cookies, login state) persist inside each profile directory between runs.

---

## First-Time Login

The first time you run any script against a fresh profile, the browser will open but the user won't be logged in. The script detects this and waits up to **120 seconds** for manual login:

```
→ Log in to ChatGPT in browser 1
→ Log in to Gemini in browser 2
→ Log in to Claude in browser 3
You have 120 seconds...
  ChatGPT=…  Gemini=…  Claude=…  (110s left)
  ChatGPT=✓  Gemini=✓  Claude=✓  (60s left)
```

Once all three show `✓`, the parallel run begins automatically. From that point on, sessions are saved and login is not required again.

**Important:** Never call `driver.quit()` at the end of a run — this destroys the session. The scripts intentionally leave browsers open.

---

## Running the Parallel Script

```bash
cd C:\Users\chris\PROJECTS
python test_parallel.py
```

What it does, in order:

1. Cleans any stale Chrome lock files from all three profiles
2. Launches ChatGPT browser → waits 3s → launches Gemini browser → waits 3s → launches Claude browser
3. Navigates all three to their sites
4. Waits 5 seconds and checks if all three show a ready input box
5. If any are not ready, gives 120 seconds for manual login
6. Once all ready, starts three parallel threads simultaneously:
   - **ChatGPT thread**: selects Thinking model → attaches file → types prompt → submits → polls for stop button → reads response
   - **Gemini thread**: selects Pro model → suppresses OS file dialog → attaches file → types prompt → submits → polls for stop button → reads response
   - **Claude thread**: selects Opus 4.6 → enables Extended Thinking → dismisses overlay → attaches file → types prompt → submits → polls for stop button → reads response
7. Joins all threads and prints all three responses

**Output example:**
```
============================================================
ChatGPT response:
============================================================
Project Name: Natural Browser Controller
Version: 1.0
Features: Navigate to any URL with anti-detection...

============================================================
Gemini response:
============================================================
The project is Natural Browser Controller, Version 1.0...

============================================================
Claude response:
============================================================
Project Name: Natural Browser Controller, Version 1.0...
```

---

## Customising Prompt and File

At the top of `test_parallel.py`, change these two variables:

```python
TEST_FILE = Path(r"C:\Users\chris\PROJECTS\test_upload_file.txt").resolve()
PROMPT = "What is the project name and version described in the uploaded file? List all the features mentioned."
```

Set `TEST_FILE` to any file path. Set `PROMPT` to any question. The same file and prompt are sent to all three services.

If you don't need a file, remove the file attachment block from any thread function. The prompt will still be submitted without an attachment.

---

## Individual Test Scripts

Use these for debugging or testing a single service in isolation:

### `test_chatgpt_upload.py`
Opens ChatGPT, selects the thinking model, attaches a file, submits a prompt, and prints the full response.

```bash
python test_chatgpt_upload.py
```

### `test_gemini_upload.py`
Opens Gemini, attaches a file (suppressing the OS file dialog), submits a prompt, and prints the response.

```bash
python test_gemini_upload.py
```

### `test_claude_upload.py`
Opens Claude, selects Haiku 4.5 with Extended Thinking OFF, attaches a file, submits a prompt, and prints the response. Takes a screenshot at every step saved as `s01_logged_in.png`, `s02_dropdown_open.png`, etc.

```bash
python test_claude_upload.py
```

### `test_claude_model_select.py`
Diagnostic script. Opens Claude, cycles through all available models (Opus, Sonnet, Haiku) and toggles Extended Thinking on and off. Use this to verify model switching works before running the full parallel test.

```bash
python test_claude_model_select.py
```

---

## Model Configuration

### ChatGPT
Selects the thinking/reasoning model by scanning for items whose text contains `think`, `reason`, `o3`, or `o1` in the model dropdown. The dropdown is opened via `button[aria-label="Model selector"]`.

### Gemini
Selects Pro by clicking the model button (which shows `Pro`, `Fast`, or `Thinking`) then clicking the `Pro` option from `[role="option"]` / `[role="menuitem"]` elements. Avoids selecting `Flash` even if its name contains `Pro`.

### Claude
- Model button text shows the active model: `Haiku 4.5`, `Sonnet 4.6`, `Opus 4.6`
- When Extended Thinking is ON, the button shows `Opus 4.6\nExtended`
- Switch models by clicking the button → clicking `[role="menuitem"]` matching the model name
- Toggle Extended Thinking by clicking the `Extended thinking` menu item (it's a toggle switch, not a radio button)
- After closing the dropdown, always press `Escape` and call `focus()` via JS on the textarea before typing — otherwise a lingering overlay intercepts clicks

---

## File Upload Mechanics

### ChatGPT
Clicking the attach (`+`) button reveals a hidden `input[type="file"]`. The script scores all visible buttons near the textarea and clicks the highest-scoring one (aria-label containing `attach` or `upload` scores highest). It then makes the file input visible via JS and calls `send_keys(file_path)` — this bypasses the OS file dialog entirely.

Image-only inputs are filtered out using their `accept` attribute.

### Gemini
Gemini's attach flow triggers an OS file dialog when the file input's `.click()` is called. To prevent this, the script overrides `HTMLInputElement.prototype.click` in the page's JS context to suppress any click on `input[type="file"]`. Then it clicks the `+` button → clicks `Upload files` from the menu → makes the file input visible via JS → calls `send_keys(file_path)`.

### Claude
Claude's file input is already present in the DOM without needing to click an attach button first. The script makes it visible via JS and calls `send_keys(file_path)` directly.

---

## Polling for Response Completion

Each service uses a different stop button selector. The script polls every 2 seconds for up to 5 minutes:

| Service | Stop button selector |
|---|---|
| ChatGPT | `button[aria-label="Stop streaming"], button[data-testid="stop-button"]` |
| Gemini | `button[aria-label="Stop response"]` |
| Claude | `button[aria-label="Stop response"]` |

When the stop button disappears, streaming has finished and the response is safe to read.

---

## Reading Responses

| Service | Primary selector | Fallback |
|---|---|---|
| ChatGPT | `[data-message-author-role='assistant']` — last element | — |
| Gemini | `.model-response-text` — last element | `model-response` |
| Claude | `[data-testid="assistant-message"]` — last element via JS | `.font-claude-message`, then largest div block |

All responses are read in full with no truncation.

---

## Killing Stale Browser Processes

If a script crashes and leaves a Chrome process running against an automation profile, the next run will fail with `session not created: chrome not reachable`. To kill only the automation Chrome processes (leaving the user's personal Chrome untouched):

```powershell
powershell.exe -Command "Get-WmiObject Win32_Process | Where-Object { `$_.Name -eq 'chrome.exe' -and `$_.CommandLine -like '*chrome-automation-profile*' } | ForEach-Object { `$_.Terminate() }"
```

Do **not** use `taskkill /F /IM chrome.exe` — that kills all Chrome instances including the user's personal browser.

---

## Integration with an AI Agent

To use this from an agent (LangChain, CrewAI, AutoGen, or any custom agent), import the results dict and wrap the run in a tool:

```python
import subprocess, json

def query_all_ais(prompt: str, file_path: str = None) -> dict:
    """
    Runs the parallel browser script and returns responses from all three AIs.
    Modify test_parallel.py's PROMPT and TEST_FILE before calling,
    or parameterise them via environment variables.
    """
    result = subprocess.run(
        ["python", r"C:\Users\chris\PROJECTS\browser-automation\test_parallel.py"],
        capture_output=True, text=True, timeout=600
    )
    # Parse responses from stdout
    output = result.stdout
    responses = {}
    for service in ["ChatGPT", "Gemini", "Claude"]:
        marker = f"{service} response:"
        if marker in output:
            start = output.index(marker) + len(marker)
            end = output.find("=" * 60, start + 1)
            responses[service.lower()] = output[start:end].strip() if end != -1 else output[start:].strip()
    return responses
```

For more control, import and call the thread functions directly with pre-configured `Driver` instances.

---

## Known Limitations

- Scripts must run on Windows 11 with a visible desktop (not headless — the browsers need to render)
- All three Chrome profiles must have valid login sessions; if one expires, that thread will fail but the others continue
- Gemini's model names can change; if `Pro` is not found in the dropdown, it falls back to whatever model is already selected
- Claude's Extended Thinking toggle sometimes leaves an overlay div in the DOM after closing; always call `Keys.ESCAPE` and `focus()` before interacting with the textarea
- Thinking models (ChatGPT o3, Claude Opus + Extended Thinking) can take significantly longer to respond; the timeout is set to 5 minutes per thread
