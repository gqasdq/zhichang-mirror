from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from loguru import logger


class PromptManager:
    """Jinja2模板管理器。"""

    def __init__(self, prompts_root: str = "./prompts") -> None:
        self.prompts_root = Path(prompts_root)
        self.prompts_root.mkdir(parents=True, exist_ok=True)
        self._env = Environment(
            loader=FileSystemLoader(str(self.prompts_root)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def exists(self, template_path: str) -> bool:
        try:
            self._env.get_template(template_path)
            return True
        except TemplateNotFound:
            return False

    def load(self, template_path: str) -> str:
        """加载模板原文。"""
        template = self._env.get_template(template_path)
        # 源码通过loader读取，避免重复实现文件读取逻辑
        source, _, _ = self._env.loader.get_source(self._env, template.name)  # type: ignore[arg-type]
        return source

    def render(self, template_path: str, **kwargs: Any) -> str:
        """渲染模板。"""
        template = self._env.get_template(template_path)
        return template.render(**kwargs)

    def render_dynamic(
        self,
        template_path: str,
        query: str = "",
        module: str = "",
        **kwargs: Any,
    ) -> str:
        """
        动态渲染：根据 query 检索最相似的 Few-shot 样例，注入模板。
        用于基于反馈的 Prompt 动态优化。
        """
        from core.few_shot_retriever import retrieve_few_shot_text

        few_shot_text = ""
        if query.strip():
            few_shot_text = retrieve_few_shot_text(query, module=module, top_k=3)
            if few_shot_text != "（暂无相似优质样例）":
                logger.info(
                    "[prompt_manager] injected few-shot for module=%s",
                    module or "any",
                )

        kwargs.setdefault("few_shot_examples", few_shot_text)
        return self.render(template_path, **kwargs)


prompt_manager = PromptManager()
