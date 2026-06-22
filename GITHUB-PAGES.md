# GitHub Pages landing site

**Live URL:** [https://avinashpeyyety.github.io/llmwatch/](https://avinashpeyyety.github.io/llmwatch/)

## Enable Pages (one-time)

1. Open [github.com/avinashpeyyety/llmwatch/settings/pages](https://github.com/avinashpeyyety/llmwatch/settings/pages)
2. **Source:** Deploy from a branch
3. **Branch:** `gh-pages` · **Folder:** `/ (root)`
4. Save

After the first workflow run, the site should be live within a minute.

## Update the terminal screenshot

Regenerate the preview from a live dashboard capture:

```bash
./scripts/capture-preview.py
git add docs/preview*.html docs/preview.txt
git commit -m "Update landing page preview"
git push
```

Pushes to `main` that touch `docs/` also run `.github/workflows/pages.yml` automatically.