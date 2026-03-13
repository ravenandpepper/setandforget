# Deploy

## Current setup
- Local development repo: `/Users/jeroenderaaf/Sites/setandforget`
- VPS bare repo: `/home/traderops/repos/setandforget.git`
- VPS deployed worktree: `/home/traderops/setandforget`

The VPS deploys automatically through the bare repo `post-receive` hook.

## Standard workflow
1. Make changes locally in `/Users/jeroenderaaf/Sites/setandforget`
2. Run the smallest relevant local validation
3. Commit the change
4. Push `main` to `origin`

Example:

```bash
cd /Users/jeroenderaaf/Sites/setandforget
git status
git add .
git commit -m "Describe the change"
git push origin main
```

## What push does
- Push updates `/home/traderops/repos/setandforget.git`
- The VPS hook checks out `main` into `/home/traderops/setandforget`

## Useful checks
Check local status:

```bash
cd /Users/jeroenderaaf/Sites/setandforget
git status
```

Check deployed files on VPS:

```bash
ssh traderops@38.242.214.188 'cd /home/traderops/setandforget && find . -maxdepth 2 -type f | sort | sed -n "1,80p"'
```

Run key tests on VPS:

```bash
ssh traderops@38.242.214.188 'cd /home/traderops/setandforget && python3 skills/set_and_forget/run_regression_tests.py'
ssh traderops@38.242.214.188 'cd /home/traderops/setandforget && python3 skills/set_and_forget/run_paper_trade_tests.py'
```

## Secrets and environment
- Do not store secrets in git
- Keep VPS secrets in `~/.config/openclaw/gateway.env`
- Project code is deployed from git; runtime config stays on the VPS

## Notes
- The VPS deployed folder is a checked-out worktree, not the bare git repo itself
- The deployed folder does not contain its own `.git` directory
