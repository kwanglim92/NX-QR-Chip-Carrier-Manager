# Auto Update Runbook

MC QR Code Chip Carrier Manager uses an installer-based auto-update flow.
Clients read `manifest.json` from `http://10.4.1.141:8006`, download a newer
`McQrManager-Setup-<version>.exe`, verify SHA-256, launch the Inno Setup
installer silently, then exit so Restart Manager can update and relaunch the app.

## Server

Start the static update server on the server PC:

```powershell
docker compose -f docker-compose.updates.yml up -d
```

The host folder `updates_publish/` is served at:

```text
http://10.4.1.141:8006/
```

## Release Steps

1. Update `VERSION`.
2. Run `build.bat`.
3. Build the installer:

```powershell
iscc installer.iss
```

4. Copy `Output/McQrManager-Setup-<version>.exe` to `updates_publish/`.
5. Calculate SHA-256:

```powershell
Get-FileHash .\updates_publish\McQrManager-Setup-<version>.exe -Algorithm SHA256
```

6. Write `updates_publish/manifest.json`:

```json
{
  "latest_version": "2.3.0",
  "min_required_version": "2.2.0",
  "download_url": "http://10.4.1.141:8006/McQrManager-Setup-2.3.0.exe",
  "sha256": "<lowercase sha256>",
  "release_notes": "- 변경 요약",
  "released_at": "2026-06-08T09:00:00+09:00"
}
```

7. Validate the server response:

```powershell
curl http://10.4.1.141:8006/manifest.json
curl -I http://10.4.1.141:8006/McQrManager-Setup-<version>.exe
```

## Notes

- The updater only runs in frozen PyInstaller builds.
- `MCQR_UPDATE_ENABLED=0` disables update checks.
- `MCQR_UPDATE_SERVER` overrides the default server URL.
- `MCQR_UPDATE_ELEVATE=1` launches the installer with UAC elevation. The current
  installer uses `PrivilegesRequired=lowest`, so elevation is off by default.
- HTTP plus SHA-256 checks integrity only. HTTPS and code signing should be added
  later if the update network is not fully trusted.
