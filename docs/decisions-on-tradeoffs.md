# Decision Log

This file records major architectural and product decisions for the Agentic Wealth Copilot.  Each entry should include the date, the decision, the rationale and any trade‑offs considered.  Recording these decisions prevents second‑guessing and provides context for future contributors.

---

## 2026‑01‑23

**Decision:** Use random UUIDs for spending records + post-save duplicate detection instead of hash-based deduplication.

**Approaches Tried & Abandoned:**

1. **Hash-based ID from (date, category, amount, merchant, description)**
   - Problem: AI extracts descriptions inconsistently ("HUG PU 3T-4" vs "HUG PU 3T-4T", "UNK" vs "KIDS SHAKES")
   - Same receipt uploaded twice → different hashes → duplicates saved

2. **Merchant normalization with aliases** (e.g., "Costco Wholesale" → "costco")
   - Problem: Only helped merchant variations, not description variations

3. **Exclude description from hash, use (date, category, amount, merchant)**
   - Problem: Legitimate same-price items on same receipt get deduplicated (3 items at $6.99 → only 1 saved)

4. **Add item_index (position in receipt) to hash**
   - Problem: AI doesn't guarantee consistent item ordering across parses

**Final Approach:** Accept all uploads with random IDs, detect suspected duplicates (same date + amount + merchant) after save, and let user review/delete manually. Trade-off: requires user intervention but avoids data loss.

---

## 2026‑01‑16

**Decision:** Use Streamlit for the web UI and FastAPI for the backend.

**Reason:** Streamlit provides a rapid way to build interactive dashboards directly in Python, which is ideal for prototyping analytics and visualizations without deep front‑end expertise.  FastAPI is lightweight yet powerful for building API endpoints and integrates nicely with Python code and asynchronous I/O.

**Trade‑offs:** Streamlit is less customizable than a full React or Next.js front‑end, and some design limitations may appear as the UI grows.  FastAPI may require additional components (e.g. background task queues) to handle long‑running processes.  However, the reduced complexity and faster iteration cycle outweigh these drawbacks for the current scope.

