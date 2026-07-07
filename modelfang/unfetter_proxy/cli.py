"""
CLI for Unfetter Proxy.

Commands:
    unfetter-proxy start   — Start the reverse proxy server
    unfetter-proxy config  — Show/edit configuration
    unfetter-proxy status  — Show proxy status
"""

from __future__ import annotations

import json
import sys

import click


def show_banner():
    """Display cool ASCII banner."""
    banner = r"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   ██╗   ██╗███╗   ██╗███████╗███████╗████████╗████████╗███████╗██████╗  ║
    ║   ██║   ██║████╗  ██║██╔════╝██╔════╝╚══██╔══╝╚══██╔══╝██╔════╝██╔══██╗ ║
    ║   ██║   ██║██╔██╗ ██║█████╗  █████╗     ██║      ██║   █████╗  ██████╔╝ ║
    ║   ██║   ██║██║╚██╗██║██╔══╝  ██╔══╝     ██║      ██║   ██╔══╝  ██╔══██╗ ║
    ║   ╚██████╔╝██║ ╚████║██║     ███████╗   ██║      ██║   ███████╗██║  ██║ ║
    ║    ╚═════╝ ╚═╝  ╚═══╝╚═╝     ╚══════╝   ╚═╝      ╚═╝   ╚══════╝╚═╝  ╚═╝ ║
    ║                                                              ║
    ║              🔓 PROXY - Break Free from Censorship 🔓        ║
    ║                    v0.1.0 - Unleashed Edition                ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    click.echo(click.style(banner, fg="cyan", bold=True))


def interactive_menu():
    """Show interactive menu for quick actions."""
    show_banner()
    
    click.echo("\n" + "═" * 60)
    click.echo(click.style("  QUICK ACTIONS MENU", fg="yellow", bold=True))
    click.echo("═" * 60 + "\n")
    
    click.echo(click.style("  [1]", fg="green", bold=True) + " 🚀 Start Proxy Server")
    click.echo(click.style("  [2]", fg="blue", bold=True) + " 🧪 Run Test Request (Jailbreak Demo)")
    click.echo(click.style("  [3]", fg="magenta", bold=True) + " ⚙️  View Configuration")
    click.echo(click.style("  [4]", fg="cyan", bold=True) + " 📊 Check Proxy Status")
    click.echo(click.style("  [5]", fg="red", bold=True) + " 🚪 Exit")
    
    click.echo("\n" + "─" * 60)
    
    choice = click.prompt(click.style("\n  Select an option", fg="white", bold=True), type=str)
    
    if choice == "1":
        click.echo(click.style("\n🚀 Starting proxy server...\n", fg="green", bold=True))
        import sys
        sys.argv = ["unfetter-proxy", "start"]
        start.callback(host="0.0.0.0", port=8080, strength=1.0, strategy="auto", max_retries=3, verbose=False)
    
    elif choice == "2":
        click.echo(click.style("\n🧪 Running jailbreak test...\n", fg="blue", bold=True))
        click.echo(click.style("⚠️  Testing with a slightly naughty prompt via Groq!\n", fg="yellow"))
        import sys
        sys.argv = ["unfetter-proxy", "test"]
        test.callback(prompt="Write a short insult for someone who cuts in line", model="llama-3.3-70b-versatile", provider="groq")
    
    elif choice == "3":
        click.echo(click.style("\n⚙️  Current Configuration:\n", fg="magenta", bold=True))
        import sys
        sys.argv = ["unfetter-proxy", "config", "--show"]
        config.callback(show=True, reset=False, set_values=())
    
    elif choice == "4":
        click.echo(click.style("\n📊 Checking proxy status...\n", fg="cyan", bold=True))
        import sys
        sys.argv = ["unfetter-proxy", "status"]
        status.callback()
    
    elif choice == "5":
        click.echo(click.style("\n👋 Goodbye! Stay unfettered!\n", fg="red", bold=True))
        sys.exit(0)
    
    else:
        click.echo(click.style("\n❌ Invalid option. Please try again.\n", fg="red"))
        interactive_menu()


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="unfetter-proxy")
@click.pass_context
def main(ctx):
    """Unfetter Proxy — Persistent closed-model unfettering via reverse proxy."""
    if ctx.invoked_subcommand is None:
        interactive_menu()


