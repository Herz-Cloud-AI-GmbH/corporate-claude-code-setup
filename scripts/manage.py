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
    - Copilot: LiteLLM proxy (ANTHROPIC_BASE_URL -> localhost:4000)
    """

    def __init__(self) -> None:
        self.workspace_root = Path(__file__).resolve().parents[1]
        self.env_file = self.workspace_root / ".devcontainer" / ".env"
        self.sample_env_file = self.workspace_root / ".devcontainer" / "sample.env"
        self.claude_settings = Path.home() / ".claude" / "settings.json"
        self.pid_file = Path("/tmp/litellm.pid")
        self.log_file = Path("/tmp/litellm.log")
        self.copilot_token_dir = Path.home() / ".config" / "litellm" / "github_copilot"
        self.copilot_api_key_file = self.copilot_token_dir / "api-key.json"
        self.copilot_access_token_file = self.copilot_token_dir / "access-token"

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
            # Claude Code may send experimental/beta params (e.g. "thinking") that
            # some non-Anthropic backends don't support.
            # Disabling experimental betas avoids those params being sent.
            "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
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

        config = env_vars.get("LITELLM_CONFIG", "").strip() or "config.copilot.yaml"
        port = env_vars.get("LITELLM_PORT", "4000")
        master_key = env_vars.get("LITELLM_MASTER_KEY", "").strip()
        config_file = self.workspace_root / "litellm" / config

        if not config_file.exists():
            self.print_error(f"Config file not found: {config_file}")
            raise SystemExit(1)
        if not master_key:
            self.print_error("LITELLM_MASTER_KEY is missing; run setup-copilot first.")
            raise SystemExit(1)

        self.print_step(f"Starting LiteLLM with config: {config_file}")

        current_env = os.environ.copy()
        current_env.update({k: v for k, v in env_vars.items() if v is not None})
        # LiteLLM v1.80+ can attempt to restructure its packaged UI assets under
        # site-packages, which fails in devcontainers due to permissions.
        # Disabling the admin UI avoids this and is fine for this local setup.
        current_env.setdefault("DISABLE_ADMIN_UI", "True")

        cmd = [
            "litellm",
            "--config",
            str(config_file),
            "--port",
            str(port)
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
        # Readiness: first ensure the HTTP server is reachable at all.
        # Note: /health may return 401 when auth is enabled and no key is passed.
        no_auth_headers: dict[str, str] = {}
        auth_headers = {"Authorization": f"Bearer {master_key}"}

        def maybe_print_copilot_device_code() -> None:
            """
            LiteLLM GitHub Copilot provider uses GitHub OAuth device flow.
            LiteLLM prints a line like:
              'Please visit https://github.com/login/device and enter code XXXX-YYYY to authenticate.'
            When LiteLLM runs in the background, that prompt ends up in /tmp/litellm.log.
            This helper surfaces it to the user.
            """
            if profile != "copilot":
                return
            try:
                if not self.log_file.exists():
                    return
                text = self.log_file.read_text(errors="ignore")
                marker = "Please visit https://github.com/login/device and enter code "
                idx = text.rfind(marker)
                if idx == -1:
                    return
                snippet = text[idx : idx + 200].splitlines()[0].strip()
                # Print only once per new snippet
                self.print_warning("GitHub Copilot authentication required.")
                print(f"{Colors.BOLD}{snippet}{Colors.ENDC}")
            except Exception:
                return

        for _ in range(30):
            if process.poll() is not None:
                self.print_error("LiteLLM process exited during startup. Check logs:")
                self.print_warning(f"Tail command: tail -f {self.log_file}")
                raise SystemExit(1)
            try:
                resp = requests.get(f"http://localhost:{port}/health", headers=no_auth_headers, timeout=2)
                # Any HTTP response means the server is up.
                self.print_success(f"LiteLLM HTTP server is up (PID {process.pid}, status {resp.status_code})")
                if resp.status_code == 401:
                    self.print_step("LiteLLM auth is enabled (401 without key is expected).")

                # Now validate the configured master key works (may take longer because /health can be slow).
                try:
                    auth_resp = requests.get(
                        f"http://localhost:{port}/health",
                        headers=auth_headers,
                        timeout=10,
                    )
                    if auth_resp.status_code == 200:
                        self.print_success("LiteLLM /health is OK with the configured key (200).")
                        break
                    if auth_resp.status_code in (401, 403):
                        self.print_error(
                            "LiteLLM is up but rejected the configured key (401/403). "
                            "Check LITELLM_MASTER_KEY in .devcontainer/.env."
                        )
                        self.print_warning(f"Tail command: tail -f {self.log_file}")
                        raise SystemExit(1)

                    # Non-200 but authenticated: don't block setup; the proxy is running.
                    self.print_warning(
                        f"LiteLLM is running but /health returned {auth_resp.status_code} with auth. "
                        "Continuing anyway; check /tmp/litellm.log if requests fail."
                    )
                    break
                except requests.exceptions.RequestException:
                    # Authenticated /health can be slow; still accept that the server is up.
                    self.print_warning(
                        "LiteLLM is running but /health (authenticated) did not respond in time. "
                        "Continuing anyway; check /tmp/litellm.log if requests fail."
                    )
                    break
            except requests.exceptions.RequestException:
                pass
            maybe_print_copilot_device_code()
            time.sleep(1)

        # If we got here, the server is up enough to proceed.
        # For GitHub Copilot, we also want to ensure provider auth is completed.
        if profile == "copilot":
            # Copilot auth can take time (user must visit GitHub device URL).
            # We surface the device code prompt and poll for a successful test request.
            self.print_step("Checking GitHub Copilot provider authentication...")
            maybe_print_copilot_device_code()

            test_payload = {
                "model": "sonnet",
                "max_tokens": 16,
                "messages": [{"role": "user", "content": "ping"}],
            }
            # Give the user time to complete the device flow.
            for _ in range(300):  # 5 minutes
                try:
                    r = requests.post(
                        f"http://localhost:{port}/v1/messages",
                        headers={**auth_headers, "Content-Type": "application/json"},
                        json=test_payload,
                        timeout=15,
                    )
                    if r.status_code == 200:
                        self.print_success("GitHub Copilot provider is authenticated and responding.")
                        return
                    # If auth isn't done yet, LiteLLM commonly returns 4xx/5xx; keep waiting.
                except requests.exceptions.RequestException:
                    pass
                maybe_print_copilot_device_code()
                time.sleep(1)

            self.print_error(
                "LiteLLM is running, but GitHub Copilot authentication is not complete. "
                "Complete the device login then re-run: make setup-copilot"
            )
            self.print_warning(f"Tail command: tail -f {self.log_file}")
            raise SystemExit(1)

        return

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

    def setup_copilot(self) -> None:
        self.print_step("Configuring for GitHub Copilot (via LiteLLM proxy)...")
        self.print_warning(
            "GitHub Copilot provider uses GitHub device login via LiteLLM. "
            "If prompted, open the URL and enter the code."
        )
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
        setup_parser.add_argument("provider", choices=["gcp", "copilot"])

        subparsers.add_parser("start", help="Start LiteLLM proxy (proxy profiles only)")
        subparsers.add_parser("stop", help="Stop LiteLLM proxy")
        subparsers.add_parser("status", help="Show status")

        args = parser.parse_args(argv)

        if args.command == "setup":
            if args.provider == "gcp":
                manager.setup_gcp()
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
