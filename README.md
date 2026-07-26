# Evolutionary MCP

Evolutionary MCP is an experimental project that explores how an MCP client and MCP server can grow their own capabilities over time.

## What this repository contains

This repository includes two core pieces:

- an MCP client that coordinates the interaction between the user, an LLM, and available MCP servers
- a basic MCP server that provides fundamental filesystem capabilities such as creating, reading, deleting files, and running terminal commands

## Example included in this branch

This branch includes a concrete example of the evolutionary workflow in action. The full interaction is recorded in `evo/output.txt`, where the client starts without weather or exchange-rate capabilities, then creates and connects new MCP servers to fulfill the user’s requests.

The example shows how the agent can:

- detect that a needed capability is missing
- create a new MCP server file
- connect that server at runtime
- immediately use the newly available tools

In this example, the agent generated `evo/weather_server.py` and `evo/exchange_rate_server.py` when asked to perform actions that were not initially supported.

A few excerpts from `evo/output.txt` show the interaction clearly:

```text
Query: What's the weather like in Lisbon?
I don't currently have weather lookup capability. I'll add it now.
[Calling tool 'create_file' from server 'evo_server']
[Native tool 'connect_to_server': Successfully connected to server 'weather'. Its tools are now available.]
Created weather_server.py, connected weather server, called get_weather for Lisbon.
```

```text
Query: Can you get the exchange rate from EUR to USD?
I don't currently have a tool to fetch exchange rates. I'll create one.
[Calling tool 'create_file' from server 'evo_server']
[Native tool 'connect_to_server': Successfully connected to server 'exchange_rate'. Its tools are now available.]
Created exchange_rate_server.py, connected it, called get_exchange_rate(EUR, USD).
```

## What is evolving?

With the base tools provided by the server and the client logic, the system can go beyond its initial capabilities. If a task requires something new, it can create additional MCP server files, connect them at runtime, and start using them immediately.

In other words, the agent is not limited to a fixed toolset. It can extend itself by generating new server capabilities according to the user’s needs.

## How it works

The key evolution capability lives in the client, not in the base server. The server provides simple, general-purpose tools like:

- `create_file` — create or update files
- `read_file` — read file contents
- `delete_file` — delete files
- `run_command` — execute shell commands

These tools are useful, but the real power comes from the client.

The client includes a prompt that explicitly tells the agent it can expand its toolset and how to do it. That prompt is defined in `evo/evo_client.py` and explains how to:

- detect missing capabilities
- write new MCP server scripts with the required tools
- connect the new server at runtime
- use the newly available tools immediately

A second critical piece is the native client-side tool called `connect_to_server`.
This tool is injected directly into the agent's available toolset and lets the client connect to new or updated MCP servers on demand:

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

When the agent decides it needs a capability it does not already have, it can call `connect_to_server` with a path to a new or modified server script. The client then starts that server and imports its tool definitions without restarting the whole client.

There is also a hot-reload mechanism watching existing server scripts for changes. In `evo/evo_client.py`, the client uses `watchdog` to observe server file updates and mark changed servers. The `apply_pending_reloads` flow is called before each query, so changed servers are reloaded before the next user interaction:

```python
self.observer = Observer()
self.observer.start()
...
self.observer.schedule(handler, watch_dir, recursive=False)
```

This means an updated server script can add new tools or change behavior, and the client will pick up the new capabilities before the next query.

These client-side features are what make the system truly evolutionary:

- the prompt tells the agent it can grow
- `connect_to_server` lets it add new servers and tools dynamically
- server file watching and reloads let the agent hot-reload updated capabilities without restarting

Without these client-side mechanisms, the agent could still use the base server tools, but it would not be able to evolve its own toolset on demand.

## Why this project exists

This project is meant to demonstrate how an agent-like system can evolve its toolset dynamically through code generation and runtime integration, using the Model Context Protocol.

## Notes

This is an experimental intended for learning and exploration rather than production deployment.
