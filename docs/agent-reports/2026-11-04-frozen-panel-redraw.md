# 2026-11-04 — panel showed "offline" while online (frozen redraw)

## 1. Context
- User: "component tracker se mi asi nějak kouše… ukazuje že internet je
  offline. to se nesmí stávat." Machine: Linux laptop (24 threads, RTX 5060
  Laptop GPU, eduroam Wi-Fi), panel as user service `pc-monitor`, running
  since 2026-11-03 13:07.
- Branch `fix/frozen-panel-redraw` from `origin/main` (5f86f75); one PR into
  `main`, nothing else to merge first. The user merges.

## 2. What happened
- Internet was fine: TCP to 1.1.1.1/8.8.8.8:443 OK, manual `speed_test()`
  46/64 Mb/s, probe connections from the panel visible in `ss` (TIME-WAIT).
- strace/gdb on the panel: `ptrace: Operation not permitted` (yama
  ptrace_scope=1). Dead end; used AT-SPI instead.
- AT-SPI showed the internet label `↓98 ↑60 · 4 ms`, tooltip "measured
  22:16" — the panel's state was online.
- X capture of the window at 22:30 and 22:38: pixel-identical (`offline`,
  `758.2 GB free`, while `df` said 747 G). The window had stopped painting.
- Journal: `2026-11-03 20:35:43 gnome-shell: 0x600003 (PC monitor): Frame has
  assigned frame counter but no frame drawn time` — mutter never sent
  `_NET_WM_FRAME_DRAWN`, GTK3 waits for it before every next frame. Wi-Fi was
  reconnecting at that moment, hence the frozen frame says `offline`.
- Unmap/map from outside (GdkX11 foreign window) unfroze it instantly.
- First attempt at a live check failed for a test reason: lowering
  `mark.drawn_at` was undone by an ordinary repaint before the next refresh;
  calling `check_redraw(time.monotonic() + 60)` directly works.

## 3. Decisions made by the agent
- Watchdog in `widget.py`: `LoadMark.on_draw` stamps `drawn_at`;
  `refresh` → `check_redraw` remaps (hide, move back, show) after
  `FROZEN_SECONDS` = 10 s without a paint, retrying no faster than every 10 s,
  logging once per freeze. If wrong: false remaps (flicker, log lines) or
  a freeze it cannot clear. Alternatives rejected in `docs/KNOWLEDGE.md` §3.
- Running panel restarted with `pixi run resurrect` to load the fix.

## 4. Open
- Behaviour while the screen is locked/off is untested.
- The in-process remap has not met a real mutter freeze yet (the external
  remap did). If a future freeze persists after the log line, re-exec the
  process instead.
- Windows: code path is the same, untested there (no XWayland frame sync on
  Windows, so it should simply never fire).

## 5. Run and test
- `pixi run smoke-test` — 26 tests, includes the watchdog unit tests and a
  remap test with hide/move/show stubbed.
- `pixi run resurrect` — reload the running panel.
- Live check: `journalctl --user -u pc-monitor | grep remapping`.
- On-screen check: X capture with `GDK_BACKEND=x11` and
  `GdkX11.X11Window.foreign_new_for_display(display, <xid>)`; xid from
  `xwininfo -root -tree | grep "PC monitor"`. State check: AT-SPI
  (`gi.repository.Atspi`) on the process.
- Do not `hide()` the user's panel from outside without need — it is the
  recovery itself, fine, but it does flash the window.

## 6. Prompt for the next agent
> Read `CLAUDE.md`, `docs/KNOWLEDGE.md` and
> `docs/agent-reports/2026-11-04-frozen-panel-redraw.md` in
> `~/Desktop/cashups/maybe_prace/components_tracker`. Check
> `journalctl --user -u pc-monitor | grep -E "remapping|speed test failed"`
> and whether `gnome-shell` logged `Frame has assigned frame counter but no
> frame drawn time` for "PC monitor" since. Tell me whether the frozen-redraw
> watchdog fired, whether the panel recovered each time, and whether any
> remap happened while the screen was locked.
