# Changelog

## 2.6.5 - 2026-03-20

- Fixed `start.bat` browser startup flow so a dedicated Chrome profile directory can be launched and detected reliably.
- Forced UTF-8 Python output in `start.bat` to avoid `patch_drissionpage.py` encoding failures under different launch modes.
- Normalized `start.bat` to consistent `CRLF` line endings to prevent `cmd` parse errors caused by mixed newlines.
- Verified end-to-end startup with `BROWSER_PROFILE_DIR=C:\Users\QIU\AppData\Local\UniversalWebApiProfile`, including Chrome DevTools on `9222` and service health on `8199`.
