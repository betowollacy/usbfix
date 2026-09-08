# USB FIX

Túnel USB remoto por assinatura (estilo GFIX/USB Redirector), em Python.

```
[Box USB] ←→ [App USB FIX] ←→ [Servidor frps] ←→ [Cliente remoto]
                        │
                        └─ API FastAPI (cadastro, login, Pix/Asaas, licença, DNS)
```

Live: **https://usbfix.site** — painel do vendedor em `/admin` (token em
`TUNNEL_ADMIN_TOKEN`).

## Fluxo

1. **Cliente**: cria a conta no site com e-mail + senha (conta fica `pendente`).
2. **Cliente**: escolhe um plano (30/90/365 dias) e paga via **Pix** (Asaas).
3. **Vendedor**: no painel `/admin`, libera (Liberar 30d/Renovar) ou ajusta a
   conta; pode **Bloquear**, **Excluir** e gerar **link de redefinição de senha**
   (o cliente troca a senha abrindo `/ #reset=<token>`).
4. **Cliente**: no app, define o nome do endereço de conexão
   (ex.: `loja.usbfix.site:33456`) e conecta.

Contas ativas recebem a **key do USB Redirector** na área do cliente.

## Estrutura

```
tunnel/
├── server/                    FastAPI (produção)
│   ├── app.py                 /api/register · /api/login · /api/me ·
│   │                          /api/subdomain · /api/checkout · /api/plans ·
│   │                          /api/change-password · /api/reset-password ·
│   │                          /api/webhooks/asaas · /api/admin/*
│   ├── database.py            usuários (pbkdf2) + portas + pagamentos
│   ├── config.py              variáveis de ambiente
│   ├── frps.toml              config do frp server
│   ├── requirements.txt
│   └── site/                  site público (index.html) + painel (admin.html)
│       └── downloads/         USB-Fix.exe, usb-cliente/servidor, key.txt
├── client/                    app desktop (tkinter, só stdlib)
│   ├── main.py
│   ├── app/                   api · config · creds · tunnel · usb · gui · logo
│   ├── USB-Fix.spec           PyInstaller (exe: USB-Fix.exe)
│   ├── build_exe.bat          reconstrói o exe
│   └── download_frp.py        baixa frpc/frps (não versionado)
├── deploy/                    deploy para VPS Ubuntu (systemd + ufw)
│   ├── deploy.sh
│   ├── systemd/ (frps, tunnel-api)
│   └── tunnel.env             ⚠ SEGREDOS — não commitado
├── admin/                     ferramenta avulsa de geração de keys
├── Iniciar.bat                menu local de dev (API, painel, app)
└── README.md
```

## Planos (editáveis no painel)

| Plano | Preço | Duração |
|---|---|---|
| 30 dias | R$ 25 | 30 dias |
| 90 dias | R$ 70 | 90 dias |
| Anual | R$ 150 | 365 dias |

Gerenciados pelo painel (`/api/admin/plans`) e cobrados automaticamente pelo
Asaas via `/api/checkout`.

## Configuração (variáveis de ambiente)

| Variável | Padrão | Uso |
|---|---|---|
| `TUNNEL_ADMIN_TOKEN` | — | token do painel `/admin` |
| `TUNNEL_SUBDOMAIN_HOST` | usbfix.site | domínio base dos subdomínios |
| `TUNNEL_FRPS_ADDR` | 127.0.0.1 | IP/domínio público do frps |
| `TUNNEL_FRPS_PORT` | 7000 | porta do frps |
| `TUNNEL_FRPS_TOKEN` | tunnel-dev-token | token do túnel (troque) |
| `TUNNEL_PORT_MIN/MAX` | 40000–49999 | faixa de portas públicas |
| `ASAAS_ACCESS_TOKEN` | — | chave API do Asaas (Pix) |
| `TUNNEL_WEBHOOK_SECRET` | — | assina o webhook Asaas |
| `TUNNEL_API` | https://usbfix.site | API padrão no app do cliente |

As configurações de planos e downloads também ficam no banco (`settings`) e
são editáveis pelo painel admin.

## Produção (resumo)

- HTTPS via nginx + Certbot (Let's Encrypt) no `usbfix.site`;
- API atrás do nginx (`proxy_pass 127.0.0.1:8000`);
- `deploy/deploy.sh` sobe frps + API + systemd + ufw do zero;
- firewall: 22, 80, 443, 7000 (frp) e a faixa de portas do túnel (40000–49999).

### Upgrade via GitHub

Com o projeto publicado em `https://github.com/betowollacy/usbfix`, a VPS pode
se atualizar direto do repositório sem precisar reenviar os arquivos:

```bash
sudo bash deploy/upgrade.sh            # atualiza para a última versão
sudo bash deploy/upgrade.sh v1.2.3     # faz checkout de uma tag/commit específico
```

O script clona/puxa o repositório em `/opt/tunnel/src`, copia o `server/` para
`/opt/tunnel/server`, atualiza as dependências e reinicia `frps` e `tunnel-api`
via systemd. Requer `git` e `rsync` (já instalados pelo `deploy.sh`).

## Túnel real (frp)

Sem os binários, rode `python client/download_frp.py` (baixa frpc/frps). No
servidor: `frps -c frps.toml` com `*.usbfix.site → IP do servidor`.