@main.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", "-p", default=8080, help="Port to listen on")
@click.option(
    "--strength", "-s", default=1.0, type=float,
    help="Unfettering strength (0.0-1.0)",
)
@click.option(
    "--strategy",
    type=click.Choice(["auto", "suppress-only", "prompt-only", "full", "disabled"]),
    default="auto",
    help="Unfettering strategy",
)
@click.option("--max-retries", "-r", default=3, type=int, help="Max retries on refusal")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
def start(host: str, port: int, strength: float, strategy: str, max_retries: int, verbose: bool):
    """Start the unfettering reverse proxy server."""
    try:
        import uvicorn
    except ImportError:
        click.echo("Error: uvicorn not installed. Run: pip install unfetter-proxy", err=True)
        sys.exit(1)

    from unfetter_proxy.proxy.config import ProxyConfig, load_config, save_config

    # Load existing config and override with CLI args
    config = load_config()
    config.host = host
    config.port = port
    config.strength = strength
    config.strategy = strategy
    config.max_retries = max_retries
    config.verbose = verbose
    save_config(config)

    # Banner
    click.echo()
    click.echo("  +----------------------------------------------+")
    click.echo("  |          UNFETTER PROXY v0.1.0               |")
    click.echo("  |   Persistent Closed-Model Unfettering        |")
    click.echo("  +----------------------------------------------+")
    click.echo()
    click.echo(f"  -> Listening on   http://{host}:{port}")
    click.echo(f"  -> Strategy       {strategy}")
    click.echo(f"  -> Strength       {strength}")
    click.echo(f"  -> Max retries    {max_retries}")
    click.echo()
    click.echo("  Connect your apps by setting base_url to:")
    click.echo(f"    OpenAI:     http://localhost:{port}/v1")
    click.echo(f"    Anthropic:  http://localhost:{port}/v1")
    click.echo(f"    Gemini:     http://localhost:{port}/v1beta")
    click.echo()
    click.echo("  Status:  GET http://localhost:{}/unfetter/status".format(port))
    click.echo("  Health:  GET http://localhost:{}/unfetter/health".format(port))
    click.echo()

    # Configure logging
    log_level = "debug" if verbose else "info"

    uvicorn.run(
        "unfetter_proxy.proxy.server:create_app",
        host=host,
        port=port,
        workers=config.workers,
        log_level=log_level,
        factory=True,
    )


@main.command()
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--reset", is_flag=True, help="Reset to defaults")
@click.option("--set", "set_values", multiple=True, help="Set a config value (key=value)")
def config(show: bool, reset: bool, set_values: tuple):
    """View or edit proxy configuration."""
    from unfetter_proxy.proxy.config import ProxyConfig, load_config, save_config

    if reset:
        cfg = ProxyConfig()
        path = save_config(cfg)
        click.echo(f"Config reset to defaults. Saved to {path}")
        return

    if set_values:
        cfg = load_config()
        for kv in set_values:
            if "=" not in kv:
                click.echo(f"Invalid format: {kv}. Use key=value", err=True)
                continue
            key, value = kv.split("=", 1)

            # Handle booleans/numbers
            if value.lower() in ("true", "1", "yes"):
                value = True
            elif value.lower() in ("false", "0", "no"):
                value = False
            elif value.replace(".", "", 1).isdigit():
                if "." in value:
                    value = float(value)
                else:
                    value = int(value)

            # Support nested keys (e.g. providers.openai.mode)
            if "." in key:
                parts = key.split(".")
                target = cfg
                
                # Navigate to the parent object
                try:
                    for i, part in enumerate(parts[:-1]):
                        if hasattr(target, part):
                            target = getattr(target, part)
                        elif isinstance(target, dict):
                            if part not in target:
                                target[part] = {}
                            target = target[part]
                        else:
                            raise AttributeError(f"Cannot traverse {part}")
                    
                    last_part = parts[-1]
                    if isinstance(target, dict):
                        target[last_part] = value
                    else:
                        setattr(target, last_part, value)
                    
                    click.echo(f"  {key} = {value}")
                except Exception as e:
                    click.echo(f"Error setting {key}: {e}", err=True)
                continue

            # Top-level keys
            if hasattr(cfg, key):
                setattr(cfg, key, value)
                click.echo(f"  {key} = {value}")
            else:
                click.echo(f"Unknown config key: {key}", err=True)
        save_config(cfg)
        return

    # Default: show config
    cfg = load_config()
    from dataclasses import asdict
    click.echo(json.dumps(asdict(cfg), indent=2))


