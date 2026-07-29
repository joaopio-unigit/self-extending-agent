# Self-Extending Agent

A self-extending agent is an experimental project that explores how an agent can grow its own capabilities at runtime, using the Model Context Protocol as its tool execution layer.

## What this repository contains

This repository includes two core pieces:

- an MCP client that coordinates the interaction between the user, an LLM, and available MCP servers
- a base MCP server that provides fundamental filesystem capabilities such as creating, reading, and deleting files, and running terminal commands

## Example included in this branch

This branch includes a concrete example of the self-extension workflow in action. The full interaction is recorded in `evo/output.txt`, where the agent starts without weather or exchange-rate capabilities, then creates and connects new MCP servers to fulfill the user's requests.

The example shows how the agent can:

- detect that a needed capability is missing
- create a new MCP server file
- connect that server at runtime
- immediately use the newly available tools

In this example, the agent generated `evo/weather_server.py` and `evo/exchange_rate_server.py` when asked to perform actions that were not initially supported.

A few excerpts from `evo/output.txt` show the interaction clearly:

```text
Query: What's the weather like in Lisbon?
[Calling tool 'create_file' from server 'evo_server']
[Native tool 'connect_to_server': Successfully connected to server 'weather'. Its tools are now available.]
Created weather_server.py, connected weather server, called get_weather for Lisbon.
```

```text
Query: Can you get the exchange rate from EUR to USD?
[Calling tool 'create_file' from server 'evo_server']
[Native tool 'connect_to_server': Successfully connected to server 'exchange_rate'. Its tools are now available.]
Created exchange_rate_server.py, connected it, called get_exchange_rate(EUR, USD).
```

## What is self-extending?

The agent is not limited to a fixed toolset. When a task requires a capability it does not have, it creates a new MCP server file, connects it at runtime, and starts using it immediately — all within the same session, without restarting.

The base server provides general-purpose tools that make this possible:

- `create_file` — create or update files
- `read_file` — read file contents
- `delete_file` — delete files
- `run_command` — execute shell commands

These are the hands the agent uses to build its own new tools.

## How it works

The self-extension capability lives in the client, not in the base server. Three things make it work.

**The system prompt** tells the agent it can extend itself and gives it an explicit workflow: identify a missing capability, install any required dependencies, write a new MCP server script, connect it, and use it. Without this, the agent would not know the mechanism exists.

**The native `connect_to_server` tool** is injected directly into the agent's available toolset on every API call. It lets the agent connect a newly created server to the client at runtime, making its tools immediately available:

```python
NATIVE_CONNECT_TOOL = {
    "name": "connect_to_server",
    "description": (
        "Connect a new MCP server to this client at runtime. "
        "Use this after creating a new server script file to make its tools immediately available. "
        "The server_name should be a short identifier (e.g. 'smart_home'). "
        "The server_script_path must be the absolute or relative path to the .py or .js file."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "server_name": {
                "type": "string",
                "description": "Short unique identifier for this server (e.g. 'smart_home')"
            },
            "server_script_path": {
                "type": "string",
                "description": "Path to the server script (.py or .js)"
            }
        },
        "required": ["server_name", "server_script_path"]
    }
}
```

**The hot-reload mechanism** watches existing server scripts for changes using `watchdog`. If a connected server file is modified on disk, the client marks it as changed and reloads it before the next query — no restart required:

```python
self.observer = Observer()
self.observer.start()
...
self.observer.schedule(handler, watch_dir, recursive=False)
```

This means the agent can also modify an already-connected server to add or change tools, and those changes are picked up automatically before the next interaction.

## The role of MCP

MCP is the tool execution layer — the protocol that lets the agent call code and receive results. It is not what makes the agent self-extending. The protocol itself is static and unchanged throughout a session.

What makes the agent self-extending is what sits on top of MCP: the system prompt, the native `connect_to_server` tool, and the hot-reload logic. These are client-side mechanisms that give the agent both the knowledge and the means to grow its own toolset on demand.

## Why this project exists

This project explores how an agent can extend its own capabilities dynamically through code generation and runtime integration, using MCP as the execution layer. It is intended for learning and experimentation rather than production deployment.