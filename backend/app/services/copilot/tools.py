"""Tool definitions for the AI copilot.

Server-side tools are executed on the backend and return data.
Client-side tools are emitted as SSE action events to the frontend.
"""

CLIENT_SIDE_TOOLS = {"render_panel", "close_panel", "navigate", "patch_store"}


def get_tool_definitions() -> list[dict]:
    """Return OpenAI function calling definitions for all server-side tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": "fetch_conversations",
                "description": "Fetch conversations in the workspace, optionally filtered.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "object",
                            "description": "Optional filters: escalated (bool), chatbot_id (str), limit (int, default 20)",
                            "properties": {
                                "escalated": {"type": "boolean"},
                                "chatbot_id": {"type": "string"},
                                "limit": {"type": "integer"},
                            },
                        }
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_conversation",
                "description": "Fetch a single conversation with all its messages.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "conversation_id": {"type": "string", "description": "UUID of the conversation"}
                    },
                    "required": ["conversation_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_chatbots",
                "description": "List all chatbots in the workspace.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_chatbot",
                "description": "Fetch a single chatbot's full config.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chatbot_id": {"type": "string", "description": "UUID of the chatbot"}
                    },
                    "required": ["chatbot_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_metrics",
                "description": "Fetch dashboard KPI metrics for the workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "enum": ["7d", "30d"],
                            "description": "Time period for metrics",
                        }
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_credits",
                "description": "Fetch credit balance and usage for the workspace.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_documents",
                "description": "List knowledge base documents for a chatbot.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chatbot_id": {"type": "string", "description": "UUID of the chatbot"}
                    },
                    "required": ["chatbot_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_actions",
                "description": "List configured actions for a chatbot.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chatbot_id": {"type": "string", "description": "UUID of the chatbot"}
                    },
                    "required": ["chatbot_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_chatbot",
                "description": "Update chatbot fields. Only include fields you want to change.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chatbot_id": {"type": "string"},
                        "fields": {
                            "type": "object",
                            "description": "Partial chatbot fields to update (name, system_prompt, tone, confidence_threshold, etc.)",
                        },
                    },
                    "required": ["chatbot_id", "fields"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_chatbot",
                "description": (
                    "Create a new chatbot silently (no UI wizard). "
                    "IMPORTANT: When the user asks to create a chatbot interactively or mentions a URL to crawl, "
                    "prefer the navigate tool with route='/chatbots/new?url=<url>&name=<name>' so the user "
                    "sees the visual setup wizard with crawl progress. "
                    "Only use this tool for fully automated/headless creation."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "url": {"type": "string", "description": "Optional URL to crawl for knowledge"},
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_chatbot",
                "description": "Delete a chatbot permanently.",
                "parameters": {
                    "type": "object",
                    "properties": {"chatbot_id": {"type": "string"}},
                    "required": ["chatbot_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_crawl",
                "description": "Trigger a web crawl for a chatbot's knowledge base.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chatbot_id": {"type": "string"},
                        "url": {"type": "string", "description": "URL to crawl"},
                    },
                    "required": ["chatbot_id", "url"],
                },
            },
        },
        # Client-side tools are NOT included here — they are emitted as SSE action events
    ]


def get_client_side_tool_definitions() -> list[dict]:
    """Return definitions for client-side tools (for LLM context only — not executed on backend)."""
    return [
        {
            "type": "function",
            "function": {
                "name": "render_panel",
                "description": "Render a UI component in the side panel next to the chat.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "component": {
                            "type": "string",
                            "enum": [
                                "ConversationList",
                                "ConversationDetail",
                                "MetricsDashboard",
                                "ChatbotList",
                                "DocumentList",
                                "ActionsList",
                                "CreditBalance",
                                "LLMSettingsPanel",
                                "PersonaSettingsPanel",
                                "WidgetSettingsPanel",
                                "CrawlStatusPanel",
                            ],
                        },
                        "props": {"type": "object", "description": "Props to pass to the component"},
                    },
                    "required": ["component"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "close_panel",
                "description": "Dismiss the component panel.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "navigate",
                "description": (
                    "Navigate to a dashboard route. "
                    "Use '/chatbots/new?url=<encoded_url>&name=<encoded_name>' to open the chatbot "
                    "creation wizard with pre-filled values and auto-start the crawl."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"route": {"type": "string", "description": "Next.js route path, may include query params"}},
                    "required": ["route"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "patch_store",
                "description": "Optimistically update a Zustand store.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "store": {"type": "string"},
                        "data": {"type": "object"},
                    },
                    "required": ["store", "data"],
                },
            },
        },
    ]
