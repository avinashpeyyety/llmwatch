# GitHub Pages landing site

**Live URL:** [https://avinashpeyyety.github.io/llmwatch/](https://avinashpeyyety.github.io/llmwatch/)

## Fix 404 ("There isn't a GitHub Pages site here")

The site files are in `docs/` on `main`. GitHub just needs Pages turned on once.

### Option A — simplest (recommended)

1. Open **[Settings → Pages](https://github.com/avinashpeyyety/llmwatch/settings/pages)**
2. Under **Build and deployment → Source**, choose **Deploy from a branch**
3. **Branch:** `main` · **Folder:** `/docs`
4. Click **Save**

Wait ~1 minute, then reload [https://avinashpeyyety.github.io/llmwatch/](https://avinashpeyyety.github.io/llmwatch/)

### Option B — GitHub Actions deploy

1. Open **[Settings → Pages](https://github.com/avinashpeyyety/llmwatch/settings/pages)**
2. Under **Source**, choose **GitHub Actions**
3. Push to `main` (or run the **Deploy GitHub Pages** workflow manually under Actions)

## Update the terminal screenshot

```bash
./scripts/capture-preview.py
git add docs/preview*.html docs/preview.txt
git commit -m "Update landing page preview"
git push
```