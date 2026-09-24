# Setup

1. **Create the repo.** On GitHub, create a public repo named exactly your username (`turabforjwell/turabforjwell`). GitHub shows its README on your profile.
2. **Push these files.**
   ```bash
   cd ~/Developer/github-profile-readme
   git init && git add . && git commit -m "Profile README"
   git branch -M main
   git remote add origin https://github.com/turabforjwell/turabforjwell.git
   git push -u origin main
   ```
3. **Get an Upwork API key** at https://www.upwork.com/developer/keys/apply (OAuth 2.0, redirect URI can be `https://localhost`). Approval can take a few days. Scope needed: read marketplace job postings.
4. **Get a refresh token** once via the OAuth code flow (authorize URL → code → `POST https://www.upwork.com/api/v3/oauth2/token` with `grant_type=authorization_code`).
5. **Add repo secrets** (Settings → Secrets and variables → Actions):
   - `UPWORK_CLIENT_ID`, `UPWORK_CLIENT_SECRET`, `UPWORK_REFRESH_TOKEN`
   - `GH_PAT` — fine-grained token, this repo only, permission **Secrets: Read and write** (the script rotates the refresh token so it never expires)
6. **Run it:** Actions → *Upwork job feed* → *Run workflow*.

Edit `feed.config.json` to change search terms, the time window, or hide job titles (`"show_titles": false`).
Until the secrets exist, the Action runs and skips cleanly.
