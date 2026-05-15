"""Mock OpenAI-compatible LLM API server for E2E tests.

Listens on port 9000. Accepts POST /v1/chat/completions and returns canned
JSON responses that match what each prompt type expects, without hitting
any real LLM API or consuming tokens.

Detection heuristic (in priority order):
  1. System message present → LangGraph chat pipeline → sectioned JSON
  2. User message contains quiz-generator keywords → MCQ JSON (8 questions)
  3. User message contains follow-up quiz keywords → MCQ JSON
  4. User message contains relearn keywords → plain text explanation
  5. User message contains news-curation keywords → selected_indices JSON
  6. User message contains auto-title keywords → title + topic JSON
  7. Everything else → sectioned educational JSON (discussion/learn-more)
"""
from __future__ import annotations

import json
import time

from flask import Flask, jsonify, request

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Canned responses — valid JSON/text matching what each prompt type expects
# ---------------------------------------------------------------------------

_SECTIONED = json.dumps({
    "type": "sectioned",
    "intro": (
        "This is a concise educational overview covering three key areas of the topic. "
        "No prior knowledge is assumed. The sections below collectively explain "
        "the concept from foundations through to practical implications."
    ),
    "hierarchy_diagram": (
        "flowchart TD\n"
        "  ROOT[Topic Overview] --> A[Core Concept]\n"
        "  ROOT --> B[Practical Applications]\n"
        "  ROOT --> C[Advanced Considerations]"
    ),
    "sections": [
        {
            "id": "s1",
            "title": "Core Concept",
            "content": (
                "The core concept is fundamental to understanding this topic. "
                "It provides the foundation upon which all subsequent ideas rest. "
                "The key relationship is $f(x) = \\sigma(wx + b)$ in simplified form."
            ),
            "key_points": [
                "The primary mechanism operates through iterative refinement",
                "Applications span both theoretical and practical domains",
                "Trade-offs exist between speed, accuracy, and resource usage",
            ],
            "misconception": (
                "A common misconception is that this concept is more restrictive "
                "than it actually is in real-world usage."
            ),
            "learn_more_topic": "Deep dive into the core mechanism and its variants",
            "artifacts": [
                {
                    "type": "formula",
                    "latex": "f(x) = \\frac{1}{1 + e^{-x}}",
                    "caption": "The core mathematical relationship",
                },
            ],
        },
        {
            "id": "s2",
            "title": "Practical Applications",
            "content": (
                "Practical applications of this concept are widespread in industry. "
                "Understanding them bridges the gap between theory and implementation."
            ),
            "key_points": [
                "Production systems rely on this concept for reliability",
                "Performance tuning focuses on the key configurable parameters",
                "Scalability is achieved through hierarchical organisation",
            ],
            "misconception": (
                "People often think this only applies at small scale, "
                "when it is equally important in large distributed systems."
            ),
            "learn_more_topic": "Real-world case studies and performance benchmarks",
            "artifacts": [
                {
                    "type": "chart",
                    "chart_type": "bar",
                    "title": "Performance Comparison",
                    "labels": ["Approach A", "Approach B", "Approach C"],
                    "datasets": [{"label": "Score", "data": [85, 72, 91]}],
                    "caption": "Relative performance across three approaches",
                },
            ],
        },
        {
            "id": "s3",
            "title": "Advanced Considerations",
            "content": (
                "Advanced aspects reveal nuances that are not obvious at the surface level. "
                "These are critical for expert understanding and robust system design."
            ),
            "key_points": [
                "Edge cases require special handling to maintain correctness",
                "Theoretical limitations arise from the mathematical foundations",
                "Current research is actively addressing known limitations",
            ],
            "misconception": (
                "Even experienced practitioners sometimes overlook "
                "these edge cases until they encounter them in production."
            ),
            "learn_more_topic": "Limitations, edge cases, and open research problems",
            "artifacts": [],
        },
    ],
    "outro": (
        "Start with the core concept to build a solid foundation, "
        "then explore practical applications before tackling advanced considerations."
    ),
})

_AUTO_TITLE = json.dumps({
    "title": "Test Knowledge Topic",
    "topic": "educational learning concepts",
})

