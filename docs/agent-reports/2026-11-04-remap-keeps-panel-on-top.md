# 2026-11-04 — panel "vanished" after the frozen-redraw watchdog fired

## 1. Context
- Follows `2026-11-04-frozen-panel-redraw.md` (PR #4, merged as 9367c2d).
  Minutes after the merge the user wrote "teď mi komponent tracker zmizel
  úplně".
- Branch `fix/remap-keeps-panel-on-top` from `origin/main` (9367c2d), one PR.

## 2. What happened
- Service active, window mapped (`IsViewable`), but `_NET_WM_STATE` had lost
  `_NET_WM_STATE_ABOVE` (only SKIP_PAGER, SKIP_TASKBAR, DEMANDS_ATTENTION).
  Journal: `22:50:30 pc-monitor: no repaint for 63 s, remapping the window`.
  The panel was simply behind other windows.
- Reproduced on a test panel: `_NET_WM_STATE` before a forced remap had ABOVE,
  after it not. GTK keeps its "above" wish in sync with the WM's state; the WM
  clears the state on withdraw, so `show()` maps without it.
- "63 s" with a once-per-second check means the check had not run (or the
  window was not mapped/was iconified) for ~50 s; the first check afterwards
  compared against an old paint time before GTK could paint → false freeze.
  Cause of the 50 s gap not found (no logind/suspend/lock lines, no
  gnome-shell frame message this time).

## 3. Decisions made by the agent
- `set_keep_above(True)` after `show()` in `check_redraw`.
- Freeze = `FROZEN_REFRESHES` (10) refreshes in a row where the mark got no
  paint since the previous refresh; not mapped / iconified resets the count.
  A blocked main loop is one late tick, then GTK paints → no remap.
  If wrong: a real freeze still gets caught (10 ticks ≈ 10 s); the risk is a
  case where GTK paints the window but not the mark — unlikely, the mark is
  queued every refresh.
- Panel restarted with `pixi run resurrect` (position resets to top-right of
  the primary monitor; position is not persisted by design).

## 4. Open
- What blocked the check for ~50 s at 22:49 is unknown. If
  `remapping` shows up again, look at what the machine did right before.
- Screen locked/off behaviour still untested.

## 5. Run and test
- `pixi run smoke-test` — 28 tests; watchdog tests use a real panel with
  hide/move/show/set_keep_above recorded.
- Live: `xprop -id <xid> _NET_WM_STATE` must list `_NET_WM_STATE_ABOVE`;
  `journalctl --user -u pc-monitor | grep remapping`.

## 6. Prompt for the next agent
> Read `CLAUDE.md`, `docs/KNOWLEDGE.md` and both 2026-11-04 reports in
> `docs/agent-reports/` of `~/Desktop/cashups/maybe_prace/components_tracker`.
> Check `journalctl --user -u pc-monitor | grep remapping` and the PC monitor
> window's `_NET_WM_STATE`. Report each remap: was it a real freeze (gnome-shell
> "no frame drawn time" nearby) or a false alarm, and is the panel on top.
