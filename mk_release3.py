import json, urllib.request, os

token = open(os.path.join(os.environ["TEMP"], "ghtok.txt"), encoding="utf-8").read().strip()
H = {"Authorization": "token " + token, "Accept": "application/vnd.github+json", "User-Agent": "dsh"}
API = "https://api.github.com/repos/hoyin-law/obsidian-live-sync"

def req(method, url, data=None, raw=None, ctype="application/json"):
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    q = urllib.request.Request(url, data=body, method=method, headers={**H, "Content-Type": ctype})
    with urllib.request.urlopen(q, timeout=60) as resp:
        return json.loads(resp.read() or b"{}")

rels = req("GET", API + "/releases")
for rel in rels:
    if rel["tag_name"] == "v1.1.1":
        req("DELETE", rel["url"]); print("deleted partial release")

rel = req("POST", API + "/releases", data={
    "tag_name": "v1.1.1", "name": "v1.1.1",
    "body": "Quiet connection notices (opt-in setting). No more popup on every note open."})
print("release created:", rel["html_url"])
up = rel["upload_url"].split("{")[0]
d = r"C:\Users\Patrick\obsidian-live-sync\release"
for fn in ["main.js", "manifest.json"]:
    req("POST", f"{up}?name={fn}", raw=open(os.path.join(d, fn), "rb").read(), ctype="application/octet-stream")
    print("uploaded", fn)
