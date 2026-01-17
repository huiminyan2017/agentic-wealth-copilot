# Decision Log

This file records major architectural and product decisions for the Agentic Wealth Copilot.  Each entry should include the date, the decision, the rationale and any trade‑offs considered.  Recording these decisions prevents second‑guessing and provides context for future contributors.

---

## 2026‑01‑16

**Decision:** Use Streamlit for the web UI and FastAPI for the backend.

**Reason:** Streamlit provides a rapid way to build interactive dashboards directly in Python, which is ideal for prototyping analytics and visualizations without deep front‑end expertise.  FastAPI is lightweight yet powerful for building API endpoints and integrates nicely with Python code and asynchronous I/O.

**Trade‑offs:** Streamlit is less customizable than a full React or Next.js front‑end, and some design limitations may appear as the UI grows.  FastAPI may require additional components (e.g. background task queues) to handle long‑running processes.  However, the reduced complexity and faster iteration cycle outweigh these drawbacks for the current scope.

---

Add new decisions below this line using the same format.