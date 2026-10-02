# Real screenshots and reproduction

![Executed synthetic dashboard](dashboard.png)

This is a screenshot of the actual generated HTML, not a design mockup. It shows a deterministic run, four synthetic documents, four checks, and synthetic human decisions. The original demo includes accepted C1, revised C2, rejected C3 and pending C4.

To reproduce:
1. Run the README quick start and its three decision commands.
2. Open the generated `dashboard.html`; refresh after each decision.
3. Capture the overview with the SYNTHETIC and deterministic-mode labels visible.
4. Expand a retention evidence row to inspect its exact source, JSON path/CSV record, chunk ID and hash.
5. Scroll to the audit trail and capture the three decisions and their rationales.

The included HTML/JSON exports in `examples/` preserve the executed demonstration. Re-running produces new event timestamps. Exact evidence IDs remain stable for unchanged inputs.
