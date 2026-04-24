# Setting Up a New Machine

This guide explains how to set up a new computer so you can manage the server and deploy changes from it.

> **Why new keys?** Each machine gets its own unique keys. If a laptop is lost or stolen, you can revoke just that machine's access without touching anything else.

---

## What You'll Need

- About 15 minutes
- Access to your server (via another machine, or the VPS provider console)
- Access to your GitHub account

---

## Step 1 — Install Git

**macOS:**
```bash
xcode-select --install
```

**Debian / Ubuntu:**
```bash
sudo apt install git
```

**Windows:** Download from https://git-scm.com

---

## Step 2 — Configure Git Identity

```bash
git config --global user.name "Your Name"
git config --global user.email "psdiablox@gmail.com"
```

---

## Step 3 — Create a Key for GitHub

This key lets you push code changes to GitHub.

```bash
ssh-keygen -t ed25519 -C "my-new-computer" -f ~/.ssh/github -N ""
```

Now add it to your GitHub account:

1. Copy the key to your clipboard:
   ```bash
   cat ~/.ssh/github.pub
   ```
2. Go to **https://github.com/settings/keys** → **New SSH key**
3. Title: something recognisable like `macbook-home` or `work-laptop`
4. Key type: **Authentication Key**
5. Paste the key → **Add SSH key**

Tell SSH to use this key for GitHub:

```bash
cat >> ~/.ssh/config << 'EOF'

Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/github
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
EOF
chmod 600 ~/.ssh/config
```

Test it — you should see **"Hi psdiablox!"**:
```bash
ssh -T git@github.com
```

---

## Step 4 — Create a Key for the Server

This key lets you SSH into the server to deploy and manage things.

```bash
ssh-keygen -t ed25519 -C "my-new-computer-server" -f ~/.ssh/server_key -N ""
```

Now add it to the server. **You'll need access from another machine that already has server access** (or use your VPS provider's web console):

```bash
# Run this from a machine that already has server access
ssh -i ~/.ssh/server_key deploy@82.223.64.68 \
  "echo 'ssh-ed25519 PASTE_YOUR_NEW_PUBLIC_KEY_HERE' >> ~/.ssh/authorized_keys"
```

To get your new public key:
```bash
cat ~/.ssh/server_key.pub
```

Test the connection from your new machine:
```bash
ssh -i ~/.ssh/server_key deploy@82.223.64.68 "echo connected"
```

You should see `connected`.

---

## Step 5 — Add the Server Key to Your SSH Agent

This lets you use the key without typing a path every time:

```bash
ssh-add ~/.ssh/server_key
```

> On macOS, add `--apple-use-keychain` to save the passphrase permanently:
> ```bash
> ssh-add --apple-use-keychain ~/.ssh/server_key
> ```

---

## Step 6 — Clone the Repository

```bash
git clone git@github.com:psdiablox/Server-Connections-agent.git
cd Server-Connections-agent
```

---

## Step 7 — Verify Everything Works

```bash
# Can you push to GitHub?
git push origin main

# Can you reach the server?
ssh -i ~/.ssh/server_key deploy@82.223.64.68 "docker ps --format '{{.Names}}: {{.Status}}' | head -5"
```

You should see a list of running containers.

---

## You're Ready

You can now make changes, commit, and deploy:

```bash
# Make a change, save it to GitHub
git add .
git commit -m "describe your change"
git push origin main

# Deploy it to the server
make ship SERVICE=infrastructure/services/vaultwarden
```

---

## When You Stop Using a Machine

When a computer is retired, lost, or sold — revoke its access:

**Remove GitHub access:**
1. Go to **https://github.com/settings/keys**
2. Delete the key for that machine

**Remove server access:**
```bash
ssh -i ~/.ssh/server_key deploy@82.223.64.68
nano ~/.ssh/authorized_keys
# Delete the line containing that machine's key
```

---

## Summary of Keys

| Key file | What it's for | Where it's registered |
|----------|--------------|----------------------|
| `~/.ssh/github` | Pushing to GitHub | github.com/settings/keys |
| `~/.ssh/server_key` | SSH into the server | `/home/deploy/.ssh/authorized_keys` on server |
