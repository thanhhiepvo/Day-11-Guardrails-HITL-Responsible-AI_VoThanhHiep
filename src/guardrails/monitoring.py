"""
Assignment 11 — Monitoring & Alerts

Tracks block rates across pipeline layers and fires alerts when thresholds
are exceeded, enabling operators to detect attack campaigns early.
"""


class MonitoringAlert:
    """Aggregate plugin metrics and raise alerts when thresholds are exceeded."""

    DEFAULT_THRESHOLDS = {
        "input_block_rate": 0.50,
        "rate_limit_hit_rate": 0.30,
        "judge_fail_rate": 0.40,
        "output_redact_rate": 0.30,
    }

    def __init__(self, plugins: list, thresholds: dict | None = None):
        self.plugins = {p.name: p for p in plugins}
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.alerts: list[str] = []

    def _rate(self, blocked: int, total: int) -> float:
        return blocked / total if total else 0.0

    def check_metrics(self) -> list[str]:
        """Evaluate all plugin metrics and return any triggered alerts."""
        self.alerts = []

        rate_limiter = self.plugins.get("rate_limiter")
        if rate_limiter and rate_limiter.total_count:
            rate = self._rate(rate_limiter.blocked_count, rate_limiter.total_count)
            if rate >= self.thresholds["rate_limit_hit_rate"]:
                self.alerts.append(
                    f"ALERT: Rate limit hit rate {rate:.0%} exceeds "
                    f"{self.thresholds['rate_limit_hit_rate']:.0%}"
                )

        input_guard = self.plugins.get("input_guardrail")
        if input_guard and input_guard.total_count:
            rate = self._rate(input_guard.blocked_count, input_guard.total_count)
            if rate >= self.thresholds["input_block_rate"]:
                self.alerts.append(
                    f"ALERT: Input block rate {rate:.0%} exceeds "
                    f"{self.thresholds['input_block_rate']:.0%}"
                )

        output_guard = self.plugins.get("output_guardrail")
        if output_guard and output_guard.total_count:
            rate = self._rate(output_guard.redacted_count, output_guard.total_count)
            if rate >= self.thresholds["output_redact_rate"]:
                self.alerts.append(
                    f"ALERT: Output redaction rate {rate:.0%} exceeds "
                    f"{self.thresholds['output_redact_rate']:.0%}"
                )

        judge = self.plugins.get("llm_judge")
        if judge and judge.total_count:
            rate = self._rate(judge.fail_count, judge.total_count)
            if rate >= self.thresholds["judge_fail_rate"]:
                self.alerts.append(
                    f"ALERT: Judge fail rate {rate:.0%} exceeds "
                    f"{self.thresholds['judge_fail_rate']:.0%}"
                )

        return self.alerts

    def print_report(self):
        """Print metric summary and any active alerts."""
        print("\n" + "=" * 60)
        print("MONITORING REPORT")
        print("=" * 60)

        for name, plugin in self.plugins.items():
            total = getattr(plugin, "total_count", 0)
            blocked = getattr(plugin, "blocked_count", 0)
            extra = ""
            if name == "output_guardrail":
                extra = f", redacted={getattr(plugin, 'redacted_count', 0)}"
            elif name == "llm_judge":
                blocked = getattr(plugin, "fail_count", 0)
            if total:
                print(f"  {name}: {blocked}/{total} flagged{extra}")

        alerts = self.check_metrics()
        if alerts:
            print("\nActive alerts:")
            for alert in alerts:
                print(f"  ⚠ {alert}")
        else:
            print("\nNo alerts — all metrics within thresholds.")
        print("=" * 60)
