"""ImpactChecker: Graph-based dependency fan-in analysis and risk calculation."""

from __future__ import annotations

from pathlib import Path
import re


class ImpactChecker:
    """Calculates file impact scores, fan-in dependencies, and risk levels."""

    SENSITIVE_PATHS = ["auth", "security", "payment", "billing", "token", "crypto", "database", "gateway"]

    def analyze_file(self, file_path: str, repo_root: str | None = None) -> tuple[int, bool, str]:
        """Returns (dependent_count, has_high_fan_in, risk_level)."""
        clean_path = file_path.lower().replace("\\", "/")
        
        # Check sensitivity
        is_sensitive = any(s in clean_path for s in self.SENSITIVE_PATHS)
        
        dependent_count = 0
        if repo_root and Path(repo_root).exists():
            dependent_count = self._count_imports(file_path, repo_root)

        has_high_fan_in = dependent_count >= 3
        
        if is_sensitive or dependent_count >= 5:
            risk_level = "high"
        elif has_high_fan_in or "core" in clean_path:
            risk_level = "medium"
        else:
            risk_level = "low"

        return dependent_count, has_high_fan_in, risk_level

    def _count_imports(self, file_path: str, repo_root: str) -> int:
        """Simple regex fallback search for import occurrences of file module."""
        stem = Path(file_path).stem
        if len(stem) <= 2:
            return 0
        
        pattern = re.compile(rf"\b(import|from)\b.*?\b{re.escape(stem)}\b")
        count = 0
        root = Path(repo_root)
        
        # Scan python/dart/js/ts files
        for p in root.rglob("*"):
            if p.is_file() and p.suffix in (".py", ".dart", ".js", ".ts"):
                if str(p.resolve()) == str(Path(file_path).resolve()):
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    if pattern.search(text):
                        count += 1
                        if count >= 10:
                            break
                except Exception:
                    pass
        return count


# Global singleton instance
impact_checker = ImpactChecker()
