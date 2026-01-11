#!/usr/bin/env python3
import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values, load_dotenv, set_key


class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


class ClaudeSetupManager:
    """
    Two-mode setup:
    - GCP: native Vertex AI (no LiteLLM)
    - Ollama/Copilot: LiteLLM proxy (ANTHROPIC_BASE_URL -> localhost:4000)
    """

    def __init__(self) -> None:
        self.workspace_root = Path(__file__).resolve().parents[1]
        self.env_file = self.workspace_root / ".devcontainer" / ".env"
        self.sample_env_file = self.workspace_root / ".devcontainer" / "sample.env"
        self.claude_settings = Path.home() / ".claude" / "settings.json"
        self.pid_file = Path("/tmp/litellm.pid")
        self.log_file = Path("/tmp/litellm.log")

    # --------- output helpers ---------
    def print_step(self, message: str) -> None:
        print(f"{Colors.BLUE}→ {message}{Colors.ENDC}")

    def print_success(self, message: str) -> None:
        print(f"{Colors.GREEN}✅ {message}{Colors.ENDC}")

    def print_warning(self, message: str) -> None:
        print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}")

    def print_error(self, message: str) -> None:
        print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")

    # --------- env helpers ---------
    def ensure_env_file(self) -> None:
        if self.env_file.exists():
            return
        if not self.sample_env_file.exists():
            self.print_error(f"Sample env file not found: {self.sample_env_file}")
            raise SystemExit(1)
        self.print_step(f"Creating {self.env_file} from {self.sample_env_file}")
        self.env_file.write_text(self.sample_env_file.read_text())

    def load_env_vars(self) -> dict:
        self.ensure_env_file()
        load_dotenv(self.env_file, override=True)
        return dict(dotenv_values(self.env_file))

    def update_env_vars(self, updates: dict[str, str]) -> None:
        self.ensure_env_file()
        for key, value in updates.items():
            # Avoid writing quoted values like PROFILE='gcp' which then break comparisons.
            set_key(self.env_file, key, value, quote_mode="never")
        self.print_step(f"Updated {self.env_file}")

    def check_command(self, command: str) -> bool:
        return (
            subprocess.call(
                f"command -v {command}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            == 0
        )

    def generate_master_key(self) -> str:
        return secrets.token_hex(32)

    # --------- claude settings generation ---------
    def write_claude_settings(self, env: dict) -> None:
        self.claude_settings.parent.mkdir(parents=True, exist_ok=True)
        self.claude_settings.write_text(json.dumps({"env": env}, indent=2) + "\n")
        self.print_step(f"Wrote {self.claude_settings}")

    def build_gcp_native_settings_env(self, env_vars: dict) -> dict:
        project_id = env_vars.get("GCP_PROJECT_ID", "")
        if not project_id:
            self.print_warning("GCP_PROJECT_ID is missing in .env for GCP profile")

        cloud_region = env_vars.get("CLOUD_ML_REGION", "global")
        # Keep compatibility with the original (main-branch) env naming.
        # These should be Vertex Claude model IDs like "claude-sonnet-4-5@20250929".
        model = env_vars.get("ANTHROPIC_MODEL", "")
        small_fast_model = env_vars.get("ANTHROPIC_SMALL_FAST_MODEL", "")

        # Native Vertex: do NOT set ANTHROPIC_BASE_URL or any LiteLLM-related vars.
        settings_env: dict[str, str] = {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": project_id,
            "CLOUD_ML_REGION": cloud_region,
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "true",
        }

        # Optional model configuration (kept compatible with original main-branch approach)
        if model:
            settings_env["ANTHROPIC_MODEL"] = model
        if small_fast_model:
            settings_env["ANTHROPIC_SMALL_FAST_MODEL"] = small_fast_model

        return settings_env

    def build_proxy_settings_env(self, env_vars: dict) -> dict:
        port = env_vars.get("LITELLM_PORT", "4000")
        base_url = f"http://localhost:{port}"
        master_key = env_vars.get("LITELLM_MASTER_KEY", "")

        # Proxy mode: Claude Code talks Anthropic-format to LiteLLM.
        return {
            "ANTHROPIC_BASE_URL": base_url,
            "ANTHROPIC_AUTH_TOKEN": master_key,
            "ANTHROPIC_MODEL": "sonnet",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "opus",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "haiku",
            "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "true",
        }

    # --------- gcp helpers ---------
    def ensure_gcp_project_id(self) -> None:
        env_vars = self.load_env_vars()
        if env_vars.get("GCP_PROJECT_ID"):
            return

        # Try to auto-detect from gcloud config
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip() and "(unset)" not in result.stdout:
                project_id = result.stdout.strip()
                self.print_step(f"Auto-detected GCP Project ID: {project_id}")
                self.update_env_vars({"GCP_PROJECT_ID": project_id})
                return
        except Exception:
            pass

        # Fall back to prompt
        print(f"{Colors.WARNING}GCP Project ID not found in .env{Colors.ENDC}")
        project_id = input(f"{Colors.BOLD}Enter your GCP Project ID: {Colors.ENDC}").strip()
        if not project_id:
            self.print_error("Project ID is required for GCP setup.")
            raise SystemExit(1)
        self.update_env_vars({"GCP_PROJECT_ID": project_id})

    def authenticate_gcp_adc(self, project_id: str) -> None:
        if not self.check_command("gcloud"):
            self.print_error("gcloud CLI not found. Cannot authenticate.")
            raise SystemExit(1)

        self.print_step("Authenticating with GCP (ADC)...")
        subprocess.run(["gcloud", "config", "set", "project", project_id], check=True)
        subprocess.run(["gcloud", "auth", "application-default", "login"], check=True)

    # --------- litellm helpers ---------
    def stop_litellm(self) -> None:
        if not self.pid_file.exists():
            self.print_step("LiteLLM is not running")
            return

        pid = self.pid_file.read_text().strip()
        try:
            if pid.isdigit():
                os.kill(int(pid), 15)  # SIGTERM
                self.print_step(f"Stopped LiteLLM (PID {pid})")
                time.sleep(1)
        except ProcessLookupError:
            pass
        finally:
            self.pid_file.unlink(missing_ok=True)

    def start_litellm(self) -> None:
        env_vars = self.load_env_vars()
        profile = env_vars.get("PROFILE", "gcp")
        if profile == "gcp":
            self.print_error("LiteLLM is not used for PROFILE=gcp (native Vertex mode).")
            raise SystemExit(1)

        self.stop_litellm()

        config = env_vars.get("LITELLM_CONFIG", "").strip() or "config.ollama.yaml"
        port = env_vars.get("LITELLM_PORT", "4000")
        master_key = env_vars.get("LITELLM_MASTER_KEY", "").strip()
        config_file = self.workspace_root / "litellm" / config

        if not config_file.exists():
            self.print_error(f"Config file not found: {config_file}")
            raise SystemExit(1)
        if not master_key:
            self.print_error("LITELLM_MASTER_KEY is missing; run setup-ollama or setup-copilot first.")
            raise SystemExit(1)

        self.print_step(f"Starting LiteLLM with config: {config_file}")

        current_env = os.environ.copy()
        current_env.update({k: v for k, v in env_vars.items() if v is not None})

        cmd = [
            "litellm",
            "--config",
            str(config_file),
            "--port",
            str(port),
            "--master-key",
            master_key,
        ]

        with open(self.log_file, "w") as log:
            process = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=log,
                preexec_fn=os.setsid,
                env=current_env,
            )
            self.pid_file.write_text(str(process.pid))

        self.print_step("Waiting for LiteLLM to be ready...")
        headers = {"Authorization": f"Bearer {master_key}"}
        for _ in range(10):
            try:
                resp = requests.get(f"http://localhost:{port}/health", headers=headers, timeout=1)
                if resp.status_code == 200:
                    self.print_success(f"LiteLLM started successfully (PID {process.pid})")
                    return
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)

        self.print_error("LiteLLM failed to start. Check logs:")
        self.print_warning(f"Tail command: tail -f {self.log_file}")
        raise SystemExit(1)

    def check_ollama(self) -> None:
        try:
            response = requests.get("http://host.docker.internal:11434/api/tags", timeout=2)
            if response.status_code == 200:
                self.print_success("Ollama is running on host")
                return
        except requests.exceptions.RequestException:
            pass

        self.print_error("Ollama is NOT running on http://host.docker.internal:11434")
        self.print_warning("Please start Ollama on your host machine: 'ollama serve'")
        raise SystemExit(1)

    def ensure_master_key(self) -> None:
        env_vars = self.load_env_vars()
        key = (env_vars.get("LITELLM_MASTER_KEY") or "").strip()
        if not key or key == "your-litellm-master-key":
            self.update_env_vars({"LITELLM_MASTER_KEY": self.generate_master_key()})

    # --------- high-level commands ---------
    def setup_gcp(self) -> None:
        self.print_step("Configuring for GCP Vertex AI (native)...")
        self.update_env_vars({"PROFILE": "gcp"})
        self.stop_litellm()

        self.ensure_gcp_project_id()
        env_vars = self.load_env_vars()
        project_id = env_vars["GCP_PROJECT_ID"]
        self.authenticate_gcp_adc(project_id)

        self.write_claude_settings(self.build_gcp_native_settings_env(env_vars))
        self.print_success("GCP setup complete (native Vertex mode).")

    def setup_ollama(self) -> None:
        self.print_step("Configuring for Ollama (via LiteLLM proxy)...")
        self.check_ollama()
        self.update_env_vars({"PROFILE": "ollama", "LITELLM_CONFIG": "config.ollama.yaml"})
        self.ensure_master_key()
        env_vars = self.load_env_vars()
        self.write_claude_settings(self.build_proxy_settings_env(env_vars))
        self.start_litellm()
        self.print_success("Ollama setup complete (proxy mode).")

    def setup_copilot(self) -> None:
        self.print_step("Configuring for GitHub Copilot (via LiteLLM proxy)...")
        self.print_warning("Ensure you are logged in to GitHub Copilot in VS Code/Cursor")
        self.update_env_vars({"PROFILE": "copilot", "LITELLM_CONFIG": "config.copilot.yaml"})
        self.ensure_master_key()
        env_vars = self.load_env_vars()
        self.write_claude_settings(self.build_proxy_settings_env(env_vars))
        self.start_litellm()
        self.print_success("Copilot setup complete (proxy mode).")

    def status(self) -> None:
        print(f"\n{Colors.BOLD}Claude Code Status{Colors.ENDC}\n")
        env_vars = self.load_env_vars()
        profile = env_vars.get("PROFILE", "None")
        print(f"Active Profile: {Colors.BLUE}{profile}{Colors.ENDC}")
        print(f"LiteLLM Config: {env_vars.get('LITELLM_CONFIG', 'None')}\n")

        if profile == "gcp":
            self.print_success("LiteLLM Proxy: Not used for GCP (native Vertex mode)")
        else:
            if self.pid_file.exists():
                pid = self.pid_file.read_text().strip()
                try:
                    os.kill(int(pid), 0)
                    self.print_success(f"LiteLLM Proxy: Running (PID {pid})")
                except (ProcessLookupError, ValueError):
                    self.print_error("LiteLLM Proxy: Not running (stale PID)")
            else:
                self.print_error("LiteLLM Proxy: Not running")
        print("")

        if self.claude_settings.exists():
            self.print_success(f"Claude Config: {self.claude_settings}")
            try:
                data = json.loads(self.claude_settings.read_text())
                is_vertex = data.get("env", {}).get("CLAUDE_CODE_USE_VERTEX") == "1"
                if is_vertex:
                    print(f"   {Colors.BLUE}Mode: Vertex AI (native){Colors.ENDC}")
                else:
                    print(f"   {Colors.BLUE}Mode: Proxy (LiteLLM){Colors.ENDC}")
            except Exception:
                pass
        else:
            self.print_error("Claude Config: Not found")
        print("")

    @classmethod
    def run_cli(cls, argv: list[str] | None = None) -> None:
        manager = cls()
        parser = argparse.ArgumentParser(description="Manage Claude Code setup")
        subparsers = parser.add_subparsers(dest="command", help="Command to run")

        setup_parser = subparsers.add_parser("setup", help="Setup a provider")
        setup_parser.add_argument("provider", choices=["gcp", "ollama", "copilot"])

        subparsers.add_parser("start", help="Start LiteLLM proxy (proxy profiles only)")
        subparsers.add_parser("stop", help="Stop LiteLLM proxy")
        subparsers.add_parser("status", help="Show status")

        args = parser.parse_args(argv)

        if args.command == "setup":
            if args.provider == "gcp":
                manager.setup_gcp()
            elif args.provider == "ollama":
                manager.setup_ollama()
            elif args.provider == "copilot":
                manager.setup_copilot()
        elif args.command == "start":
            manager.start_litellm()
        elif args.command == "stop":
            manager.stop_litellm()
        elif args.command == "status":
            manager.status()
        else:
            parser.print_help()


if __name__ == "__main__":
    ClaudeSetupManager.run_cli()
