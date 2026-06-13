"""Plotly 环形评分图组件。"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go


_COLORS = {
    "keyword": "#4A90D9",
    "star": "#5DAE8B",
    "quant": "#D4956A",
    "track": "rgba(61, 56, 51, 0.10)",
    "center_text": "#2C2420",
    "center_sub": "#8C8279",
}


def render_score_ring(
    overall_score: float,
    keyword_score: int,
    star_score: int,
    quant_score: int,
) -> None:
    """在 Streamlit 中渲染环形评分图。"""
    weights = [40, 30, 30]
    scores = [keyword_score, star_score, quant_score]
    labels = ["关键词匹配", "STAR 结构", "量化表达"]
    colors = [_COLORS["keyword"], _COLORS["star"], _COLORS["quant"]]

    # 各维度按权重折算后的弧长，直观展示三维贡献
    segment_values = [max(0.1, s * w / 100) for s, w in zip(scores, weights)]
    hover_texts = [
        f"{label}<br>得分：{score} 分<br>权重：{weight}%"
        for label, score, weight in zip(labels, scores, weights)
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Pie(
            values=weights,
            hole=0.72,
            sort=False,
            direction="clockwise",
            marker={"colors": [_COLORS["track"]] * 3, "line": {"width": 0}},
            textinfo="none",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Pie(
            values=segment_values,
            hole=0.72,
            sort=False,
            direction="clockwise",
            marker={
                "colors": colors,
                "line": {"color": "#F7F3EF", "width": 2},
            },
            textinfo="none",
            hovertext=hover_texts,
            hoverinfo="text",
            showlegend=False,
        )
    )

    display_score = int(round(overall_score))

    fig.update_layout(
        height=260,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[
            dict(
                text=(
                    f"<span style='font-size:36px;font-weight:700;color:#2C2420'>"
                    f"{display_score}</span>"
                    f"<span style='font-size:14px;color:#8C8279'>/100</span>"
                ),
                x=0.5,
                y=0.55,
                showarrow=False,
            ),
            dict(
                text="综合匹配",
                x=0.5,
                y=0.38,
                font=dict(size=13, color=_COLORS["center_sub"], family="PingFang SC, sans-serif"),
                showarrow=False,
            ),
        ],
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_quality_ring(
    overall_score: float,
    star_score: int,
    quant_score: int,
    expression_score: int,
) -> None:
    """简历质量报告的环形图（绿=STAR 橙=量化 蓝=规范）。"""
    weights = [40, 30, 30]
    scores = [star_score, quant_score, expression_score]
    labels = ["STAR 结构", "量化表达", "表达规范"]
    colors = [_COLORS["star"], _COLORS["quant"], _COLORS["keyword"]]

    segment_values = [max(0.1, s * w / 100) for s, w in zip(scores, weights)]
    hover_texts = [
        f"{label}<br>得分：{score} 分<br>权重：{weight}%"
        for label, score, weight in zip(labels, scores, weights)
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Pie(
            values=weights,
            hole=0.72,
            sort=False,
            direction="clockwise",
            marker={"colors": [_COLORS["track"]] * 3, "line": {"width": 0}},
            textinfo="none",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Pie(
            values=segment_values,
            hole=0.72,
            sort=False,
            direction="clockwise",
            marker={
                "colors": colors,
                "line": {"color": "#F7F3EF", "width": 2},
            },
            textinfo="none",
            hovertext=hover_texts,
            hoverinfo="text",
            showlegend=False,
        )
    )

    display_score = int(round(overall_score))

    fig.update_layout(
        height=260,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[
            dict(
                text=(
                    f"<span style='font-size:36px;font-weight:700;color:#2C2420'>"
                    f"{display_score}</span>"
                    f"<span style='font-size:14px;color:#8C8279'>/100</span>"
                ),
                x=0.5,
                y=0.55,
                showarrow=False,
            ),
            dict(
                text="简历质量",
                x=0.5,
                y=0.38,
                font=dict(size=13, color=_COLORS["center_sub"], family="PingFang SC, sans-serif"),
                showarrow=False,
            ),
        ],
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
