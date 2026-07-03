# Installing the browser extension

The extension is what tells the tracker which website/tab has focus. Do this once for each browser you want tracked (Chrome, Brave, and/or Edge).

## 1. Build the extension

From the project root:

```
python extension/build_extension.py
```

This creates `extension/build/chrome/`, `extension/build/brave/`, and `extension/build/edge/` — one ready-to-load folder per browser. Re-run this any time you change `extension/src/background.js` or `extension/src/manifest.json`.

## 2. Load it into your browser

Pick the folder that matches the browser you're loading into (`chrome`, `brave`, or `edge` — don't mix them up, each one is stamped for that specific browser).

1. Open the extensions page:
   - Chrome: `chrome://extensions`
   - Brave: `brave://extensions`
   - Edge: `edge://extensions`
2. Turn on **Developer mode** (toggle, usually top-right).
3. Click **Load unpacked**.
4. Select the matching folder, e.g. `extension/build/brave/`.
5. Confirm the extension card shows up and is enabled.

Repeat steps 1-4 in every other browser you want tracked, picking that browser's own folder.

## 3. Allow file:// URLs (optional, browser-dependent)

The extension asks for permission to read local file (`file://`) tabs, e.g. PDFs or HTML files opened directly in the browser, so those get tracked too instead of showing up as blank.

- click extensions, go to "manage extension" for this extension
- Some browsers show a separate "Allow access to file URLs" toggle on the extension's card in the extensions page.
- **This toggle wasn't present/needed in Brave** — file tabs tracked fine without it. Whether you see this option (and need to enable it) seems to vary by browser/version, so just check your extension's card after loading it: if you see the toggle, turn it on; if you don't, you likely don't need to do anything.

## 4. allow private window monitoring
- Same location as when you allowed file:// URLs. Click extensions, go to "manage extension" for this extension
- Turn on "Allow in Private" or whatever it's called in your browser

## 5. Verify it's working

1. Start the tracker: `python Computer_Tracker.py`
2. Switch to the browser you just loaded the extension into and browse a couple of sites.
3. Open `data/daily-<today's date>.csv` and confirm rows are appearing with the site's URL in the third column.

If you never see a URL show up and instead hear a repeated beep after ~30 seconds, the extension isn't posting — double check it's enabled on the extensions page and that you loaded the correct per-browser folder.

## Notes

- This is an unpacked, unsigned extension (no Chrome Web Store listing), so your browser will show a "disable developer mode extensions" nag banner on restart. This is expected and not a bug.