# GitHub Pages landing site

**Live URL:** [https://avinashpeyyety.github.io/llmwatch/](https://avinashpeyyety.github.io/llmwatch/)

---

## Fix 404 — enable Pages (one time)

The 404 *"There isn't a GitHub Pages site here"* means Pages is **not enabled** in repo settings. The site files are ready on the `gh-pages` branch (same setup as [ollama-chat-app](https://avinashpeyyety.github.io/ollama-chat-app/)).

### Steps

1. Open **[Settings → Pages](https://github.com/avinashpeyyety/llmwatch/settings/pages)**
2. Under **Build and deployment → Source**, select **Deploy from a branch**
3. **Branch:** `gh-pages` · **Folder:** `/ (root)`
4. Click **Save**
5. Wait 1–2 minutes, then refresh the live URL

You should see: *"Your site is live at https://avinashpeyyety.github.io/llmwatch/"*

---

## How updates work

- **Automatic:** pushing to `main` runs `.github/workflows/pages.yml`, which updates the `gh-pages` branch from `docs/`
- **Manual edit:** change `docs/index.html` or `docs/styles.css` on `main`

---

## Update the terminal screenshot

```bash
./scripts/capture-preview.py
git add docs/preview*.html docs/preview.txt
git commit -m "Update landing page preview"
git push
```