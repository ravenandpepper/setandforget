# Deploy

## Current setup
- Local development repo: `/Users/jeroenderaaf/Sites/setandforget`
- GitHub remote: `git@github.com:ravenandpepper/setandforget.git`
- VPS bare repo: `/home/traderops/repos/setandforget.git`
- VPS deployed worktree: `/home/traderops/setandforget`

The VPS deploys automatically through the bare repo `post-receive` hook.

## Remotes
- `github` = GitHub source repository
- `origin` = VPS deploy repository

## Standard workflow
1. Make changes locally in `/Users/jeroenderaaf/Sites/setandforget`
2. Run the smallest relevant local validation
3. Commit the change
4. Push `main` to `github`
5. Push `main` to `origin`

Example:

```bash
cd /Users/jeroenderaaf/Sites/setandforget
git status
git add .
git commit -m "Describe the change"
git push github main
git push origin main
```

## Recommended push flow
Push to GitHub first:

```bash
git push github main
```

Then deploy to the VPS:

```bash
git push origin main
```

## What each push does
- `git push github main`
  - updates the GitHub repository
- `git push origin main`
  - updates `/home/traderops/repos/setandforget.git`
  - triggers the VPS hook
  - checks out `main` into `/home/traderops/setandforget`

## Useful checks
Check local status:

```bash
cd /Users/jeroenderaaf/Sites/setandforget
git status
git remote -v
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
- Reserved cTrader env vars for Pepperstone adapter prep:
  `CTRADER_ENVIRONMENT`, `CTRADER_ACCOUNT_ID`, `CTRADER_CLIENT_ID`, `CTRADER_CLIENT_SECRET`, `CTRADER_REDIRECT_URI`
- Optional cTrader overrides:
  `CTRADER_AUTH_BASE_URL`, `CTRADER_API_BASE_URL`

## Notes
- The VPS deployed folder is a checked-out worktree, not the bare git repo itself
- The deployed folder does not contain its own `.git` directory
