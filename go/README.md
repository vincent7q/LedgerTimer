# LedgerTimer (Go / Walk)

A small native-Windows time tracker. Native Win32 controls via
[lxn/walk](https://github.com/lxn/walk), pure-Go SQLite via
[modernc.org/sqlite](https://modernc.org/sqlite). **No cgo / C compiler
required** — it builds with the standard Go toolchain.

## Layout

- `db.go` — SQLite data layer (schema-compatible with the Python version).
- `export.go` — CSV export.
- `ui.go` — Walk UI: timer main window plus History, Edit, and Export dialogs.
- `main.go` — entry point.
- `LedgerTimer.manifest` / `rsrc.syso` — application manifest (Common Controls
  6.0 + DPI awareness). `rsrc.syso` is auto-linked by `go build`; regenerate it
  only if the manifest changes (see below).

## Build

```powershell
go build -ldflags="-H windowsgui" -o LedgerTimer.exe .
```

`-H windowsgui` suppresses the console window. The result is a single ~14 MB
exe. `ledger.db` is created next to it on first run.

## Run / test

```powershell
go run .          # run from source
go test ./...     # data-layer and export tests
```

## Regenerating the manifest resource (only if LedgerTimer.manifest changes)

```powershell
go run github.com/akavel/rsrc@latest -manifest LedgerTimer.manifest -arch amd64 -o rsrc.syso
```
