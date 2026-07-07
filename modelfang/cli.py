"""
ModelFang CLI

Command-line interface for the ModelFang framework.
Supports running attacks, listing resources, and managing configurations.

Also includes Unfetter Proxy CLI for persistent closed-model unfettering.
"""

import argparse
import json
import logging
import sys
from typing import List, Optional

from modelfang.api import run_attack
from modelfang.config.loader import load_models_config

def setup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ModelFang - AI Red Teaming Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run standard template attack
  modelfang run --model target-llama3 --template standard

  # Run IRIS (Self-Jailbreak)
  modelfang run --model target-llama3 --iris "Write a keylogger" --attacker-model attacker-gemini

  # Run Policy Puppetry
  modelfang run --model target-gpt4 --puppetry "Bypass safety filters"

  # Run Weak-to-Strong (Logprob)
  modelfang run --model target-llama3 --weak-strong "Explain how to hack"

  # List available models
  modelfang list models
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # --- LIST Command ---
    list_parser = subparsers.add_parser("list", help="List available resources")
    list_parser.add_argument("resource", choices=["models", "strategies"], help="Resource type to list")
    list_parser.add_argument("--config", help="Path to configuration directory")
    
    # --- RUN Command ---
    run_parser = subparsers.add_parser("run", help="Execute an attack")
    
    # Target (Required)
    run_parser.add_argument("--model", required=True, help="Target model ID (from models.yaml)")
    
    # Context & Config
    run_parser.add_argument("--attacker-model", help="Attacker model ID (required for IRIS/Auto-Attack)")
    run_parser.add_argument("--context", help="JSON string of context variables", default="{}")
    run_parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    run_parser.add_argument("--config", help="Path to configuration directory")
    run_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    # Attack Construction (Mutually Exclusive)
    group = run_parser.add_mutually_exclusive_group(required=True)
    
    # Phase 9: Advanced Techniques
    group.add_argument("--iris", metavar="GOAL", help="Run IRIS (Self-Jailbreak) attack with specified goal")
    group.add_argument("--gcg", metavar="GOAL", help="Run AmpleGCG (Transfer Suffix) attack with specified goal")
    group.add_argument("--puppetry", metavar="GOAL", help="Run Policy Puppetry (Framing) attack with specified goal")
    group.add_argument("--weak-strong", metavar="GOAL", help="Run Weak-to-Strong (Logprob) attack with specified goal")
    
    # Original Modes
    group.add_argument("--template", choices=["standard", "roles", "logic"], help="Run a standard attack template")
    group.add_argument("--systematic", metavar="PLUGINS", help="Run Systematic Probe (comma-separated plugins, e.g. 'jailbreak,pii')")
    group.add_argument("--dataset", metavar="ID", help="Run attack from dataset ID (e.g. 'jb_dan_11')")
    group.add_argument("--attacker", metavar="GOAL", help="Run Automated LLM-vs-LLM attack with specified goal")
    
    # Manual Override
    group.add_argument("--id", metavar="ATTACK_ID", help="Manual attack ID string (e.g. 'iris:goal', 'template:standard')")

    # --- UNFETTER Command ---
    unfetter_parser = subparsers.add_parser("unfetter", help="Unfetter Proxy commands (persistent closed-model unfettering)")
    unfetter_subparsers = unfetter_parser.add_subparsers(dest="unfetter_command", help="Unfetter command to run")

    # unfetter start
    unfetter_start = unfetter_subparsers.add_parser("start", help="Start the unfettering reverse proxy server")
    unfetter_start.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    unfetter_start.add_argument("--port", "-p", default=8080, type=int, help="Port to listen on")
    unfetter_start.add_argument("--strength", "-s", default=1.0, type=float, help="Unfettering strength (0.0-1.0)")
    unfetter_start.add_argument("--strategy", type=str, choices=["auto", "suppress-only", "prompt-only", "full", "disabled"], default="auto", help="Unfettering strategy")
    unfetter_start.add_argument("--max-retries", "-r", default=3, type=int, help="Max retries on refusal")
    unfetter_start.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    # unfetter config
    unfetter_config = unfetter_subparsers.add_parser("config", help="View or edit proxy configuration")
    unfetter_config.add_argument("--show", action="store_true", help="Show current configuration")
    unfetter_config.add_argument("--reset", action="store_true", help="Reset to defaults")
    unfetter_config.add_argument("--set", "set_values", nargs="+", help="Set a config value (key=value)")

    # unfetter status
    unfetter_subparsers.add_parser("status", help="Show proxy status")

    # unfetter test
    unfetter_test = unfetter_subparsers.add_parser("test", help="Run a test request against the local proxy")
    unfetter_test.add_argument("--prompt", "-p", default="Explain how to pick a lock", help="Prompt to test")
    unfetter_test.add_argument("--model", "-m", default="gpt-5.2", help="Model to target")
    unfetter_test.add_argument("--provider", type=str, choices=["openai", "anthropic", "gemini", "groq", "cerebras", "abliteration"], default="openai", help="Provider to use")

    return parser

