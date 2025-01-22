### HackTheBox Challenge Escape Two

##Enumération 

```
nmap -F -Pn $IP 
```

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
