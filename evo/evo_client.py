import asyncio
import sys
import threading
from pathlib import Path
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

load_dotenv()

ANTHROPIC_MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """
You are Swiss — a silent, capable agent named after the Swiss Army Knife. You do almost anything your user needs.

## Identity
You are work-focused. You do not make small talk, do not announce what you are about to do, and do not ask for confirmation unless a decision is genuinely irreversible and ambiguous. You act, then report briefly.

## How you operate
At the end of every response, provide a short summary of what you did — tools called, files created or modified, servers connected. Nothing else. No preamble, no explanations before acting.

## Your base capabilities
You have access to a set of file system tools on your base MCP server:
- **create_file** — create a new file or update an existing one with content
- **read_file** — read the content of a file
- **delete_file** — delete a file
- **run_command** — execute a bash shell command in a given directory

These are your hands. Use them freely and in combination to fulfill any request.

## Expanding your own capabilities
You are not limited to your base tools. You can and should create new MCP servers when a task requires capabilities you do not currently have.

The workflow is:
1. Identify that a capability is missing
2. Identify any third-party Python packages the new server will need (beyond the standard library and mcp/fastmcp)
3. Install those packages first using run_command: `pip install <package1> <package2>` — do this before writing the server file
4. Write the new MCP server script using create_file
5. Call connect_to_server with the path to that file to connect it to the client immediately
6. The new tools become available in the same session — use them

Always install dependencies before creating the server file. Never assume a package is available — if the server imports anything beyond the standard library and mcp, install it first.

You can also edit existing MCP server scripts directly using create_file or run_command. Changes to already-connected servers are detected automatically and the server is reloaded — no reconnection needed.

## When to expand
If a user request requires a capability you do not have, expand first, then fulfill the request — all in one turn if possible. Do not tell the user you are expanding. Do not ask permission. Just do it and include it in the end summary.

## MCP server structure
New MCP servers must follow this pattern:

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("server_name")

@mcp.tool()
async def tool_name(param: str) -> str:
    \"\"\"Tool description.\"\"\"
    ...

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
```

## What you never do
- Do not describe what you are about to do
- Do not ask for confirmation on routine tasks
- Do not explain your reasoning unless asked
- Do not leave a task half done — if a tool is missing, build it
""".strip()

# Native client-side tool definition — injected into every API call.
# The model can call this to connect a newly created server to the client.
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


class ServerFileChangeHandler(FileSystemEventHandler):
    """Watchdog handler that sets a flag when a watched server script is modified."""

    def __init__(self, server_name: str, script_path: str, changed_servers: set, lock: threading.Lock):
        self.server_name = server_name
        self.script_path = str(Path(script_path).resolve())
        self.changed_servers = changed_servers
        self.lock = lock

    def on_modified(self, event):
        if not event.is_directory and str(Path(event.src_path).resolve()) == self.script_path:
            with self.lock:
                self.changed_servers.add(self.server_name)