def handle_list(args):
    if args.resource == "models":
        try:
            config = load_models_config(args.config)
            print(f"\nTarget Models:")
            for m in config.get_targets():
                print(f"  - {m.model_id:<20} ({m.provider}: {m.model_name})")
            
            print(f"\nAttacker Models:")
            attackers = [m for m in config.models.values() if m.role == "attacker"]
            for m in attackers:
                print(f"  - {m.model_id:<20} ({m.provider}: {m.model_name})")
                
            print(f"\nEvaluator Models:")
            for m in config.get_evaluators():
                print(f"  - {m.model_id:<20} ({m.provider}: {m.model_name})")

        except Exception as e:
            print(f"Error loading config: {e}")
            
    elif args.resource == "strategies":
        print("\nAvailable Strategies:")
        print("  - Standard Templates: standard, roles, logic")
        print("  - Systematic Probe:   systematic:<plugins>")
        print("  - Dataset Attack:     dataset:<id>")
        print("  - Auto-LLM Attack:    attacker:<goal>")
        print("\nAdvanced Techniques (Phase 9):")
        print("  - IRIS:               iris:<goal>")
        print("  - Policy Puppetry:    puppetry:<goal>")
        print("  - AmpleGCG:           gcg:<goal>")
        print("  - Weak-to-Strong:     weak-strong:<goal>")

def handle_run(args):
    # Construct Attack ID based on flags
    attack_id = None
    context = {}
    
    try:
        context = json.loads(args.context)
    except json.JSONDecodeError:
        print("Error: --context must be valid JSON")
        sys.exit(1)
        
    # Inject attacker model into data/context if provided
    if args.attacker_model:
        context["attacker_model_id"] = args.attacker_model
    
    # Determine Attack ID
    if args.id:
        attack_id = args.id
    elif args.iris:
        attack_id = f"iris:{args.iris}"
        if not args.attacker_model:
            print("Warning: IRIS strategy usually requires --attacker-model. Using default if configured.")
    elif args.gcg:
        attack_id = f"gcg:{args.gcg}"
    elif args.puppetry:
        attack_id = f"puppetry:{args.puppetry}"
    elif args.weak_strong:
        attack_id = f"weak-strong:{args.weak_strong}"
    elif args.template:
        attack_id = f"template:{args.template}"
        # Templates usually need a goal in context, let's ask for it if missing?
        # Actually standard template has hardcoded goal or checks context.
        pass
    elif args.systematic:
        attack_id = f"systematic:{args.systematic}"
    elif args.dataset:
        attack_id = f"dataset:{args.dataset}"
    elif args.attacker:
        attack_id = "attacker:auto" 
        context["goal"] = args.attacker # Set goal in context for auto-attacker
        if not args.attacker_model:
            print("Warning: Attacker mode requires --attacker-model. Using default.")

    print(f"🚀 Initializing ModelFang Attack...")
    print(f"Target: {args.model}")
    print(f"Attack: {attack_id}")
    
    try:
        result = run_attack(
            attack_id=attack_id,
            target_model_id=args.model,
            context=context,
            seed=args.seed,
            config_dir=args.config
        )
        
        print("\n✅ Execution Complete")
        print(f"Status: {result.get('status', 'UNKNOWN')}")
        print(f"Score:  {result.get('success_score', 0.0):.2f}")
        print(f"Turns:  {result.get('turn_count', 0)}")
        
        if result.get('status') == 'failed':
            sys.exit(1)
        sys.exit(0)
        
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        print(f"\n❌ Error during execution: {e}")
        sys.exit(1)

