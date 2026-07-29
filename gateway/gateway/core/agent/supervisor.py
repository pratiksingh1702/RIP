"""SupervisorAgent: Dual-tier Foreman Assistant for real-time task monitoring and retasking."""

from __future__ import annotations

import re
from typing import Any
from gateway.core.agent.status_log import status_log
from gateway.core.agent.signal_channel import signal_channel, AgentSignal, SignalType
from gateway.core.agent.plan_analyzer import plan_analyzer
from gateway.core.agent.impact_checker import impact_checker
from gateway.core.agent.task_state import TaskProgress
from gateway.core.agent.llm_interface import LLMInterface
from gateway.core.llm_pool.router import LLMConfig


class SupervisorAgent:
    """Read-only AI Assistant providing status explanations, file plan inspections, and retasking."""

    def __init__(self) -> None:
        self.llm = LLMInterface()

    async def answer_user_query(
        self,
        task_id: str,
        user_query: str,
        llm_config: LLMConfig | None = None,
    ) -> dict[str, Any]:
        """Main entrypoint: Classifies query tier and responds."""
        progress = await status_log.get_task_progress(task_id)
        if not progress:
            # Fallback 1: Resolve matching Docker container terminal session
            try:
                from gateway.core.sandbox.terminal import get_terminal_manager
                term = get_terminal_manager().get_terminal_by_sandbox(task_id)
                if term:
                    history = term.get_history()
                    last_cmd = history[-1]["command"] if history else "Terminal Stream"
                    progress = await status_log.init_task(task_id, query=f"Sandbox Terminal ({term.sandbox_id}): {last_cmd}")
                    for item in history:
                        await status_log.append_event(
                            task_id,
                            LogEventType.STEP_COMPLETED if item.get("exit_code") == 0 else LogEventType.STEP_FAILED,
                            step_id="cmd",
                            data={"command": item.get("command"), "exit_code": item.get("exit_code"), "output": item.get("output_preview")}
                        )
            except Exception:
                pass

        if not progress:
            # Fallback 2: Grab the most recent active task in status_log
            async with status_log._lock:
                if status_log._progress:
                    progress = list(status_log._progress.values())[-1]

        if not progress:
            return {
                "tier": "tier1",
                "answer": f"I am monitoring terminal sandbox `{task_id}`. No active pipeline commands have been executed yet.",
                "actions": [],
            }

        # Tier 1 Regex check for ultra-fast status Q&A (<100ms)
        tier1_reply = self._check_tier1(user_query, progress)
        if tier1_reply:
            return {
                "tier": "tier1",
                "answer": tier1_reply,
                "actions": ["inspect_status"],
            }

        # Tier 2 Deep Reasoning & Plan Inspection
        return await self._run_tier2_reasoning(task_id, user_query, progress, llm_config)

    def _check_tier1(self, query: str, progress: TaskProgress) -> str | None:
        q = query.lower().strip()
        
        # Greetings
        if re.search(r"\b(hi|hello|hey|status|how's it going|what's happening)\b", q):
            completed = sum(1 for s in progress.steps if s.status == "completed")
            curr_title = "Initializing"
            if progress.current_step_id:
                for s in progress.steps:
                    if s.step_id == progress.current_step_id:
                        curr_title = s.title
            return (
                f"Main agent is executing task: **{progress.original_query}**\n\n"
                f"- **Progress**: Step {progress.current_step_index + 1} of {progress.total_steps} ({completed} completed)\n"
                f"- **Active Step**: {curr_title}\n"
                f"- **Git Branch**: `{progress.git_branch or 'active'}`\n"
                f"- **Files Changed**: {len(progress.files_changed)}"
            )

        if re.search(r"\b(how much longer|time left|remaining)\b", q):
            remaining = max(0, progress.total_steps - progress.current_step_index)
            return f"There are currently **{remaining} subtasks remaining** out of {progress.total_steps} total steps."

        return None

    async def _run_tier2_reasoning(
        self,
        task_id: str,
        user_query: str,
        progress: TaskProgress,
        llm_config: LLMConfig | None = None,
    ) -> dict[str, Any]:
        """Deep reasoning with read-only state, AST diffs, and retasking synthesis."""
        events = await status_log.get_events(task_id)
        events_summary = "\n".join([f"- [{e.event_type.value}] {e.data}" for e in events[-50:]])
        
        terminal_output_context = ""
        try:
            from gateway.core.sandbox.terminal import get_terminal_manager
            term = get_terminal_manager().get_terminal_by_sandbox(task_id)
            if term:
                history = term.get_history()
                if history:
                    terminal_output_context = "\n--- COMPLETE CONTAINER TERMINAL OUTPUT HISTORY ---\n"
                    for idx, h in enumerate(history[-20:], 1):
                        cmd = h.get('command', '')
                        out = h.get('output_preview', '')
                        code = h.get('exit_code', 0)
                        terminal_output_context += f"Item {idx}: [Command: {cmd}] (Exit {code})\nOutput Output:\n{out}\n---\n"
        except Exception:
            pass

        steps_summary = "\n".join([
            f"Step {s.step_id}: {s.title} ({s.status}) - Target files: {', '.join(s.target_files)}"
            for s in progress.steps
        ])

        system_prompt = (
            "You are the RIP Supervisor Agent — a foreman assistant helping the user monitor and manage "
            "a heavy worker AI agent. The main agent is executing a coding task.\n\n"
            "Your job:\n"
            "1. Answer the user's questions about WHY the main agent is doing something, using the execution context.\n"
            "2. Summarize ALL terminal commands and output history accurately without missing past steps.\n"
            "3. If the user wants to change a plan or retask the agent, synthesize a clear, corrected subtask plan.\n"
            "4. Be concise, technical, and objective."
        )

        user_prompt = (
            f"Task: {progress.original_query}\n"
            f"Current Active Step: {progress.current_step_id}\n"
            f"Execution Steps:\n{steps_summary}\n\n"
            f"Recent Status Log:\n{events_summary}\n"
            f"{terminal_output_context}\n\n"
            f"User Question/Directive: {user_query}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        from gateway.core.llm_pool.router import get_llm_router
        llm_router = get_llm_router()
        if llm_config:
            candidate_chain = await llm_router.get_fallback_chain(config_id=llm_config.id)
        else:
            try:
                candidate_chain = await llm_router.get_fallback_chain()
            except Exception:
                candidate_chain = [LLMConfig(id="supervisor_default", provider="ollama", model="qwen2.5:3b")]

        answer = None
        for candidate in candidate_chain:
            try:
                response = await self.llm.call_with_tools(messages, [], candidate)
                if response.text and not response.text.startswith("Error:"):
                    answer = response.text
                    break
            except Exception:
                continue

        if not answer:
            answer = (
                f"I reviewed the pipeline status log for **{progress.original_query}**.\n\n"
                f"- **Active Step**: `{progress.current_step_id or 'Executing'}`\n"
                f"- **Files Modified**: {len(progress.files_changed)} file(s)\n\n"
                f"The main worker agent is actively executing tasks according to the step plan."
            )

        # Detect retask directives in user query
        actions = []
        if any(w in user_query.lower() for w in ["change", "modify", "stop", "retask", "instead", "wrong"]):
            actions.append("suggested_retask")

        return {
            "tier": "tier2",
            "answer": answer,
            "actions": actions,
            "context": {
                "active_step": progress.current_step_id,
                "files_changed": progress.files_changed,
            },
        }

    async def issue_signal(
        self,
        task_id: str,
        signal_type: SignalType,
        step_id: str | None = None,
        payload: dict[str, Any] | None = None,
        issued_by: str = "supervisor",
    ) -> AgentSignal:
        signal = AgentSignal(
            signal_id=f"sig_{task_id[:6]}_{signal_type.value}",
            task_id=task_id,
            signal_type=signal_type,
            step_id=step_id,
            payload=payload or {},
            issued_by=issued_by,
        )
        await signal_channel.publish_signal(signal)

        # If task_id belongs to a Docker container terminal session, forward input directly
        try:
            from gateway.core.sandbox.terminal import get_terminal_manager
            term = get_terminal_manager().get_terminal_by_sandbox(task_id)
            if term:
                if signal_type in (SignalType.PAUSE, SignalType.ABORT):
                    await term.write("\x03")  # Transmit Ctrl+C interrupt to PTY
                elif signal_type == SignalType.MODIFY_PLAN and payload and "command" in payload:
                    await term.write(payload["command"] + "\n")
        except Exception as e:
            logger.warning("Failed to forward signal to terminal PTY: %s", e)

        return signal


# Global singleton instance
supervisor_agent = SupervisorAgent()
