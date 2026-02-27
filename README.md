# kroger-grocery-tool

A simple CLI tool + OpenClaw skill for searching Kroger/Fry's products and adding items to your cart via the [Kroger Public API](https://developer.kroger.com).

## Features

- 🔍 Search products with prices and sale info
- 🏪 Find nearby Kroger/Fry's stores
- 🛒 Add grocery lists to your cart by name
- 🔑 OAuth2 cart authentication with automatic token refresh

## Setup

### 1. Get Kroger API credentials

Go to [developer.kroger.com](https://developer.kroger.com/manage/apps/register), create an account, register an app, and grab your Client ID and Client Secret. Set your redirect URI to `http://localhost:8000/callback`.

### 2. Install dependencies

```bash
pip3 install kroger-api
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your credentials and zip code
```

### 4. Authorize cart access (one-time)

```bash
python3 auth_cart.py
```

Open the URL it prints, log into your Kroger/Fry's account, then paste the redirect URL back into the terminal. Token is saved automatically.

## Usage

### Find nearby stores
```bash
python3 kroger_tool.py stores
python3 kroger_tool.py stores --set-default 1
```

### Search products
```bash
python3 kroger_tool.py search "oat milk"
python3 kroger_tool.py search "eggs" --limit 5
```

### Add items to cart
```bash
# Preview first
python3 kroger_tool.py cart "eggs" "bread" "bananas" --dry-run

# Add to cart
python3 kroger_tool.py cart "eggs" "bread" "bananas"
```

## Notes

- The Kroger public API only supports `cart.basic:write` — cart read is a partner-only scope
- Tokens are saved locally and refreshed automatically
- Rate limits: Products 10k/day, Locations 1.6k/day, Cart 5k/day

## OpenClaw Skill

This repo includes a skill at `skills/kroger/SKILL.md` for use with [OpenClaw](https://openclaw.ai). Drop the `skills/` folder into your OpenClaw workspace to enable natural language grocery ordering via Discord/iMessage/etc.