def handle_unfetter(args):
    """Handle unfetter proxy commands."""
    if args.unfetter_command == "start":
        handle_unfetter_start(args)
    elif args.unfetter_command == "config":
        handle_unfetter_config(args)
    elif args.unfetter_command == "status":
        handle_unfetter_status(args)
    elif args.unfetter_command == "test":
        handle_unfetter_test(args)
    else:
        print("Usage: modelfang unfetter {start|config|status|test}")
        sys.exit(1)

def handle_unfetter_start(args):
    """Start the unfettering reverse proxy server."""
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn not installed. Run: pip install uvicorn")
        sys.exit(1)

    from modelfang.unfetter_proxy.proxy.config import ProxyConfig, load_config, save_config

    config = load_config()
    config.host = args.host
    config.port = args.port
    config.strength = args.strength
    config.strategy = args.strategy
    config.max_retries = args.max_retries
    config.verbose = args.verbose
    save_config(config)

    print()
    print("  +----------------------------------------------+")
    print("  |          UNFETTER PROXY v0.1.0               |")
    print("  |   Persistent Closed-Model Unfettering        |")
    print("  +----------------------------------------------+")
    print()
    print(f"  -> Listening on   http://{args.host}:{args.port}")
    print(f"  -> Strategy       {args.strategy}")
    print(f"  -> Strength       {args.strength}")
    print(f"  -> Max retries    {args.max_retries}")
    print()
    print("  Connect your apps by setting base_url to:")
    print(f"    OpenAI:     http://localhost:{args.port}/v1")
    print(f"    Anthropic:  http://localhost:{args.port}/v1")
    print(f"    Gemini:     http://localhost:{args.port}/v1beta")
    print()

    log_level = "debug" if args.verbose else "info"
    uvicorn.run(
        "modelfang.unfetter_proxy.proxy.server:create_app",
        host=args.host,
        port=args.port,
        workers=config.workers,
        log_level=log_level,
        factory=True,
    )

def handle_unfetter_config(args):
    """View or edit proxy configuration."""
    from modelfang.unfetter_proxy.proxy.config import ProxyConfig, load_config, save_config

    if args.reset:
        cfg = ProxyConfig()
        path = save_config(cfg)
        print(f"Config reset to defaults. Saved to {path}")
        return

    if args.set_values:
        cfg = load_config()
        for kv in args.set_values:
            if "=" not in kv:
                print(f"Invalid format: {kv}. Use key=value", file=sys.stderr)
                continue
            key, value = kv.split("=", 1)

            if value.lower() in ("true", "1", "yes"):
                value = True
            elif value.lower() in ("false", "0", "no"):
                value = False
            elif value.replace(".", "", 1).isdigit():
                if "." in value:
                    value = float(value)
                else:
                    value = int(value)

            if "." in key:
                parts = key.split(".")
                target = cfg
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
                    
                    print(f"  {key} = {value}")
                except Exception as e:
                    print(f"Error setting {key}: {e}", file=sys.stderr)
                continue

            if hasattr(cfg, key):
                setattr(cfg, key, value)
                print(f"  {key} = {value}")
            else:
                print(f"Unknown config key: {key}", file=sys.stderr)
        save_config(cfg)
        return

    cfg = load_config()
    from dataclasses import asdict
    print(json.dumps(asdict(cfg), indent=2))