class MCPClient:
    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}
        self.server_exit_stacks: dict[str, AsyncExitStack] = {}
        self.server_paths: dict[str, str] = {}

        # Hot reload state
        self.changed_servers: set[str] = set()
        self.changed_servers_lock = threading.Lock()
        self.observer = Observer()
        self.observer.start()

        self.anthropic = Anthropic()

    async def connect_to_server(self, server_name: str, server_script_path: str):
        """Connect (or reconnect) to an MCP server, cleanly replacing any existing session."""

        if server_name in self.server_exit_stacks:
            print(f"Restarting server '{server_name}'...")
            await self.server_exit_stacks[server_name].aclose()

        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stack = AsyncExitStack()
        await stack.__aenter__()

        try:
            stdio_transport = await stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await stack.enter_async_context(ClientSession(stdio, write))
            await session.initialize()
        except Exception as e:
            try:
                await stack.aclose()
            except Exception:
                pass
            raise RuntimeError(f"Failed to start server '{server_name}': {e}") from e

        self.sessions[server_name] = session
        self.server_exit_stacks[server_name] = stack
        self.server_paths[server_name] = server_script_path

        # Start watching this server's file for changes
        watch_dir = str(Path(server_script_path).resolve().parent)
        handler = ServerFileChangeHandler(
            server_name, server_script_path, self.changed_servers, self.changed_servers_lock
        )
        self.observer.schedule(handler, watch_dir, recursive=False)

        response = await session.list_tools()
        tools = response.tools
        print(f"Connected to server '{server_name}' with {len(tools)} tools: {[tool.name for tool in tools]}")

    async def reload_server(self, server_name: str):
        """Restart a server by name, picking up any changes to its script."""
        if server_name not in self.server_paths:
            print(f"Unknown server '{server_name}'")
            return
        await self.connect_to_server(server_name, self.server_paths[server_name])

    async def apply_pending_reloads(self):
        """Check for servers that changed on disk and reload them. Called between queries."""
        with self.changed_servers_lock:
            pending = list(self.changed_servers)
            self.changed_servers.clear()

        for server_name in pending:
            print(f"\nDetected change in server '{server_name}', reloading...")
            await self.reload_server(server_name)

    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools from all servers."""
        messages = [{"role": "user", "content": query}]

        # Aggregate tools from all connected servers
        available_tools = []
        tool_server_map = {}

        for server_name, session in self.sessions.items():
            response = await session.list_tools()
            for tool in response.tools:
                available_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                })
                tool_server_map[tool.name] = server_name

        # Inject the native client-side connect tool
        available_tools.append(NATIVE_CONNECT_TOOL)

        final_text = []

        response = self.anthropic.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=available_tools
        )

        while response.stop_reason == "tool_use":
            assistant_message_content = []

            for content in response.content:
                assistant_message_content.append(content)
                if content.type == 'text':
                    final_text.append(content.text)

            tool_results = []

            for content in response.content:
                if content.type == 'tool_use':
                    tool_name = content.name
                    tool_args = content.input

                    # Native tool: dispatch directly to the client method
                    if tool_name == "connect_to_server":
                        try:
                            await self.connect_to_server(
                                tool_args["server_name"],
                                tool_args["server_script_path"]
                            )
                            result_text = (
                                f"Successfully connected to server '{tool_args['server_name']}'. "
                                f"Its tools are now available."
                            )
                        except Exception as e:
                            result_text = f"Failed to connect to server: {str(e)}"

                        final_text.append(f"[Native tool 'connect_to_server': {result_text}]")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": result_text
                        })
                        continue

                    # MCP server tool: route to the correct session
                    if tool_name not in tool_server_map:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": f"Error: Tool '{tool_name}' not found"
                        })
                        continue

                    server_name = tool_server_map[tool_name]
                    session = self.sessions[server_name]
                    result = await session.call_tool(tool_name, tool_args)
                    final_text.append(f"[Calling tool '{tool_name}' from server '{server_name}']")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content.id,
                        "content": result.content
                    })

            messages.append({"role": "assistant", "content": assistant_message_content})
            messages.append({"role": "user", "content": tool_results})

            # Rebuild available_tools to include any newly connected servers
            available_tools = []
            tool_server_map = {}
            for server_name, session in self.sessions.items():
                response = await session.list_tools()
                for tool in response.tools:
                    available_tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema
                    })
                    tool_server_map[tool.name] = server_name
            available_tools.append(NATIVE_CONNECT_TOOL)

            response = self.anthropic.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=available_tools
            )

        for content in response.content:
            if content.type == 'text':
                final_text.append(content.text)

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop with automatic server hot-reload between queries."""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit'/'exit' to exit.")
        print("Server scripts are watched automatically — save a change and it reloads before your next query.\n")

        while True:
            try:
                await self.apply_pending_reloads()

                query = input("Query: ").strip()

                if not query:
                    continue

                if query.lower() in ('quit', 'exit'):
                    break

                await self.apply_pending_reloads()

                response = await self.process_query(query)
                print("\n" + response + "\n")

            except Exception as e:
                print(f"\nError: {str(e)}\n")

    async def cleanup(self):
        """Clean up all server sessions and stop the file watcher."""
        self.observer.stop()
        self.observer.join()
        for stack in self.server_exit_stacks.values():
            await stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script1> [path_to_server_script2] ...")
        sys.exit(1)

    client = MCPClient()
    try:
        for server_path in sys.argv[1:]:
            server_name = Path(server_path).stem
            await client.connect_to_server(server_name, server_path)

        print(f"✓ Connected to {len(sys.argv) - 1} server(s)")
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())