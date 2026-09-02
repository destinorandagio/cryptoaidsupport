# CryptoAID Forgejo

Forgejo is the self-hosted Git control plane for CryptoAID. GitHub remains the public upstream and GitHub Actions remain available during migration; Forgejo adds a sovereign mirror, local collaboration surface and a future home for Forgejo Actions/runners.

## Start locally

```bash
cd infra/forgejo
cp .env.example .env
docker compose up -d
```

Open `http://localhost:3000`. The persistent Forgejo state is stored in the `forgejo-data` Docker volume.

## Bootstrap

The compose configuration starts Forgejo with installation locked and public registration disabled. Create/administer the first account from the host container, then create an organization (recommended: `cryptoaid`) and an empty `cryptoaidsupport` repository.

Example admin command after the container is healthy:

```bash
docker compose exec forgejo forgejo admin user create \
  --username cryptoaid-admin \
  --password 'CHANGE-ME-NOW' \
  --email admin@example.invalid \
  --admin \
  --must-change-password=true
```

Do not put the real password, access tokens, API keys, wallet secrets, Telegram tokens or AI provider keys in Git.

## Mirror the canonical repository

The included `scripts/forgejo-mirror.sh` performs a full Git mirror push, including branches and tags. Configure `FORGEJO_URL`, `FORGEJO_REPOSITORY` and `FORGEJO_TOKEN` only in the runtime environment/secret store.

```bash
export FORGEJO_URL=https://git.example.org
export FORGEJO_REPOSITORY=cryptoaid/cryptoaidsupport
export FORGEJO_TOKEN='...'
./scripts/forgejo-mirror.sh
```

## Target architecture

`GitHub public upstream -> CI/security gates -> Forgejo sovereign mirror -> Antigravity/local agents -> reviewed changes -> GitHub main`

During MVP closure, GitHub `main` remains canonical. Do not create two writable canonical histories. Forgejo is initially a protected mirror/control plane; promotion to canonical should happen only after runner, backup, restore and branch-protection tests pass.

## Production hardening gate

Before internet exposure: use a real DNS name and HTTPS reverse proxy; keep registration disabled; use strong admin credentials and 2FA; back up `/data`; test restore; restrict SSH/HTTP with firewall; use least-privilege tokens; configure branch protection; and pin/upgrade the Forgejo image deliberately after testing.
