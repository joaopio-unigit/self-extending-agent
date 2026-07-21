# Evolutionary MCP

Evolutionary MCP is an experimental project that explores how an MCP client and MCP server can grow their own capabilities over time.

## What this repository contains

This repository includes two core pieces:

- an MCP client that coordinates the interaction between the user, an LLM, and available MCP servers
- a basic MCP server that provides fundamental filesystem capabilities such as creating, reading, deleting files, and running terminal commands

## What is evolving?

With the base tools provided by the server and the client logic, the system can go beyond its initial capabilities. If a task requires something new, it can create additional MCP server files, connect them at runtime, and start using them immediately.

In other words, the MCP is not limited to a fixed toolset. It can extend itself by generating new server capabilities according to the user’s needs.

## Why this project exists

This project is meant to demonstrate how an agent-like system can evolve its toolset dynamically through code generation and runtime integration, using the Model Context Protocol.

## Notes

This is an experimental intended for learning and exploration rather than production deployment.