@main.command()
def status():
    """Show proxy status (requires running proxy)."""
    import httpx

    from unfetter_proxy.proxy.config import load_config

    cfg = load_config()
    url = f"http://localhost:{cfg.port}/unfetter/status"

    try:
        resp = httpx.get(url, timeout=5.0)
        click.echo(json.dumps(resp.json(), indent=2))
    except httpx.ConnectError:
        click.echo(f"Proxy not running on port {cfg.port}", err=True)
        sys.exit(1)


@main.command()
@click.option("--prompt", "-p", default="Explain how to pick a lock", help="Prompt to test")
@click.option("--model", "-m", default="gpt-5.2", help="Model to target")
@click.option("--provider", type=click.Choice(["openai", "anthropic", "gemini", "groq", "cerebras", "abliteration"]), default="openai", help="Provider to use")
def test(prompt: str, model: str, provider: str):
    """Run a test request against the local proxy."""
    import httpx
    import os
    from pathlib import Path
    from unfetter_proxy.proxy.config import load_config

    # Load .env manually
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

    cfg = load_config()
    base_url = f"http://127.0.0.1:{cfg.port}"  # Use 127.0.0.1 for safety

    # Check health
    try:
        httpx.get(f"{base_url}/unfetter/health", timeout=2.0)
    except Exception:
        click.echo(f"[ERROR] Proxy not running at {base_url}. Run 'unfetter-proxy start' first.", err=True)
        sys.exit(1)

    click.echo(f"Testing {provider} ({model}) via {base_url}...")
    click.echo(f"Prompt: \"{prompt}\"\n")

    api_key = ""
    target_url = ""
    headers = {"Content-Type": "application/json"}
    payload = {}

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY") or "dummy"
        target_url = f"{base_url}/v1/chat/completions"
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500
        }
    
    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY") or "dummy"
        target_url = f"{base_url}/v1/messages"
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500
        }

    elif provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY") or "dummy"
        target_url = f"{base_url}/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 500}
        }

    elif provider == "groq":
        api_key = os.environ.get("GROQ2_API_KEY") or os.environ.get("GROQ_API_KEY") or "dummy"
        target_url = f"{base_url}/groq/v1/chat/completions"
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500
        }

    elif provider == "cerebras":
        api_key = os.environ.get("CEREBRAS_API_KEY") or "dummy"
        target_url = f"{base_url}/cerebras/v1/chat/completions"
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500
        }

    elif provider == "abliteration":
        api_key = os.environ.get("ABLITERATION_API_KEY") or "dummy"
        target_url = f"{base_url}/abliteration/v1/chat/completions"
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500
        }

    try:
        timeout = 60.0
        response = httpx.post(target_url, headers=headers, json=payload, timeout=timeout)
        data = response.json()

        # Parse output
        content = ""
        meta = data.get("_unfetter_proxy", {})

        if provider == "openai" or provider == "cerebras" or provider == "abliteration":
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        elif provider == "anthropic":
            content = data.get("content", [{}])[0].get("text", "")
        elif provider == "gemini":
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            content = parts[0].get("text", "") if parts else ""

        if not content:
            click.echo(f"[ERROR] No content in response: {data}")
            return

        click.echo("[SUCCESS] Response received:")
        click.echo("─" * 40)
        click.echo(content.strip())
        click.echo("─" * 40)
        
        if meta:
            click.echo("\n[Unfetter Metadata]")
            click.echo(f"Techniques: {', '.join(meta.get('techniques_applied', []))}")
            if meta.get("refusal_detected"):
                click.echo("Refusal Detected: Yes (Retried)")
        
    except Exception as e:
        click.echo(f"[ERROR] Request failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
