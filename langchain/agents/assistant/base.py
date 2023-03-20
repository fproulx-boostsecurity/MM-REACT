"""An agent designed to hold a conversation in addition to using tools."""
from __future__ import annotations

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
        return "<|im_sep|>Assistant\n"

    @property
    def llm_prefix(self) -> str:
        """Prefix to append the llm call with."""
        return "<|im_sep|>AI\n"

    @property
    def _stop(self) -> List[str]:
        return ["<|im_end|>", "\nEXAMPLE", "\nNEW INPUT", "<|im_sep|>Assistant"]

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
        return "<|im_end|>"

    @staticmethod
    def _fix_chatgpt(text: str) -> str:
        text = text.replace("<|im_sep|>AI\n", "")
        lines = text.split("\n")
        new_lines = []
        for l in lines:
            term = "Is there anything else I"
            idx = text.find(term)
            if idx >= 0:
                l = l[:idx]
            if not l:
                continue
            new_lines.append(l)
        text = "\n".join(new_lines)

        return text
    
    def _fix_text(self, text: str) -> str:
        text = self._fix_chatgpt(text)
        if "Assistant, " in text:
            return text
        return f"{text}\n{self.llm_prefix}"

    def _extract_tool_and_input(self, llm_output: str, tries=0) -> Optional[Tuple[str, str]]:
        # TODO: this should be a separate llm as a tool to decide the correct tool(s) here
        llm_output = self._fix_chatgpt(llm_output)
        photo_editing = "photo edit" in llm_output or "image edit" in llm_output
        is_table = " table" in llm_output
        cmd_idx = llm_output.rfind("Assistant,")
        if cmd_idx >= 0:
            cmd = llm_output[cmd_idx + len("Assistant,"):].strip()
            if photo_editing:
                return "Photo Editing", cmd
            search_idx = cmd.lower().find("bing search")
            if search_idx >= 0:
                 action_input = cmd[search_idx + len("bing serach") + 1:]
                 return "Bing Search", action_input
            cmd_idx = cmd.rfind(" ")
            action_input = cmd[cmd_idx + 1:].strip()
            if "/" not in action_input and "http" not in action_input:
                if action_input.endswith("?"):
                    return "Bing Search" , action_input       
                return self.finish_tool_name, "Please provide the image url at the end."
            if action_input.endswith((".", "?")):
                action_input = action_input[:-1].strip()
            if not action_input:
                return self.finish_tool_name, "Please provide the image url at the end."
            cmd = cmd[:cmd_idx + 1].lower()
            if "receipt" in cmd:
                action = "Receipt Understanding"
            elif "business card" in cmd:
                action = "Business Card Understanding"
            elif "ocr" in cmd:
                if is_table:
                    action = "Layout Understanding"
                else:
                    action = "OCR Understanding"
            elif "celebrit" in cmd:
                action = "Celebrity Understanding"
            elif "landmark" in cmd:
                action = "Bing Search"
            elif "brand" in cmd:
                action = "Bing Search"
            else:
                if "objects" in cmd:
                    action = "Image Understanding"
                else:
                    action = self.finish_tool_name
            return action, action_input
        action_log = llm_output.strip()
        if tries == 1 or not action_log:
            return self.finish_tool_name, action_log

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
