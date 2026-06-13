from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from core.model_router import model_router
from core.privacy_filter import sanitize_resume_for_api
from core.prompt_manager import prompt_manager


class ResumeAnalysis(BaseModel):
    raw_content: str = Field(description="LLM原始分析结果")


class ResumeAnalyzer(BaseAgent):
    AGENT_NAME = "resume_analyzer"
    PROMPT_TEMPLATE = "gold_detector/analyzer_prompt.txt"

    def __init__(self):
        super().__init__(self.AGENT_NAME)

    def analyze(self, resume_text: str) -> ResumeAnalysis:
        sanitized = sanitize_resume_for_api(resume_text)
        prompt = prompt_manager.render(self.PROMPT_TEMPLATE, resume_text=sanitized)
        response = model_router.call(
            prompt=prompt,
            task_type="complex_analysis",
            system_prompt="你是一位专业的求职顾问。铁律：严禁编造！你的一切分析必须且只能基于简历原文中实际存在的内容。简历没写的经历、技能、成果，绝对不能自己编造。每条结论都要能指向简历中的具体文字。",
        )
        return ResumeAnalysis(raw_content=response)


resume_analyzer = ResumeAnalyzer()
