from azure.identity import ClientSecretCredential
import logging
import requests
import traceback
import os

from dotenv import load_dotenv
# Load environment variables
load_dotenv()

def _print_agent_details(agent):
    """Print key agent details in a readable format."""
    print("=" * 50)
    print(f"  Agent ID:           {agent.get('id', 'N/A')}")
    print(f"  Display Name:       {agent.get('displayName', 'N/A')}")
    print(f"  Source Agent ID:    {agent.get('sourceAgentId', 'N/A')}")
    print(f"  Originating Store:  {agent.get('originatingStore', 'N/A')}")
    print(f"  URL:                {agent.get('url', 'N/A')}")
    print(f"  Transport:          {agent.get('preferredTransport', 'N/A')}")
    print(f"  Owner IDs:          {agent.get('ownerIds', 'N/A')}")
    print(f"  Managed By:         {agent.get('managedBy', 'N/A')}")
    print(f"  Created:            {agent.get('createdDateTime', 'N/A')}")
    print(f"  Last Modified:      {agent.get('lastModifiedDateTime', 'N/A')}")
    print(f"  Identity ID:        {agent.get('agentIdentityId', 'N/A')}")
    print(f"  User ID:            {agent.get('agentUserId', 'N/A')}")
    manifest = agent.get("agentCardManifest", {})
    if manifest:
        print(f"  Manifest Version:   {manifest.get('version', 'N/A')}")
        print(f"  Protocol Version:   {manifest.get('protocolVersion', 'N/A')}")
        print(f"  Description:        {manifest.get('description', 'N/A')}")
        caps = manifest.get("capabilities", {})
        if caps:
            print(f"  Streaming:          {caps.get('streaming', 'N/A')}")
            print(f"  Push Notifications: {caps.get('pushNotifications', 'N/A')}")
        skills = manifest.get("skills", [])
        for i, skill in enumerate(skills):
            print(f"  Skill [{i+1}]:          {skill.get('displayName', 'N/A')} - {skill.get('description', 'N/A')}")
    print("=" * 50)

def listAgent365(request_json):
    import requests
    from datetime import datetime, timedelta
    import time
    

    try:
        logging.debug ("inside registerAgent365")

        tenant_id = request_json.get("tenant_id")
        client_id = request_json.get("client_id")
        client_secret = request_json.get("client_secret_value")

        if not all([tenant_id, client_id, client_secret]):
            raise ValueError("Missing tenant_id, client_id, or client_secret_value")

        cred = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )

        token = cred.get_token("https://graph.microsoft.com/.default").token

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }


        agent_card = request_json.get("agent_card") or {}
        graph_url = "https://graph.microsoft.com/beta/agentRegistry/agentInstances"

        source_id = agent_card.get("sourceAgentId") or agent_card.get("id")
        display_name = agent_card.get("displayName", "")
        list_resp = requests.get(graph_url, headers=headers)
        if list_resp.status_code < 300:
            items = list_resp.json().get("value", [])
            if not items:
                logging.info("No agents found in registry.")
                return {"STATUS": 0, "MESSAGE": "No agents found.", "agents": []}

            # If no specific agent card filter, show all agents
            if not source_id and not display_name:
                print(f"\nTotal agents in registry: {len(items)}")
                print("All registered agents:")
                for idx, item in enumerate(items, 1):
                    print(f"\n  Agent {idx}:")
                    _print_agent_details(item)
                return {"STATUS": 0, "MESSAGE": f"Found {len(items)} agent(s).", "agents": items}

            # Search for a specific agent
            for item in items:
                item_source = item.get("sourceAgentId", "")
                item_name = item.get("displayName", "")
                if (source_id and source_id in item_source) or \
                   (item_source == source_id) or \
                   (display_name and item_name == display_name):
                    logging.info("Agent already exists. Skipping creation.")
                    print("\n[VERIFIED] Agent is ACTIVE in Microsoft 365 Agents list.")
                    _print_agent_details(item)
                    print(f"\nTotal agents in registry: {len(items)}")
                    print("All registered agents:")
                    for idx, a in enumerate(items, 1):
                        marker = " <-- YOUR AGENT" if a.get("id") == item.get("id") else ""
                        print(f"  {idx}. {a.get('displayName', 'N/A')} (id: {a.get('id', 'N/A')}){marker}")
                    return {"STATUS": 0, "MESSAGE": "Agent already registered. Skipped creation.", "agent": item}
        else:
            logging.error(f"Failed to list agents. Status: {list_resp.status_code}, Response: {list_resp.text}")
            return {"STATUS": 1, "MESSAGE": f"Failed to list agents: {list_resp.status_code}"}

    except Exception as e:
        logging.error(f"An error occurred in listAgent365: {str(e)}")
        traceback.print_exc()
        return {"STATUS": 1, "MESSAGE": str(e)}


if __name__ == "__main__":
    print("starting --------------------------------------------------")
    import json
    result = listAgent365({
    "request_type": "register-agent-365",
    "application_id": "admin-test",
    "tenant_id": os.getenv("tenant_id"),
    "client_id": os.getenv("client_id"),
    "client_secret_value": os.getenv("client_secret_value"),
    "agent_card": {
        "id": "Langchain-finance-agent-007",
        "displayName": "LangChain Finance Agent",
        "ownerIds": ["ede415a0-fe5a-420f-8982-a7f1776fc36a"],
        "sourceAgentId": "finance-agent-007",
        "originatingStore": "Custom",
        "url": "https://yourdomain.com/agent",
        "preferredTransport": "HTTP+JSON",
        "additionalInterfaces": [
          {
            "url": "https://yourdomain.com/agent",
            "transport": "HTTP+JSON"
          }
        ],
        "agentCardManifest": {
          "displayName": "LangChain Finance Agent",
          "description": "Finance operations assistant powered by LangChain",
          "originatingStore": "Custom",
          "protocolVersion": "1.0",
          "version": "1.0.0",
          "supportsAuthenticatedExtendedCard": False,
          "defaultInputModes": ["application/json"],
          "defaultOutputModes": ["application/json"],
          "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
            "extensions": []
          },
          "skills": [
            {
              "displayName": "Finance Ops Q&A",
              "description": "Answer finance operations questions and explain next steps for common finance processes.",
              "examples": [
                "How do I book an accrual for vendor invoices?",
                "Explain the approval flow for expense reimbursements"
              ]
            }
          ]
        }
  }
  })

    
    print("=" * 60)
    print("\nCompleted ------------------------------------")
