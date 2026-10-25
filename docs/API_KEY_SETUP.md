# Setting up your own Anthropic API key

GRFP Scorer's best reading comes from Claude, accessed through Anthropic's API with a key
**you** create and pay for. The author does not provide keys and never sees yours. This
takes about five minutes. If you would rather not pay anything, skip to
[Free alternative](#free-alternative-ollama) at the end.

## 1. Create a Console account

Go to **https://console.anthropic.com** and sign up. This is separate from a claude.ai
subscription — a Claude Pro or Max plan does **not** include API access, and a claude.ai
login does not work here.

## 2. Add credit and set a spend limit

Under **Billing**, add prepaid credit. A scoring run is roughly 9,000 tokens, which at
Sonnet-tier pricing is on the order of 5–10 cents, so **$5 comfortably covers an entire
application season** of scoring drafts. Check the current prices at
https://www.anthropic.com/pricing (they change).

Then, still under Billing, **set a monthly spend limit** (for example $10). This caps what
the key can cost you even if something goes wrong.

## 3. Create a key

Under **API Keys**, click *Create Key*, name it (e.g. "GRFP Scorer"), and copy it. The
full key is shown **only once**; it starts with `sk-ant-`. If you lose it, delete it and
make a new one.

## 4. Put it in the app

Either on the first-launch screen or later under **Settings…**, paste the key into
*Anthropic API key* and click **Test**. Within a few seconds you should see
*✓ Claude reachable*. The key is stored only on your computer, in
`~/.grfp_scorer/config.json`, with owner-only permissions. Deleting that folder removes it.

## 5. Keep it private

Treat the key like a password. Do not paste it into documents, screenshots, or shared
drives. If you think it has leaked, delete it in the Console — a leaked key costs one click
to replace, and your spend limit bounds the damage in the meantime.

## What is sent where

With the Claude backend, the app sends **the text of your statement and the rubric** to
Anthropic's API under your key, and nothing else. Anthropic's API terms and privacy policy
govern that data; as of this writing, Anthropic states that API inputs are not used to
train its models, but check their current policy yourself. The author of GRFP Scorer
receives none of your statement text under any backend.

Score only drafts you are entitled to send to a third-party service — your own.

## Troubleshooting

| Message | Meaning |
|---|---|
| *authentication_error* / 401 | The key is wrong or was deleted. Make a new one. |
| *insufficient credit* / 400 billing | Add prepaid credit under Billing. |
| *rate_limit* / 429 | You have hit your spend limit or a per-minute cap. Wait, or raise the limit. |
| *not_found* / 404 on the model | The model id in Settings is stale. Leave it at the default. |
| Connection error | A network or firewall is blocking `api.anthropic.com`. Try another network, or use Ollama. |

## Free alternative: Ollama

1. Install Ollama from https://ollama.com/download and open it.
2. In a terminal: `ollama pull qwen2.5:14b` (≈9 GB; needs 16 GB RAM) or
   `ollama pull llama3.1:8b` (≈5 GB; 8 GB RAM — less reliable).
3. Start GRFP Scorer with no API key set. It detects Ollama and uses it automatically.

Nothing leaves your computer. Expect scores a point or so lower than Claude on the
judgement items, and several minutes per run on older hardware.
