#!/usr/bin/env python3
"""
Demo script showing how the intelligent agent works with LiteLLM and user-configured MCP servers
"""
import asyncio
import sys
import os
import json

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cortex.core.intelligent_agent import process_intelligent_message, get_intelligent_agent


async def demo_intelligent_agent():
    """Demo the intelligent agent with LiteLLM integration"""
    print("🧠 Intelligent Agent Orchestrator Demo")
    print("=" * 60)
    print("This demo shows how LiteLLM analyzes messages and routes them to MCP servers")
    print()
    
    # Note: For this demo to work, you'd need:
    # 1. A user configured in the database
    # 2. An MCP server configured for that user
    # 3. LiteLLM properly configured with API keys
    
    user_id = 1  # Example user ID
    
    # Test messages that demonstrate intelligence
    test_messages = [
        # Natural language requests that should trigger MCP actions
        "Can you show me information about the microsoft/vscode repository?",
        "What are the open issues in the facebook/react project?",
        "I want to see the contents of the microsoft/vscode repo",
        "Search for Python web frameworks on GitHub",
        
        # Conversational messages that shouldn't trigger MCP actions  
        "Hello, how are you?",
        "What can you help me with?",
        "Thank you for your help!",
        
        # Complex requests that need parameter extraction
        "Get me the README.md file from the microsoft/vscode repository",
        "Show me all the pull requests for the facebook/react project",
    ]
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{i}. User: {message}")
        print("-" * 50)
        
        try:
            # Process with intelligent agent (LiteLLM enabled)
            print("🧠 Processing with LiteLLM...")
            intelligent_response = await process_intelligent_message(
                user_id=user_id,
                message=message,
                use_llm=True
            )
            
            print(f"🤖 Intelligent Response: {intelligent_response}")
            
            # Also show what simple processing would do
            print("\n📝 For comparison, simple processing would:")
            simple_response = await process_intelligent_message(
                user_id=user_id,
                message=message,
                use_llm=False  # Fallback to keyword matching
            )
            print(f"🔧 Simple Response: {simple_response}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print()
        await asyncio.sleep(0.5)  # Small delay
    
    print("=" * 60)
    print("✅ Demo completed!")


async def demo_conversation_context():
    """Demo conversation with context"""
    print("\n💬 Conversation Context Demo")
    print("=" * 60)
    
    user_id = 1
    conversation_history = []
    
    # Simulate a conversation
    conversation = [
        "Hello, I'm working on a React project",
        "Can you show me the latest issues in the facebook/react repository?",
        "What about pull requests?",
        "Thanks, can you also show me the main files in that repo?"
    ]
    
    for i, message in enumerate(conversation, 1):
        print(f"\n{i}. User: {message}")
        print("-" * 40)
        
        try:
            agent = await get_intelligent_agent(user_id)
            response = await agent.chat_with_context(message, conversation_history)
            
            print(f"🤖 Agent: {response}")
            
            # Add to conversation history
            conversation_history.append({"role": "user", "content": message})
            conversation_history.append({"role": "assistant", "content": response})
            
            # Keep only last 10 messages
            if len(conversation_history) > 10:
                conversation_history = conversation_history[-10:]
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        await asyncio.sleep(0.5)
    
    print("\n=" * 60)
    print("✅ Conversation demo completed!")


async def demo_server_analysis():
    """Demo how the agent analyzes available servers"""
    print("\n🔍 Server Analysis Demo")
    print("=" * 60)
    
    user_id = 1
    
    try:
        agent = await get_intelligent_agent(user_id)
        servers = await agent.get_available_servers()
        
        print("Available MCP servers:")
        for server in servers:
            print(f"- {server['name']} ({server['type']}) - {'Default' if server.get('is_default') else 'Secondary'}")
            if server.get('description'):
                print(f"  Description: {server['description']}")
        
        if not servers:
            print("No MCP servers configured for this user.")
            print("\nTo test the intelligent agent, you need to:")
            print("1. Create a user in the database")
            print("2. Configure an MCP server for that user")
            print("3. Set up credentials if needed")
            
    except Exception as e:
        print(f"❌ Error getting servers: {str(e)}")


def show_integration_examples():
    """Show code examples for integration"""
    print("\n📚 Integration Examples")
    print("=" * 60)
    
    examples = [
        {
            "title": "Basic Intelligent Processing",
            "code": '''
from cortex.core.intelligent_agent import process_intelligent_message

# Process with LiteLLM intelligence
response = await process_intelligent_message(
    user_id=1,
    message="Show me info about microsoft/vscode repo",
    use_llm=True
)
print(response)
'''
        },
        {
            "title": "Chainlit Integration with Intelligence",
            "code": '''
import chainlit as cl
from cortex.core.intelligent_agent import process_intelligent_message

@cl.on_message
async def main(message: cl.Message):
    # Get user ID from session or auth
    user_id = cl.user_session.get("user_id", 1)
    
    response = await process_intelligent_message(
        user_id=user_id,
        message=message.content,
        use_llm=True
    )
    
    await cl.Message(content=response).send()
'''
        },
        {
            "title": "Conversation with Context",
            "code": '''
from cortex.core.intelligent_agent import get_intelligent_agent

agent = await get_intelligent_agent(user_id=1)

# Maintain conversation history
conversation_history = [
    {"role": "user", "content": "I'm working on a React project"},
    {"role": "assistant", "content": "Great! How can I help you with React?"}
]

response = await agent.chat_with_context(
    "Show me the latest React issues",
    conversation_history
)
'''
        },
        {
            "title": "API Endpoint Usage",
            "code": '''
# POST /mcp/intelligent-process
{
  "message": "Show me microsoft/vscode repository info",
  "use_llm": true,
  "conversation_history": [
    {"role": "user", "content": "I'm looking at VS Code"},
    {"role": "assistant", "content": "I can help you with VS Code information!"}
  ]
}
'''
        }
    ]
    
    for example in examples:
        print(f"\n{example['title']}:")
        print(example['code'])


async def main():
    """Main function"""
    print("🚀 Starting Intelligent Agent Demo...")
    print("Note: This demo requires proper database setup and LiteLLM configuration")
    print()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "conversation":
            await demo_conversation_context()
        elif sys.argv[1] == "servers":
            await demo_server_analysis()
        else:
            print("Available options: conversation, servers")
    else:
        await demo_intelligent_agent()
        await demo_server_analysis()
        show_integration_examples()


if __name__ == "__main__":
    print("Intelligent Agent Demo")
    print("Run with:")
    print("  python intelligent_agent_demo.py           # Full demo")
    print("  python intelligent_agent_demo.py conversation  # Conversation demo")
    print("  python intelligent_agent_demo.py servers      # Server analysis")
    print()
    
    asyncio.run(main())