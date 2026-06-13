from typing import Dict, Any, Optional, Iterator
from dataclasses import dataclass, field
from loguru import logger

from agents.emotion.detector import emotion_detector, EmotionDetectionResult
from agents.emotion.anxiety_agent import anxiety_agent, AnxietyResponse
from agents.emotion.grievance_agent import grievance_agent
from agents.emotion.frustration_agent import frustration_agent
from agents.emotion.empathic_synthesizer import empathic_synthesizer, SynthesizedResponse
from agents.emotion.score_utils import build_emotion_score_strategy_hint
from core.constants import API_EMOTION_FAST_TIMEOUT

from data.database import get_db
from data.models import ChatSession, Conversation, Analysis


@dataclass
class EmotionPreparedContext:
    """情绪分析前置步骤结果，供流式输出使用。"""

    user_input: str
    detection: Dict[str, Any]
    emotion_type: str
    agent_output_text: str
    score_hint: str
    rag_status: Dict[str, Any]
    reasoning_chain: Dict[str, str] = field(default_factory=dict)


class EmotionService:
    """情绪急救站服务"""

    EMOTION_AGENTS = {
        "焦虑": anxiety_agent,
        "委屈": grievance_agent,
        "挫败": frustration_agent
    }

    @staticmethod
    def _extract_reasoning(agent_response: Any) -> Dict[str, str]:
        if hasattr(agent_response, "reasoning_chain"):
            chain = agent_response.reasoning_chain
            if isinstance(chain, dict):
                return chain
        if hasattr(agent_response, "model_dump"):
            data = agent_response.model_dump()
            chain = data.get("reasoning_chain")
            if isinstance(chain, dict):
                return chain
        return {}

    @staticmethod
    def _search_rag_context(user_input: str, top_k: int = 3) -> tuple[list[str], Dict[str, Any]]:
        """混合检索 RAG 上下文，优先优质 Few-shot 样例；embedding 不可用时关键词降级。"""
        try:
            from vectorstore.safe_search import hybrid_search

            results = hybrid_search(user_input, top_k=top_k * 2, include_pending=True)

            few_shot = [
                r for r in results
                if (r.get("metadata") or {}).get("type") == "few_shot"
                or float((r.get("metadata") or {}).get("quality_score", 0)) >= 0.8
            ]
            if few_shot:
                picked = few_shot[:top_k]
                rag_label = "优质回复样例"
            else:
                picked = [r for r in results if r.get("score", 0) > 0.01][:top_k]
                rag_label = "相似案例"

            similar_stories = [r["text"] for r in picked if r.get("text")]
            rag_status = {
                "mode": "hybrid_few_shot" if few_shot else ("hybrid_rag" if similar_stories else "no_rag"),
                "reason": "few_shot" if few_shot else ("ok" if similar_stories else "no_match"),
                "retrieved": len(similar_stories),
                "rag_label": rag_label,
            }
            return similar_stories, rag_status
        except Exception:
            return [], {
                "mode": "no_rag",
                "reason": "unavailable",
                "retrieved": 0,
                "rag_label": "相似案例",
            }

    @staticmethod
    def _format_few_shot_for_prompt(similar_stories: list[str]) -> str:
        """将检索到的 Few-Shot 样例格式化为 Prompt 文本。"""
        if not similar_stories:
            return "（暂无相似优质回复样例）"

        lines = [
            "以下是与你情况相似的过往优质回复，请参考其风格和结构，但针对当前用户输入生成新的回复：\n"
        ]
        for i, story in enumerate(similar_stories, 1):
            text = str(story).strip()
            if text:
                lines.append(f"### 样例{i}：\n{text}\n")
        return "\n".join(lines) if len(lines) > 1 else "（暂无相似优质回复样例）"

    @staticmethod
    def _inject_few_shot_into_prompt(prompt: str, similar_stories: list[str]) -> str:
        """把 Few-Shot 样例注入含占位符的 Prompt 文本。"""
        from agents.emotion.prompt_utils import inject_few_shot_examples

        few_shot_text = EmotionService._format_few_shot_for_prompt(similar_stories)
        return inject_few_shot_examples(prompt, few_shot_text)

    def record_positive_feedback(
        self,
        user_input: str,
        assistant_output: str,
        emotion_type: str = "",
    ) -> bool:
        """用户点赞时，将优质对话写入 pending 队列（不即时建索引，避免加载 embedding 模型）。"""
        try:
            import re
            from vectorstore.incremental import IncrementalVectorStore

            tokens = re.findall(r"[\u4e00-\u9fa5]{2,}|\w+", user_input.lower())
            text = f"【优质共情样例】用户：{user_input}\n小镜：{assistant_output}"
            metadata = {
                "type": "few_shot",
                "quality_score": 0.9,
                "emotion": emotion_type,
                "keywords": tokens[:12],
            }
            store = IncrementalVectorStore()
            store.queue_add(text, metadata)
            logger.info("[emotion] recorded positive feedback to pending queue")
            return True
        except Exception as exc:
            logger.warning("[emotion] feedback storage failed: %s", exc)
            return False

    @staticmethod
    def _agent_output_as_text(agent_response: Any) -> str:
        if hasattr(agent_response, "model_dump"):
            data = agent_response.model_dump()
            parts: list[str] = []
            for key, value in data.items():
                if key == "actions" and isinstance(value, list):
                    if value:
                        parts.append("行动建议：" + "；".join(str(v) for v in value if v))
                elif isinstance(value, str) and value.strip():
                    parts.append(value.strip())
            if parts:
                return "\n".join(parts)
        return str(agent_response)

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id

    def process(
        self,
        user_input: str,
        user_id: Optional[str] = None,
        emotion_start_score: Optional[int] = None,
    ) -> Dict[str, Any]:
        """兼容UI调用入口，内部复用 analyze。"""
        if user_id and not self.session_id:
            self.session_id = f"emotion_{user_id}"
        return self.analyze(user_input, emotion_start_score=emotion_start_score)

    def fast_respond(
        self,
        user_input: str,
        emotion_hint: str = "平稳",
        emotion_start_score: Optional[int] = None,
        conversation_history: Optional[list[dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        情绪急救站快速路径：单次 emotion_fast LLM 调用。
        不触发 RAG / embedding 模型，避免 HuggingFace 下载阻塞。
        conversation_history: 连续对话模式下传入 [{role, content}, ...]
        """
        from agents.emotion.parse_utils import extract_natural_response
        from core.model_router import model_router
        from core.privacy_filter import sanitize_chat_for_api

        sanitized = (user_input or "").strip()
        if not sanitized:
            raise ValueError("输入为空")

        safe_input = sanitize_chat_for_api(sanitized)
        emotion_type = emotion_hint or "平稳"
        score_hint = ""
        if emotion_start_score is not None:
            score_hint = build_emotion_score_strategy_hint(emotion_start_score)

        rag_status: Dict[str, Any] = {
            "mode": "skipped_fast",
            "reason": "no_rag_on_fast_path",
            "retrieved": 0,
            "rag_label": "相似案例",
        }

        system_prompt = (
            "你是「职场镜子」里的小镜，像半夜会接电话的朋友，不是客服，也不是心理咨询师。\n"
            "只做情绪陪伴：接住感受、温柔回应。不评判、不给简历建议、不列行动清单。\n\n"
            "说话方式：\n"
            "- 禁止只复述用户原话（如「投简历确实挺累」这类回声式回应）\n"
            "- 禁止「理解您的感受」「确实不容易」等空洞套话\n"
            "- 第一句接住情绪；第二句看见对方的努力或处境；第三句轻陪伴、不催促\n"
            "- 口语化，像朋友发微信，2–3 段，每段 1–2 句，共约 80–180 字\n"
            "- 只输出纯文本，不要 JSON"
        )
        if score_hint:
            system_prompt = f"{system_prompt}\n\n{score_hint}"
        if conversation_history:
            system_prompt += (
                "\n\n这是连续对话模式：用户可能接着上一句继续说。"
                "请结合前文语境回应，但不要重复之前说过的话。"
            )

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for turn in conversation_history or []:
            role = turn.get("role", "")
            content = (turn.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        user_prompt = (
            f"用户说：「{safe_input}」\n"
            f"情绪倾向：{emotion_type}\n\n"
            "写一段有温度的陪伴回复。不要重复用户说过的话，要让他们感到被看见、被接住。"
        )
        messages.append({"role": "user", "content": user_prompt})

        if conversation_history:
            response = model_router.call_with_messages(
                messages=messages,
                task_type="emotion_fast",
                max_tokens=320,
                temperature=0.88,
                timeout=API_EMOTION_FAST_TIMEOUT,
            )
        else:
            response = model_router.call(
                prompt=user_prompt,
                task_type="emotion_fast",
                system_prompt=system_prompt,
                max_tokens=320,
                temperature=0.88,
                timeout=API_EMOTION_FAST_TIMEOUT,
            )
        content = extract_natural_response(response)
        if not content.strip():
            raise RuntimeError("AI 回复为空")

        return {
            "detection": {"primary_emotion": emotion_type},
            "response": {
                "content": content,
                "emotion_type": emotion_type,
                "key_suggestions": [],
            },
            "reasoning_chain": {},
            "rag_status": rag_status,
        }

    def prepare_for_response(
        self,
        user_input: str,
        emotion_start_score: Optional[int] = None,
    ) -> EmotionPreparedContext:
        """完成检测与专业 Agent 分析，为流式整合回复做准备。"""
        logger.info(f"EmotionService: Preparing input length={len(user_input)}")

        score_hint = ""
        if emotion_start_score is not None:
            score_hint = build_emotion_score_strategy_hint(emotion_start_score)

        detection_result = emotion_detector.detect(user_input)
        self._save_detection(detection_result)

        similar_stories, rag_status = self._search_rag_context(user_input, top_k=3)
        rag_label = str(rag_status.get("rag_label", "相似案例"))
        few_shot_text = self._format_few_shot_for_prompt(similar_stories)

        emotion_type = detection_result.primary_emotion
        agent_system_prompt = "你是一位温暖、专业的职场心理咨询师。"
        if score_hint:
            agent_system_prompt = f"{agent_system_prompt}\n\n{score_hint}"

        rag_context = "\n---\n".join(similar_stories) if similar_stories else ""
        if emotion_type in self.EMOTION_AGENTS:
            agent = self.EMOTION_AGENTS[emotion_type]
            agent_response = agent.respond(
                user_input=user_input,
                emotion_state=detection_result.model_dump(),
                rag_context=rag_context,
                system_prompt_override=agent_system_prompt,
                rag_label=rag_label,
                few_shot_examples=few_shot_text,
            )
        else:
            agent_response = anxiety_agent.respond(
                user_input=user_input,
                emotion_state=detection_result.model_dump(),
                rag_context=rag_context,
                system_prompt_override=agent_system_prompt,
                rag_label=rag_label,
                few_shot_examples=few_shot_text,
            )

        reasoning_chain = self._extract_reasoning(agent_response)

        return EmotionPreparedContext(
            user_input=user_input,
            detection=detection_result.model_dump(),
            emotion_type=emotion_type,
            agent_output_text=self._agent_output_as_text(agent_response),
            score_hint=score_hint,
            rag_status=rag_status,
            reasoning_chain=reasoning_chain,
        )

    def iter_final_response(self, prepared: EmotionPreparedContext) -> Iterator[str]:
        """流式输出最终共情回复。"""
        yield from empathic_synthesizer.synthesize_stream(
            user_input=prepared.user_input,
            emotion_detection=prepared.detection,
            agent_output=prepared.agent_output_text,
            emotion_type=prepared.emotion_type,
            score_strategy_hint=prepared.score_hint,
        )

    def finalize_streamed_response(
        self,
        prepared: EmotionPreparedContext,
        raw_content: str,
    ) -> Dict[str, Any]:
        """流式结束后保存记录并返回结构化结果。"""
        from agents.emotion.parse_utils import extract_natural_response

        content = extract_natural_response(raw_content)
        synthesized = SynthesizedResponse(
            content=content,
            emotion_type=prepared.emotion_type,
            key_suggestions=[],
        )
        self._save_conversation(prepared.user_input, content)
        return {
            "detection": prepared.detection,
            "response": synthesized.model_dump(),
            "rag_status": prepared.rag_status,
            "reasoning_chain": prepared.reasoning_chain,
        }

    def analyze(
        self,
        user_input: str,
        emotion_start_score: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        分析用户情绪并提供响应

        Args:
            user_input: 用户输入
            emotion_start_score: 用户自评情绪温度计分数（1-10）

        Returns:
            Dict: 包含检测结果和响应的字典
        """
        logger.info(f"EmotionService: Analyzing input length={len(user_input)}")

        score_hint = ""
        if emotion_start_score is not None:
            score_hint = build_emotion_score_strategy_hint(emotion_start_score)

        # Step 1: 情绪检测（分数仅影响回应策略，不参与检测 prompt，避免重复加长）
        detection_result = emotion_detector.detect(user_input)

        # 保存检测结果
        self._save_detection(detection_result)

        # Step 1.5: 混合检索 RAG
        similar_stories, rag_status = self._search_rag_context(user_input, top_k=3)
        rag_label = str(rag_status.get("rag_label", "相似案例"))
        few_shot_text = self._format_few_shot_for_prompt(similar_stories)

        # Step 2: 根据情绪类型调用对应Agent（含 Chain-of-Empathy）
        emotion_type = detection_result.primary_emotion
        agent_system_prompt = "你是一位温暖、专业的职场心理咨询师。"
        if score_hint:
            agent_system_prompt = f"{agent_system_prompt}\n\n{score_hint}"

        rag_context = "\n---\n".join(similar_stories) if similar_stories else ""
        if emotion_type in self.EMOTION_AGENTS:
            agent = self.EMOTION_AGENTS[emotion_type]
            agent_response = agent.respond(
                user_input=user_input,
                emotion_state=detection_result.model_dump(),
                rag_context=rag_context,
                system_prompt_override=agent_system_prompt,
                rag_label=rag_label,
                few_shot_examples=few_shot_text,
            )
        else:
            agent_response = anxiety_agent.respond(
                user_input=user_input,
                emotion_state=detection_result.model_dump(),
                rag_context=rag_context,
                system_prompt_override=agent_system_prompt,
                rag_label=rag_label,
                few_shot_examples=few_shot_text,
            )

        reasoning_chain = self._extract_reasoning(agent_response)
        agent_output_text = self._agent_output_as_text(agent_response)

        # Step 3: 共情整合
        synthesized = empathic_synthesizer.synthesize(
            user_input=user_input,
            emotion_detection=detection_result.model_dump(),
            agent_output=agent_output_text,
            emotion_type=emotion_type,
            score_strategy_hint=score_hint,
        )

        self._save_conversation(user_input, synthesized.content)

        return {
            "detection": detection_result.model_dump(),
            "response": synthesized.model_dump(),
            "rag_status": rag_status,
            "reasoning_chain": reasoning_chain,
        }

    def _save_detection(self, detection: EmotionDetectionResult):
        """保存情绪检测结果"""
        try:
            with get_db() as db:
                # 查找或创建会话
                session = db.query(ChatSession).filter(
                    ChatSession.session_id == self.session_id
                ).first()

                if not session:
                    # 创建新会话
                    from data.models import User
                    user = db.query(User).filter(
                        User.user_id == "default"
                    ).first()

                    if not user:
                        user = User(user_id="default")
                        db.add(user)
                        db.flush()

                    session = ChatSession(
                        session_id=self.session_id or f"session_{hash(str(__import__('time').time()))}",
                        user_id=user.id,
                        module_type="emotion"
                    )
                    db.add(session)
                    db.flush()

                # 保存分析结果
                analysis = Analysis(
                    session_id=session.id,
                    analysis_type="emotion_detection",
                    input_data={"primary_emotion": detection.primary_emotion},
                    output_data=detection.model_dump(),
                    score=detection.confidence
                )
                db.add(analysis)

        except Exception as e:
            logger.error(f"Failed to save detection: {e}")

    def _save_conversation(self, user_input: str, assistant_output: str):
        """保存对话记录"""
        try:
            with get_db() as db:
                session = db.query(ChatSession).filter(
                    ChatSession.session_id == self.session_id
                ).first()

                if session:
                    # 用户消息
                    user_msg = Conversation(
                        session_id=session.id,
                        role="user",
                        content=user_input
                    )
                    db.add(user_msg)

                    # 助手回复
                    assistant_msg = Conversation(
                        session_id=session.id,
                        role="assistant",
                        content=assistant_output
                    )
                    db.add(assistant_msg)

        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")


# 全局实例工厂
def get_emotion_service(session_id: Optional[str] = None) -> EmotionService:
    return EmotionService(session_id)
