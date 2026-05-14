# Documentation Workflow

## Operating Model

The user guide is managed in three layers:

1. **HTML source**: `docs/user-guide.html`
2. **Field PDF**: `docs/MC_QR_Manager_User_Guide_v2.1.0.pdf`
3. **Training deck**: `docs/training/MC_QR_Manager_User_Training_v2.1.0.pptx`

Keep `user-guide.html` as the single source of truth. The PDF and PPT are generated/distribution artifacts.

## Screenshot Assets

Screenshots live in:

```text
docs/assets/user-guide/
```

Use relative paths from `user-guide.html`, for example:

```html
<img src="assets/user-guide/fig-07-01-manual-capture-menu.png" alt="Manual Capture menu">
```

When sharing HTML for review, share the whole `docs/` folder or a ZIP of it. If only the HTML file is moved, image paths will break.

For field distribution, use the PDF because images are embedded in the PDF file.

## Update Workflow

1. Update `docs/user-guide.html`.
2. Add or replace PNG screenshots in `docs/assets/user-guide/`.
3. Open `docs/user-guide.html` in a browser and check all screenshot references.
4. Export `docs/MC_QR_Manager_User_Guide_v2.1.0.pdf`.
5. Update the training deck only when the operator workflow changes.
6. Run `git diff --check`.
7. Commit and push.

## PDF Generation

Recommended command when Microsoft Edge is installed:

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --headless `
  --disable-gpu `
  --print-to-pdf="$PWD\docs\MC_QR_Manager_User_Guide_v2.1.0.pdf" `
  "$((Resolve-Path docs\user-guide.html).Path)"
```

If the command does not preserve the desired print style, open `docs/user-guide.html` in Edge/Chrome and use **Print → Save as PDF**.

## Distribution Rule

- Operators receive the PDF.
- The HTML and screenshot folder stay in Git as source assets.
- The PowerPoint deck is for onboarding or refresher training only.
