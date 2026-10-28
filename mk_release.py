import subprocess, os
r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                   capture_output=True, text=True, cwd=r"C:\Users\Patrick\obsidian-live-sync\release")
token = None
for line in r.stdout.splitlines():
    if line.startswith("password="):
        token = line.split("=", 1)[1]
print("token obtained:", bool(token))
env = dict(os.environ, GH_TOKEN=token or "")
r2 = subprocess.run(["gh", "release", "create", "v1.1.1", "main.js", "manifest.json",
                     "--title", "v1.1.1", "--notes", "Quiet connection notices (opt-in setting)"],
                    capture_output=True, text=True, cwd=r"C:\Users\Patrick\obsidian-live-sync\release", env=env)
print(r2.stdout[-500:], r2.stderr[-300:])
