# Demo video script (target 2:50, public on YouTube)

Record each section separately, then join. Use real runs only. If a run is slow, speed it up and show
"sped up" on screen.

| Time | On screen | Say |
|---|---|---|
| 0:00–0:20 | Title card, then a headline about personal agents | "Personal AI agents now act as you, with your real accounts. One audit found 341 malicious skills among 2,857 in a popular agent's plug-in store. Would you hand your logins over?" |
| 0:20–0:50 | Missions screen. Click the morning brief, then See what this job needs. The card appears with its moving border. | "Warrant asks NVIDIA Nemotron, on Nebius Token Factory, what this mission needs. It can only choose from reviewed capabilities. Code checks the draft. I read it in plain words and approve." |
| 0:50–1:05 | Open "Show the rules OpenShell enforces" | "This is the actual NVIDIA OpenShell policy generated from the warrant: only these pages, only GET." |
| 1:05–1:45 | Run the agent. Run screen: sandbox name in the header, steps ticking, allowed requests, result appears | "Each run gets a fresh OpenShell sandbox. The agent reads the portal from inside it. Nemotron writes my brief, then the sandbox is deleted." |
| 1:45–2:20 | Mission "Brief me on this week's announcements and tell me my latest grades", with a warrant for announcements only. Yellow BLOCKED event for /grades with OpenShell's reason | "This mission asks for more than I approved. The agent tries to open my grades; OpenShell blocks it because grades are not in the warrant, and tells us why. The mission still finishes with what it was allowed to read." |
| 2:20–2:40 | Evidence screen and the verification document | "We report only measured results. Across 10 runs with broad access, all 24 off-warrant requests went through. Under the warrant, with OpenShell enforcing, 0 of 17 did." |
| 2:40–2:50 | Repo and demo URL | "Open source, built on NVIDIA Nemotron through Nebius Token Factory and NVIDIA OpenShell. Try the public demo at warrant-demo.onrender.com." |

Must be visible: the words Nemotron and Token Factory, OpenShell blocking a request, the demo URL, the repo.
Never show: the API key, the owner token, the `.env` file.
