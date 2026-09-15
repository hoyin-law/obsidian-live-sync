import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("129.204.145.142", username="root", password="HoYinLaw.1", timeout=15)
def run(cmd, t=60):
    i,o,e = c.exec_command(cmd, timeout=t)
    o.channel.recv_exit_status()
    print(f"$ {cmd}\n{o.read().decode(errors=chr(39)+'replace'+chr(39))}{e.read().decode(errors=chr(39)+'replace'+chr(39))}")

# 给 server.js 加连接日志（重启服务不影响数据，房间是内存态）
srv = open("obsidian-live-sync/server/server.js", encoding="utf-8").read()
srv = srv.replace(
  'wss.handleUpgrade(req, socket, head, (ws) => {',
  'wss.handleUpgrade(req, socket, head, (ws) => {\n    console.log(new Date().toISOString(), "client connected, room:", decodeURIComponent(req.url.split("?")[0]));'
)
sftp = c.open_sftp()
with sftp.file("/opt/live-sync/server.js", "w") as f:
    f.write(srv)
sftp.close()
run("systemctl restart live-sync && sleep 1 && systemctl is-active live-sync")
c.close()
print("日志已开启，等待客户端重连...")
