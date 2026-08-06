# Round 2 targeted product evidence

> Reviewed commit: `ebaec0d71b9c5322b6042a5724b8015777ceb5e9`
>
> Fix delta: `ac47fca08148ccc245eca956d253096b9394f8dd..ebaec0d71b9c5322b6042a5724b8015777ceb5e9`
>
> Date: 2026-08-06

## Environment

- Isolated IM/Gateway from the unit worktree; dedicated `nano` test user and `e2e` Agent.
- Current Vite client at `1280×800`; frontend production build completed before the journey.
- Source conversation: `75597ae5aa2d4dff9eecb757dddedf56`.
- Fork conversation: `fc7a573134674d7ab2c89c416a67ba7c`.

## Targeted journey

The source conversation displayed this order:

1. user `Reply only: R2-ONE.`
2. Agent `R2-ONE.`
3. `· Background self-evolution: skills updated`
4. user `Reply only: R2-TWO.`
5. Agent `R2-TWO.`
6. `· Background self-evolution: memory updated`
7. user `Reply only: R2-THREE.`
8. Agent `R2-THREE.` — fork point
9. `· Background self-evolution: memory updated` — after the fork point, so it must not be copied

The new branch immediately displayed items 1–8 in exactly the same order and excluded item 9. The same eight-item order remained after a full browser reload and after switching to the source conversation and reopening the branch.

After switching the existing branch to Chinese, items 3 and 6 rendered as `· 后台自进化：技能已更新` and `· 后台自进化：记忆已更新` in the same positions. A further reload preserved both Chinese renderings and their order. This is the user-observable evidence that the copied notices retained their structured update-target semantics instead of becoming fixed fallback text.

## Screenshots

| Evidence | State | Observable conclusion |
|---|---|---|
| `source-en-before-fork-top.png` | source, English, top of timeline | Items 1–7 keep the expected user/Agent/notice interleave. |
| `source-en-before-fork.png` | source, English, lower timeline | Agent item 8 and post-fork notice item 9 follow the upper sequence. |
| `fork-en-immediate.png` | branch immediately after creation | Items 1–8 retain source order; item 9 is absent. |
| `fork-en-after-reload.png` | branch after full reload | The same order persists. |
| `fork-en-after-reentry.png` | source opened, then branch reopened | The same order persists after conversation re-entry. |
| `fork-zh-after-reentry.png` | existing branch switched to Chinese | Notice targets re-render in Chinese without moving. |
| `fork-zh-after-reload.png` | Chinese branch after full reload | Chinese semantics and the repaired order both persist. |

All screenshots are `1280×800` and were captured from the real Web IM product entry.
