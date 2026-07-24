"""Sandbox Security — Command validation, allowlists, resource limits."""
from __future__ import annotations
import re, shlex
from dataclasses import dataclass, field
from enum import StrEnum

class CommandRisk(StrEnum):
    SAFE = "safe"
    RESTRICTED = "restricted"
    BLOCKED = "blocked"

@dataclass
class SecurityPolicy:
    allowlisted_commands: list[str] = field(default_factory=lambda: [
        "ls","dir","pwd","cd","cat","head","tail","less","more","find","grep","wc","sort","uniq","cut","awk","sed","tree","stat","file","du","df","touch","mkdir","cp","mv","ln","chmod","chown","echo","printf","tee","git","nano","vim","vi","code","pip","pip3","uv","poetry","npm","npx","yarn","pnpm","cargo","go","dart","flutter","pub","apt","apt-get","gem","composer","python","python3","node","ruby","php","perl","javac","java","gcc","g++","clang","make","cmake","pytest","jest","mocha","vitest","go test","cargo test","flutter test","ruff","black","mypy","pylint","eslint","prettier","gofmt","golangci-lint","cargo clippy","rustfmt","curl","wget","ping","traceroute","ps","top","htop","free","uptime","uname","whoami","id","env","printenv","which","whereis","kill","killall","nohup","bg","fg","jobs","docker","docker-compose","aws","gcloud","az","kubectl","helm","terraform","gradle","mvn","sbt","tar","gzip","gunzip","zip","unzip","ssh","scp","rsync","screen","tmux","jq","yq","xargs"
    ])
    restricted_commands: dict[str, str] = field(default_factory=lambda: {
        "rm": "File deletion","rmdir": "Directory deletion","rm -rf": "Recursive force deletion",
        "git push": "Pushing to remote","git push --force": "Force push","npm publish": "Publishing packages",
        "docker push": "Pushing images","kubectl apply": "Applying K8s config","kubectl delete": "Deleting K8s resources",
        "terraform apply": "Applying Terraform","terraform destroy": "Destroying infrastructure"
    })
    blocked_patterns: list[str] = field(default_factory=lambda: [
        r"rm\s+-rf\s+/",r"mkfs\.",r"dd\s+if=",r"shutdown",r"reboot",r"halt",r"poweroff",r"mount\s+/dev",
        r"umount\s+/",r"iptables",r"ufw",r">\\s*/dev/sd",r"chmod\s+777\s+/"
    ])
    resource_limits: dict[str, str] = field(default_factory=lambda: {"cpu_limit":"2.0","memory_limit":"2g","memory_swap":"3g","storage_limit":"10g","process_limit":"100","timeout_seconds":"120"})

    def validate_command(self, command: str) -> tuple[bool, str, CommandRisk]:
        if not command or not command.strip(): return False, "Empty command", CommandRisk.BLOCKED
        cmd_lower = command.lower().strip()
        for pattern in self.blocked_patterns:
            if re.search(pattern, cmd_lower): return False, "Command blocked by security policy", CommandRisk.BLOCKED
        try: parts = shlex.split(command, posix=False)
        except ValueError: return False, "Invalid command syntax", CommandRisk.BLOCKED
        if not parts: return False, "No command found", CommandRisk.BLOCKED
        base = parts[0].lower()
        for restricted_cmd, reason in self.restricted_commands.items():
            if cmd_lower.startswith(restricted_cmd.lower()): return True, reason, CommandRisk.RESTRICTED
        for allowed in self.allowlisted_commands:
            if base == allowed.lower() or cmd_lower.startswith(allowed.lower() + " "): return True, "ok", CommandRisk.SAFE
        if base.startswith("./") or base.startswith("/"): return True, "ok", CommandRisk.SAFE
        return True, f"Unknown command: {base}", CommandRisk.RESTRICTED

    def needs_approval(self, risk: CommandRisk) -> bool: return risk in (CommandRisk.RESTRICTED, CommandRisk.BLOCKED)
    def is_blocked(self, command: str) -> bool: _, _, risk = self.validate_command(command); return risk == CommandRisk.BLOCKED
    def sanitize_for_logging(self, command: str) -> str:
        s = command
        for pattern in [r'--password\s+\S+', r'-p\s+\S+', r'PASSWORD=\S+', r'TOKEN=\S+', r'API_KEY=\S+', r'SECRET=\S+']:
            s = re.sub(pattern, lambda m: m.group(0).split('=')[0] + '=***' if '=' in m.group(0) else m.group(0).split()[0] + ' ***', s, flags=re.IGNORECASE)
        return s

_security_policy: SecurityPolicy | None = None
def get_security_policy() -> SecurityPolicy:
    global _security_policy
    if _security_policy is None: _security_policy = SecurityPolicy()
    return _security_policy
