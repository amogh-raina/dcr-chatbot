# DCR FAQ chatbot

A chatbot for exploring SU disability supplement FAQs. DCR supplies the answers and controls the flow; OpenAI matches typed questions to modeled FAQ content.

## Answer-first experiment

This branch, `experiment/faq-answer-matching`, adds matching against both questions and answers. Import **`xml graphs/SU_handicaptillaeg_FAQ_AnswerMatching.xml`** into DCR as a new graph, then use `http://localhost:8080/?graphid=YOUR_NEW_GRAPH_ID`. Restart the Python app after switching branches. The existing graph ID does not activate this experiment.

Strong matches display the verbatim answer immediately, followed by Yes/No. No opens that topic's full question list; Yes says “Feel free to ask me anything else.” Uncertain matches still offer clarification. See [ANSWER_MATCHING.md](ANSWER_MATCHING.md) for the brief implementation map.

## Run it on your computer

1. Install **Python 3.12** (on Windows, tick **Add Python to PATH**). Download this repository using **Code → Download ZIP**, unzip it, and open a terminal in the extracted folder.
2. Create an environment and install the dependencies:

   **macOS / Linux**
   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

   **Windows — Command Prompt**
   ```bat
   py -3.12 -m venv .venv
   .venv\Scripts\activate.bat
   python -m pip install -r requirements.txt
   ```
3. Make a copy of `.env.faq.example` named **`.env`**. Ask the maintainer privately for the DCR credentials (`API_KEY`, `TOKEN`) and an OpenAI key (`OPENAI_API_KEY`). Keep the repository URL and FAQ settings from the example. Your DCR account must have access to graph **2012636**, or the maintainer must supply another graph ID. Never upload your filled-in `.env` to GitHub.
4. Run `python app.py`. Leave the terminal open and visit **http://localhost:8080/?graphid=2012636** in your browser.

Next time, activate the environment using the command above and run `python app.py`. Stop with **Ctrl+C**. After code updates, reinstall `requirements.txt` and restart. Internet access is required. If authentication fails, ask the maintainer to check your keys and graph access. `INFO:openchat:` lines in the terminal show matching diagnostics.

## The second UI

The included demo build is at **http://localhost:8080/demo** while the same server runs. No extra installation is needed to view it. This is an unfinished showcase: it still targets an older graph and has not been adapted to the current FAQ interaction contract. Use the main UI for testing.

Only developers changing the demo need **Node.js 22.12 or newer**. From `demo-ui`, run `npm ci`, then `npm run build`; refresh `/demo`. Its React/Vite dependencies are in `demo-ui/package.json` and `package-lock.json`, not Python's `requirements.txt`.

## Where things are

- `app.py`: server and browser-session endpoints.
- `faq_runtime.py`: FAQ confirmation and presentation using live DCR state.
- `openchat.py`: OpenAI question/answer ranking; never generates FAQ answers.
- `dcr_repository.py`: DCR API calls; `chatnlp.py`: legacy non-FAQ interpretation.
- `templates/` and `static/script.js`: main UI; `demo-ui/`: showcase source; `static/demo/`: built showcase.
- `xml graphs/SU_handicaptillaeg_FAQ_MVP.xml`: current graph source. Runtime uses DCR's API, not this file.
- `external_scripts/graph_parser.py`: optional review-cache helper; uses only Python’s standard library. Other legacy scripts are excluded.
- `tests/`: developer checks (`python -m unittest discover -s tests`).

See [Overview.md](Overview.md) for architecture and the API contract. Local traces, caches, review notes, `.env`, and unused legacy scripts are deliberately excluded. The graph parser is included, but is not used for FAQ matching or routing.
