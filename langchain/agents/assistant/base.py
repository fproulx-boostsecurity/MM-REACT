"""An agent designed to hold a conversation in addition to using tools."""
from __future__ import annotations

import re
from typing import Any, List, Optional, Sequence, Tuple

from langchain.agents.agent import Agent
from langchain.agents.assistant.prompt import PREFIX, SUFFIX
from langchain.callbacks.base import BaseCallbackManager
from langchain.chains import LLMChain
from langchain.llms import BaseLLM
from langchain.prompts import PromptTemplate
from langchain.tools.base import BaseTool


class AssistantAgent(Agent):
    """An agent designed to hold a conversation in addition to an specialized assistant tool."""

    ai_prefix: str = "AI"

    @property
    def _agent_type(self) -> str:
        """Return Identifier of agent type."""
        return "conversational-assistant"

    @property
    def observation_prefix(self) -> str:
        """Prefix to append the observation with."""
        return "ImageAssistant: "

    @property
    def llm_prefix(self) -> str:
        """Prefix to append the llm call with."""
        return "AI:"

    @classmethod
    def create_prompt(
        cls,
        prefix: str = PREFIX,
        suffix: str = SUFFIX,
        ai_prefix: str = "AI",
        input_variables: Optional[List[str]] = None,
    ) -> PromptTemplate:
        """Create prompt in the style of the zero shot agent.

        Args:
            prefix: String to put before the list of tools.
            suffix: String to put after the list of tools.
            input_variables: List of input variables the final prompt will expect.

        Returns:
            A PromptTemplate with the template assembled from the pieces here.
        """
        template = "\n\n".join([prefix.format(ai_prefix=ai_prefix), suffix])
        if input_variables is None:
            input_variables = ["input", "chat_history", "agent_scratchpad"]
        return PromptTemplate(template=template, input_variables=input_variables)

    @property
    def finish_tool_name(self) -> str:
        """Name of the tool to use to finish the chain."""
        return self.ai_prefix

    def _extract_tool_and_input(self, llm_output: str) -> Optional[Tuple[str, str]]:
        cmd_idx = llm_output.find("ImageAssistant,")
        if cmd_idx >= 0:
            cmd = llm_output[len("ImageAssistant,"):]
            action = "Image Understanding"
            action_input = "/mnt/output/gr/DemoTest/math1.png"
            return action.strip(), action_input.strip(" ").strip('"')
        
        if f"{self.ai_prefix}:" in llm_output:
            return self.ai_prefix, llm_output.split(f"{self.ai_prefix}:")[-1].strip()
        # if the role is assumed!
        if "ImageAssistant:" in llm_output:
            return self.ai_prefix, llm_output.split("ImageAssistant:")[-1].strip()
        return self.ai_prefix, llm_output.strip()

    @classmethod
    def from_llm_and_tools(
        cls,
        llm: BaseLLM,
        tools: Sequence[BaseTool],
        callback_manager: Optional[BaseCallbackManager] = None,
        prefix: str = PREFIX,
        suffix: str = SUFFIX,
        ai_prefix: str = "AI",
        input_variables: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Agent:
        """Construct an agent from an LLM and tools."""
        cls._validate_tools(tools)
        prompt = cls.create_prompt(
            ai_prefix=ai_prefix,
            prefix=prefix,
            suffix=suffix,
            input_variables=input_variables,
        )
        llm_chain = LLMChain(
            llm=llm,
            prompt=prompt,
            callback_manager=callback_manager,
        )
        tool_names = [tool.name for tool in tools]
        return cls(
            llm_chain=llm_chain, allowed_tools=tool_names, **kwargs
        )
