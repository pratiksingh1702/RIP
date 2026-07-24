"""Environment Templates — Pre-built Docker images for common stacks."""
from __future__ import annotations
from typing import Any

ENVIRONMENT_TEMPLATES: dict[str, dict[str, Any]] = {
    "python": {"name":"Python","description":"Python 3.12 with pip, uv, pytest, ruff, black, mypy, IPython","image":"python:3.12-slim","icon":"code","color":"#3776AB","packages":["python3","python3-pip","python3-venv","git","curl","wget","build-essential"],"post_install":["pip install --upgrade pip uv pytest ruff black mypy ipython"],"default_shell":"/bin/bash"},
    "node": {"name":"Node.js","description":"Node.js 20 with npm, yarn, pnpm, TypeScript, ESLint, Prettier, Jest","image":"node:20-slim","icon":"javascript","color":"#339933","packages":["git","curl","wget","build-essential"],"post_install":["npm install -g npm@latest yarn pnpm typescript eslint prettier jest ts-node"],"default_shell":"/bin/bash"},
    "flutter": {"name":"Flutter","description":"Flutter SDK with Dart, Android tools","image":"ghcr.io/cirruslabs/flutter:3.22.0","icon":"phone_android","color":"#02569B","packages":["git","curl","wget"],"post_install":["flutter doctor"],"default_shell":"/bin/bash"},
    "rust": {"name":"Rust","description":"Rust with cargo, clippy, rustfmt","image":"rust:1.78-slim","icon":"build","color":"#DEA584","packages":["git","curl","wget","build-essential"],"post_install":["rustup component add clippy rustfmt"],"default_shell":"/bin/bash"},
    "go": {"name":"Go","description":"Go 1.22 with golangci-lint","image":"golang:1.22-slim","icon":"terminal","color":"#00ADD8","packages":["git","curl","wget","build-essential"],"post_install":["go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest"],"default_shell":"/bin/bash"},
    "java": {"name":"Java","description":"OpenJDK 21 with Maven, Gradle","image":"eclipse-temurin:21-jdk","icon":"coffee","color":"#ED8B00","packages":["git","curl","wget"],"post_install":[],"default_shell":"/bin/bash"},
    "fullstack": {"name":"Full Stack","description":"Python + Node.js + PostgreSQL + Redis","image":"python:3.12-slim","icon":"layers","color":"#6366F1","packages":["python3","python3-pip","python3-venv","nodejs","npm","postgresql-client","redis-tools","git","curl","wget","build-essential"],"post_install":["pip install --upgrade pip uv pytest ruff black mypy ipython","npm install -g npm@latest yarn pnpm"],"default_shell":"/bin/bash"},
    "devops": {"name":"DevOps","description":"Terraform, kubectl, Helm, AWS CLI, gcloud","image":"ubuntu:24.04","icon":"cloud","color":"#F59E0B","packages":["git","curl","wget","gnupg","lsb-release","ca-certificates","unzip","jq","yq","vim","nano"],"post_install":[],"default_shell":"/bin/bash"},
    "datascience": {"name":"Data Science","description":"Python with Jupyter, pandas, numpy, scikit-learn","image":"python:3.12-slim","icon":"bar_chart","color":"#10B981","packages":["python3","python3-pip","git","curl","wget","build-essential"],"post_install":["pip install jupyter pandas numpy scikit-learn matplotlib seaborn plotly"],"default_shell":"/bin/bash"},
    "blank": {"name":"Blank Linux","description":"Ubuntu 24.04 with git, curl, vim, build-essential","image":"ubuntu:24.04","icon":"terminal","color":"#64748B","packages":["git","curl","wget","vim","nano","build-essential","ca-certificates"],"post_install":[],"default_shell":"/bin/bash"},
}

class EnvironmentRegistry:
    def list_environments(self) -> list[dict[str, Any]]:
        return [{"id":eid,"name":c["name"],"description":c["description"],"icon":c.get("icon","terminal"),"color":c.get("color","#64748B")} for eid,c in ENVIRONMENT_TEMPLATES.items()]
    def get_environment(self, environment_id: str) -> dict[str, Any] | None: return ENVIRONMENT_TEMPLATES.get(environment_id)
    def get_default_environment(self) -> str: return "python"

_registry: EnvironmentRegistry | None = None
def get_environment_registry() -> EnvironmentRegistry:
    global _registry
    if _registry is None: _registry = EnvironmentRegistry()
    return _registry
