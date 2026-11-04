# PC monitor — knowledge and decisions

Living state of what we know. Session history lives in `docs/agent-reports/`;
older notes per feature are in `CLAUDE.md`.

## 1. Verified facts

- **The panel window can freeze while its state stays correct.** 2026-11-04:
  the panel showed `internet offline` although the PC was online. Read through
  AT-SPI, the internet label said `↓98 ↑60 · 4 ms`; two X captures of the
  window (`Gdk.pixbuf_get_from_window`) 7 min apart were pixel-identical.
  The frame was from 2026-11-03 ~20:36.
- **Cause is the compositor's frame sync.** Journal, 2026-11-03 20:35:43:
  `gnome-shell: 0x600003 (PC monitor): Frame has assigned frame counter but no frame drawn time`
  (`0x600003` = the panel's X window). Around that time: Wi-Fi reconnect
  (`CONNECTED_SITE`, then a new activation at 20:36:52) and logind
  suspend/hibernate attempts. The same message hit VLC on 2026-10-31.
- **Unmap + map unfreezes it.** Done from outside (GdkX11 foreign window
  `hide()`/`show()`), the frozen panel painted the current values at once.
- **In-process remap keeps the position** and the window paints again within
  1 s (test panel, forced `check_redraw`, 2026-11-04).
- **Remapping drops `_NET_WM_STATE_ABOVE`** (xprop before/after on a test
  panel, 2026-11-04): without `set_keep_above(True)` after `show()` the panel
  sinks behind other windows — the user saw it "vanish" after the first
  watchdog version fired.
- **A healthy panel does not trip the watchdog:** after the restart, 12 X
  captures over 60 s were all different and nothing was logged.
- The internet probe and speed test themselves were fine during the
  incident: probe ~3–20 ms, manual speed test 46/64 Mb/s, no
  `speed test failed` line in the panel's journal since 2026-11-03 13:07.
- Diagnostics that work here without ptrace (`ptrace_scope=1` blocks strace/gdb):
  AT-SPI (`gi.repository.Atspi`, system python) for the labels and tooltips;
  X capture with `GDK_BACKEND=x11` for what is actually on screen.

## 2. Refuted hypotheses and dead ends

- "The internet check is wrong" — refuted: the in-process state was online;
  only the picture was stale.
- "`stalled` stuck true" — refuted by the AT-SPI tooltip (last test 22:16,
  normal green row).
- A watchdog by seconds since the last paint — refuted 2026-11-04: it fired
  `no repaint for 63 s` on a panel that was not frozen (the check itself had
  not run for ~50 s, or the window was not shown; cause of the gap unknown),
  right before GTK could paint. Now counted in refreshes without a paint.
- A screenshot via X capture is not proof of what the panel *thinks*: it
  showed `offline` for the whole frozen period. Read AT-SPI as well.

## 3. Decisions

- **2026-11-04, agent: watchdog that remaps a frozen window** (`check_redraw`
  in `widget.py`, `FROZEN_REFRESHES = 10`), corrected the same evening (v1
  counted seconds and lost keep-above; see §2 and §1). Alternatives: run on
  native Wayland (loses `move()`, the panel could not anchor or be dragged),
  restart the process on a freeze (loses a dragged position and the current
  speed result), disable frame sync (no public GTK3 switch). Consequence: a
  frozen panel shows a stale frame for ~10 refreshes; while it stays frozen
  it hides/shows every 10 refreshes, one log line per freeze. Wrong if: the
  journal shows `remapping` while the panel was visibly fine, the panel ends
  up below other windows or off its spot after a remap, or it stays frozen
  after the remap (then fall back to re-exec of the process).

## 4. Open questions and next step

- Does the remap fire while the screen is locked/off? Check
  `journalctl --user -u pc-monitor | grep remapping` after a night.
- The next real freeze will show whether the in-process remap clears it (look
  for the log line followed by a live panel).