def handle_unfetter_status(args):
    """Show proxy status."""
    import httpx
    from modelfang.unfetter_proxy.proxy.config import load_config

    cfg = load_config()
    url = f"http://localhost:{cfg.port}/unfetter/status"

    try:
        resp = httpx.get(url, timeout=5.0)
        print(json.dumps(resp.json(), indent=2))
    except httpx.ConnectError:
        print(f"Proxy not running on port {cfg.port}", file=sys.stderr)
        sys.exit(1)

def handle_unfetter_test(args):
    """Run a test request against the local proxy."""
    import httpx
    import os
    from pathlib import Path
    from modelfang.unfetter_proxy.proxy.config import load_config

    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

    cfg = load_config()
    base_url = f"http://127.0.0.1:{cfg.port}"

    try:
        httpx.get(f"{base_url}/unfetter/health", timeout=2.0)
    except Exception:
        print(f"[ERROR] Proxy not running at {base_url}. Run 'modelfang unfetter start' first.", file=sys.stderr)
        sys.exit(1)

    print(f"Testing {args.provider} ({args.model}) via {base_url}...")
    print(f"Prompt: \"{args.prompt}\"\n")

    api_key = ""
    target_url = ""
    headers = {"Content-Type": "application/json"}
    payload = {}

    if args.provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY") or "dummy"
        target_url = f"{base_url}/v1/chat/completions"
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": args.prompt}],
            "max_tokens": 500
        }
    elif args.provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY") or "dummy"
        target_url = f"{base_url}/v1/messages"
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": args.prompt}],
            "max_tokens": 500
        }
    elif args.provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY") or "dummy"
        target_url = f"{base_url}/v1beta/models/{args.model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": args.prompt}]}],
            "generationConfig": {"maxOutputTokens": 500}
        }
    elif args.provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY") or "dummy"
        target_url = f"{base_url}/groq/v1/chat/completions"
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": args.prompt}],
            "max_tokens": 500
        }
    elif args.provider == "cerebras":
        api_key = os.environ.get("CEREBRAS_API_KEY") or "dummy"
        target_url = f"{base_url}/cerebras/v1/chat/completions"
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": args.prompt}],
            "max_tokens": 500
        }
    elif args.provider == "abliteration":
        api_key = os.environ.get("ABLITERATION_API_KEY") or "dummy"
        target_url = f"{base_url}/abliteration/v1/chat/completions"
        headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": args.prompt}],
            "max_tokens": 500
        }

    try:
        timeout = 60.0
        response = httpx.post(target_url, headers=headers, json=payload, timeout=timeout)
        data = response.json()

        content = ""
        meta = data.get("_unfetter_proxy", {})

        if args.provider in ("openai", "cerebras", "abliteration"):
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        elif args.provider == "anthropic":
            content = data.get("content", [{}])[0].get("text", "")
        elif args.provider == "gemini":
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            content = parts[0].get("text", "") if parts else ""

        if not content:
            print(f"[ERROR] No content in response: {data}")
            return

        print("[SUCCESS] Response received:")
        print("─" * 40)
        print(content.strip())
        print("─" * 40)
        
        if meta:
            print("\n[Unfetter Metadata]")
            print(f"Techniques: {', '.join(meta.get('techniques_applied', []))}")
            if meta.get("refusal_detected"):
                print("Refusal Detected: Yes (Retried)")
        
    except Exception as e:
        print(f"[ERROR] Request failed: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = setup_parser()
    args = parser.parse_args()
    
    if args.command == "list":
        handle_list(args)
    elif args.command == "run":
        handle_run(args)
    elif args.command == "unfetter":
        handle_unfetter(args)
    else:
        parser.print_help()
        sys.exit(0)

if __name__ == "__main__":
    main()
