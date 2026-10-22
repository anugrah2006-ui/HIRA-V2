# core/agent.py

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from services.ai_service import generate_text


@dataclass
class Tool:
    name: str
    description: str
    function: Callable[..., Any]
    dangerous: bool = False


@dataclass
class AgentStep:
    tool: str
    arguments: Dict[str, Any] = field(default_factory=dict)


class HiraAgent:
    """
    HIRA Agent Mode.

    Converts a natural-language request into a small executable plan,
    executes registered tools, and returns a final response.
    """

    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.max_steps = 8

    # ---------------------------------------------------------
    # TOOL REGISTRATION
    # ---------------------------------------------------------

    def register_tool(
        self,
        name: str,
        description: str,
        function: Callable[..., Any],
        dangerous: bool = False,
    ):
        self.tools[name] = Tool(
            name=name,
            description=description,
            function=function,
            dangerous=dangerous,
        )

    # ---------------------------------------------------------
    # TOOL DESCRIPTION FOR AI
    # ---------------------------------------------------------

    def get_tool_descriptions(self) -> str:
        if not self.tools:
            return "No tools are currently available."

        lines = []

        for tool in self.tools.values():
            danger = " [CONFIRMATION REQUIRED]" if tool.dangerous else ""

            lines.append(
                f"- {tool.name}: {tool.description}{danger}"
            )

        return "\n".join(lines)

    # ---------------------------------------------------------
    # PLANNER
    # ---------------------------------------------------------

    def create_plan(self, user_request: str) -> List[AgentStep]:

        prompt = f"""
You are the planning brain of HIRA, a Windows AI assistant.

User request:
{user_request}

Available tools:

{self.get_tool_descriptions()}

Create a plan using ONLY the available tools.

Return ONLY valid JSON.

Format:

{{
    "steps": [
        {{
            "tool": "tool_name",
            "arguments": {{}}
        }}
    ]
}}

Rules:

1. Use the minimum number of steps necessary.
2. Never invent tools.
3. Never invent arguments.
4. If the request does not require tools, return an empty steps list.
5. Maximum {self.max_steps} steps.
"""

        response = generate_text(prompt)

        try:
            json_match = re.search(
                r"\{.*\}",
                response,
                re.DOTALL,
            )

            if not json_match:
                return []

            data = json.loads(json_match.group(0))

            steps = []

            for item in data.get("steps", [])[:self.max_steps]:

                tool_name = item.get("tool")

                if tool_name not in self.tools:
                    continue

                arguments = item.get("arguments", {})

                if not isinstance(arguments, dict):
                    arguments = {}

                steps.append(
                    AgentStep(
                        tool=tool_name,
                        arguments=arguments,
                    )
                )

            return steps

        except Exception as exc:
            print(f"[HIRA Agent] Planning error: {exc}")
            return []

    # ---------------------------------------------------------
    # TOOL EXECUTION
    # ---------------------------------------------------------

    def execute_tool(
        self,
        step: AgentStep,
        confirmation_callback: Optional[Callable] = None,
    ):

        tool = self.tools.get(step.tool)

        if not tool:
            return {
                "success": False,
                "error": f"Tool '{step.tool}' does not exist.",
            }

        # Dangerous actions require confirmation.
        if tool.dangerous:

            if confirmation_callback is None:
                return {
                    "success": False,
                    "error": (
                        f"Tool '{tool.name}' requires confirmation."
                    ),
                }

            approved = confirmation_callback(
                tool.name,
                step.arguments,
            )

            if not approved:
                return {
                    "success": False,
                    "error": "User denied the action.",
                }

        try:

            result = tool.function(**step.arguments)

            return {
                "success": True,
                "tool": tool.name,
                "result": result,
            }

        except Exception as exc:

            print(
                f"[HIRA Agent] Tool '{tool.name}' failed: {exc}"
            )

            return {
                "success": False,
                "tool": tool.name,
                "error": str(exc),
            }

    # ---------------------------------------------------------
    # FINAL RESPONSE
    # ---------------------------------------------------------

    def generate_final_response(
        self,
        user_request: str,
        execution_results: List[Dict[str, Any]],
    ):

        prompt = f"""
You are HIRA, a helpful Windows AI assistant.

Original request:

{user_request}

Actions executed:

{json.dumps(execution_results, indent=2, default=str)}

Give the user a concise natural-language response.

Rules:

- Do not mention internal tool names.
- Do not claim an action succeeded if it failed.
- Mention important results.
- If something failed, explain it clearly.
"""

        return generate_text(prompt)

    # ---------------------------------------------------------
    # MAIN AGENT LOOP
    # ---------------------------------------------------------

    def run(
        self,
        user_request: str,
        confirmation_callback: Optional[Callable] = None,
    ):

        print("\n[HIRA Agent] Thinking...")

        plan = self.create_plan(user_request)

        # No tools required.
        if not plan:

            return generate_text(user_request)

        print("\n[HIRA Agent] Plan:")

        for index, step in enumerate(plan, start=1):

            print(
                f"{index}. {step.tool} "
                f"{step.arguments}"
            )

        results = []

        for step in plan:

            print(
                f"\n[HIRA Agent] Executing: "
                f"{step.tool}"
            )

            result = self.execute_tool(
                step,
                confirmation_callback,
            )

            results.append(result)

            # Stop if a tool failed.
            if not result.get("success"):

                print(
                    f"[HIRA Agent] Step failed: "
                    f"{result.get('error')}"
                )

                break

        return self.generate_final_response(
            user_request,
            results,
        )