_MCQ = json.dumps({
    "questions": [
        {
            "id": "q_01",
            "text": (
                "What is the primary mechanism that enables efficient "
                "optimisation in gradient-based systems?"
            ),
            "options": [
                "Backpropagation through the computation graph",
                "Random weight initialisation at each step",
                "Batch normalisation without gradient signals",
                "Dropout-only regularisation during training",
            ],
            "correct": 0,
            "topic": "optimisation mechanisms",
        },
        {
            "id": "q_02",
            "text": (
                "Which property fundamentally distinguishes supervised "
                "from unsupervised learning?"
            ),
            "options": [
                "Dataset size requirements for convergence",
                "Presence of labelled training examples",
                "Total number of model parameters",
                "Required compute during inference",
            ],
            "correct": 1,
            "topic": "machine learning paradigms",
        },
        {
            "id": "q_03",
            "text": "What does the vanishing gradient problem primarily affect during training?",
            "options": [
                "Output layer activation magnitudes",
                "Batch size selection strategy",
                "Gradient signal in early network layers",
                "Dropout rate calibration",
            ],
            "correct": 2,
            "topic": "deep learning training challenges",
        },
        {
            "id": "q_04",
            "text": (
                "Which mathematical operation is central to the "
                "attention mechanism in transformers?"
            ),
            "options": [
                "Convolution with learned spatial filters",
                "Scaled dot-product between query and key matrices",
                "Recurrent hidden state propagation",
                "Max-pooling over token embeddings",
            ],
            "correct": 1,
            "topic": "transformer architecture",
        },
        {
            "id": "q_05",
            "text": "What is the key advantage of residual connections in deep networks?",
            "options": [
                "Significantly reducing trainable parameter count",
                "Enabling gradient flow through identity shortcuts",
                "Eliminating the need for batch normalisation",
                "Replacing all non-linear activation functions",
            ],
            "correct": 1,
            "topic": "residual network design",
        },
        {
            "id": "q_06",
            "text": "What term does L2 regularisation add to the loss function?",
            "options": [
                "The L1 norm of the weight vector",
                "A penalty proportional to the squared magnitude of weights",
                "Random noise scaled by the batch size",
                "A sparsity penalty on hidden activations",
            ],
            "correct": 1,
            "topic": "regularisation techniques",
        },
        {
            "id": "q_07",
            "text": "Which property does the softmax function guarantee for its output?",
            "options": [
                "All outputs are bounded between -1 and 1",
                "All outputs form a valid probability distribution summing to 1",
                "All outputs are non-negative integers",
                "The maximum output equals the maximum input",
            ],
            "correct": 1,
            "topic": "activation functions and probability",
        },
        {
            "id": "q_08",
            "text": (
                "What distinguishes the Adam optimiser from standard "
                "stochastic gradient descent?"
            ),
            "options": [
                "It requires no learning rate hyperparameter",
                "It adapts per-parameter learning rates via moment estimates",
                "It always converges to the global optimum",
                "It eliminates weight initialisation requirements",
            ],
            "correct": 1,
            "topic": "adaptive optimisation algorithms",
        },
    ]
})

_RELEARN = (
    "The correct answer accurately identifies the underlying mechanism as established "
    "by the foundational theory. The first wrong option conflates two related but distinct "
    "concepts that operate at different abstraction levels. The second wrong option describes "
    "a separate process addressing an orthogonal problem. The third option sounds plausible "
    "but misidentifies the key causal factor — it describes an effect, not a cause."
)

_NEWS_CURATION = json.dumps({
    "selected_indices": [0, 1, 2, 3, 4],
    "reason": "Leading developments in technology and artificial intelligence research",
})


# ---------------------------------------------------------------------------
# Response builder — wraps content in OpenAI chat.completion format
# ---------------------------------------------------------------------------

def _completion(content: str) -> dict:
    return {
        "id": f"chatcmpl-mock-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "mock-llm",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 200, "total_tokens": 250},
    }


def _pick_response(messages: list[dict]) -> str:
    if not messages:
        return _SECTIONED

    first = messages[0]
    role = str(first.get("role", ""))
    content = str(first.get("content", ""))

    # LangGraph pipeline always prepends a system message
    if role == "system":
        return _SECTIONED

    # Direct llm.invoke(string) calls → single user message with full prompt text
    c = content

    if "short title" in c and "topic phrase" in c:
        return _AUTO_TITLE

    if ("exactly" in c or "generate" in c) and (
        "quiz generator" in c or "multiple-choice" in c or "MCQ" in c
    ):
        return _MCQ

    if "follow-up quiz" in c or ("previous quiz" in c and "performance" in c):
        return _MCQ

    if "plain text only" in c and "sentences" in c and ("correct" in c or "explain" in c):
        return _RELEARN

    if "selected_indices" in c or ("news curator" in c and "important" in c):
        return _NEWS_CURATION

    # Discussion prompt, learn-more prompt, or anything else → sectioned
    return _SECTIONED


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "mock-llm"})


@app.post("/v1/chat/completions")
def chat_completions():
    data = request.get_json(force=True, silent=True) or {}
    messages = data.get("messages", [])
    content = _pick_response(messages)
    return jsonify(_completion(content))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
