# Cortex - Intelligent MCP Agent Orchestrator

Cortex is an intelligent agent orchestrator that manages multiple MCP (Model Context Protocol) servers for users.

It combines LiteLLM for natural language understanding with user-configured MCP servers to provide a powerful, multi-tenant agent platform.

## Features

**Intelligent Message Processing** - Uses LiteLLM to understand natural language and route to appropriate MCP servers
**Multi-Tenant** - Each user can configure their own MCP servers with encrypted credentials
**Secure** - Credentials are encrypted and user-isolated
**Extensible** - Easy to add new MCP server types
**Conversational** - Maintains conversation context and history
**Smart Routing** - Automatically selects the right server and tool for each request

## Deployment

The idea of this project is to be able to scale the API independently of the MCP servers.
