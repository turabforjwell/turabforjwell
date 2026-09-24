"""Refresh the Upwork job feed section of README.md.

Env (GitHub secrets):
  UPWORK_CLIENT_ID, UPWORK_CLIENT_SECRET, UPWORK_REFRESH_TOKEN  - Upwork API key (OAuth2)
  GH_PAT            - fine-grained token with "Secrets: write" on this repo (rotates the refresh token)
  GITHUB_REPOSITORY - set by Actions
Without Upwork secrets the script exits cleanly and leaves README untouched.
"""
import base64, json, os, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
CONFIG = json.load(open(os.path.join(ROOT, "feed.config.json")))
TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
GQL_URL = "https://api.upwork.com/graphql"
START, END = "<!-- UPWORK-FEED:START -->", "<!-- UPWORK-FEED:END -->"

QUERY = """
query($filter: MarketplaceJobPostingsSearchFilter, $sort: [MarketplaceJobPostingSearchSortAttribute]) {
  marketplaceJobPostingsSearch(marketPlaceJobFilter: $filter, searchType: USER_JOBS_SEARCH, sortAttributes: $sort) {
    totalCount
    edges { node { title ciphertext createdDateTime } }
  }
}"""


def post(url, data, headers):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def refresh_access_token():
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": os.environ["UPWORK_CLIENT_ID"],
        "client_secret": os.environ["UPWORK_CLIENT_SECRET"],
        "refresh_token": os.environ["UPWORK_REFRESH_TOKEN"],
    }).encode()
    tok = post(TOKEN_URL, body, {"Content-Type": "application/x-www-form-urlencoded"})
    new_refresh = tok.get("refresh_token")
    if new_refresh and new_refresh != os.environ["UPWORK_REFRESH_TOKEN"]:
        rotate_secret("UPWORK_REFRESH_TOKEN", new_refresh)
    return tok["access_token"]


def rotate_secret(name, value):
    pat, repo = os.environ.get("GH_PAT"), os.environ.get("GITHUB_REPOSITORY")
    if not (pat and repo):
        print("::warning::Refresh token rotated but GH_PAT missing; update the secret manually.")
        return
    from nacl import encoding, public
    h = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=h)
    key = json.loads(urllib.request.urlopen(req).read())
    box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
    enc = base64.b64encode(box.encrypt(value.encode())).decode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
        data=json.dumps({"encrypted_value": enc, "key_id": key["key_id"]}).encode(),
        headers={**h, "Content-Type": "application/json"}, method="PUT")
    urllib.request.urlopen(req)
    print(f"Rotated secret {name}")


def search(token, query):
    variables = {
        "filter": {"searchExpression_eq": query, "daysPosted_eq": CONFIG["days_posted"]},
        "sort": [{"field": "RECENCY"}],
    }
    res = post(GQL_URL, json.dumps({"query": QUERY, "variables": variables}).encode(),
               {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    if res.get("errors"):
        raise RuntimeError(res["errors"])
    return res["data"]["marketplaceJobPostingsSearch"]


def md_escape(s):
    return re.sub(r"([\[\]|*_`<>])", r"\\\1", s.strip())


def render(results):
    days = CONFIG["days_posted"]
    lines = [f"| Service | New jobs (last {days}d) | Browse |", "|---|---:|---|"]
    for label, query, data in results:
        url = "https://www.upwork.com/nx/search/jobs/?" + urllib.parse.urlencode({"q": query, "sort": "recency"})
        lines.append(f"| **{label}** | {data['totalCount']:,} | [Search →]({url}) |")
    if CONFIG.get("show_titles"):
        n = CONFIG.get("titles_per_service", 3)
        lines += ["", "<details><summary><b>Latest matches</b></summary>", ""]
        for label, _, data in results:
            edges = data["edges"][:n]
            if not edges:
                continue
            lines.append(f"**{label}**")
            for e in edges:
                node = e["node"]
                link = f"https://www.upwork.com/jobs/{node['ciphertext']}"
                lines.append(f"- [{md_escape(node['title'])}]({link})")
            lines.append("")
        lines.append("</details>")
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    lines += ["", f"<sub>Updated {stamp} · via Upwork API</sub>"]
    return "\n".join(lines)


def main():
    if not all(os.environ.get(k) for k in ("UPWORK_CLIENT_ID", "UPWORK_CLIENT_SECRET", "UPWORK_REFRESH_TOKEN")):
        print("Upwork secrets not set; skipping feed update.")
        return 0
    token = refresh_access_token()
    results = [(s["label"], s["query"], search(token, s["query"])) for s in CONFIG["services"]]
    readme = open(README, encoding="utf-8").read()
    block = f"{START}\n{render(results)}\n{END}"
    updated = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, readme, flags=re.S)
    open(README, "w", encoding="utf-8").write(updated)
    print("README feed updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
