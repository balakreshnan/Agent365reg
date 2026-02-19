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

def registerAgent365(request_json):
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


        agent_card = request_json.get("agent_card")
        graph_url = "https://graph.microsoft.com/beta/agentRegistry/agentInstances"

        # Check if agent already exists before trying to create
        source_id = agent_card.get("sourceAgentId") or agent_card.get("id")
        display_name = agent_card.get("displayName", "")
        list_resp = requests.get(graph_url, headers=headers)
        if list_resp.status_code < 300:
            items = list_resp.json().get("value", [])
            for item in items:
                item_source = item.get("sourceAgentId", "")
                item_name = item.get("displayName", "")
                if (source_id and source_id in item_source) or \
                   (item_source == source_id) or \
                   (display_name and item_name == display_name):
                    logging.info("Agent already exists. Skipping creation.")
                    print("\n[VERIFIED] Agent is ACTIVE in Microsoft 365 Agents list.")
                    _print_agent_details(item)
                    # Show position in full agent list
                    print(f"\nTotal agents in registry: {len(items)}")
                    print("All registered agents:")
                    for idx, a in enumerate(items, 1):
                        marker = " <-- YOUR AGENT" if a.get("id") == item.get("id") else ""
                        print(f"  {idx}. {a.get('displayName', 'N/A')} (id: {a.get('id', 'N/A')}){marker}")
                    return {"STATUS": 0, "MESSAGE": "Agent already registered. Skipped creation.", "agent": item}

        # Agent does not exist — create it
        # The API requires 'id' in the body
        response = requests.post(graph_url, headers=headers, json=agent_card)

        if response.status_code == 409:
            # Agent exists but wasn't in our list — ghost/tombstone state
            logging.info("Agent already exists (409). Trying filter query and alternate deletion.")

            # Try to find it with $filter
            filter_url = f"{graph_url}?$filter=sourceAgentId eq '{source_id}'"
            filter_resp = requests.get(filter_url, headers=headers)
            if filter_resp.status_code < 300:
                filtered = filter_resp.json().get("value", [])
                if filtered:
                    print("Found agent via filter:")
                    _print_agent_details(filtered[0])
                    return {"STATUS": 0, "MESSAGE": "Agent already registered.", "agent": filtered[0]}

            # Try to delete the ghost agent using the old known IDs
            old_ids = [
                agent_card.get("id", ""),
                f"LangChain Finance Agent: {source_id}",
                source_id,
            ]
            import time
            for old_id in old_ids:
                if not old_id:
                    continue
                del_url = f"{graph_url}/{requests.utils.quote(str(old_id), safe='')}"
                logging.info(f"Attempting DELETE with id: {old_id}")
                del_resp = requests.delete(del_url, headers=headers)
                logging.info(f"DELETE response: {del_resp.status_code}")
                if del_resp.status_code < 300 or del_resp.status_code == 204:
                    # Deletion succeeded — wait and retry POST
                    time.sleep(5)
                    response = requests.post(graph_url, headers=headers, json=agent_card)
                    if response.status_code < 300:
                        print("Agent re-created successfully after deleting ghost entry:")
                        result = response.json()
                        _print_agent_details(result)
                        return result

            # If all else fails, suggest changing sourceAgentId
            print("\n" + "!" * 60)
            print("  The agent with sourceAgentId '{}' is in a ghost state.".format(source_id))
            print("  It exists (409 on create) but is not visible in the agent list.")
            print("  This can happen after a partial delete.")
            print("")
            print("  Options:")
            print("  1. Wait ~15 minutes for the tombstone to expire, then retry.")
            print("  2. Use a different sourceAgentId (e.g. 'finance-agent-007').")
            print("!" * 60 + "\n")
            return {"STATUS": -1, "MESSAGE": f"Agent with sourceAgentId '{source_id}' is in a ghost state. Try a different sourceAgentId or wait and retry."}

        if response.status_code >= 300:
            raise Exception(f"Graph API Error: {response.status_code} - {response.text}")

        result = response.json()
        print("\n[SUCCESS] Agent created and is now ACTIVE in Microsoft 365 Agents list!")
        _print_agent_details(result)

        # Verify by fetching the list again
        verify_resp = requests.get(graph_url, headers=headers)
        if verify_resp.status_code < 300:
            all_agents = verify_resp.json().get("value", [])
            agent_found = any(a.get("id") == result.get("id") for a in all_agents)
            if agent_found:
                print(f"\n[VERIFIED] Agent confirmed in registry.")
                print(f"Total agents in registry: {len(all_agents)}")
                for idx, a in enumerate(all_agents, 1):
                    marker = " <-- YOUR AGENT" if a.get("id") == result.get("id") else ""
                    print(f"  {idx}. {a.get('displayName', 'N/A')} (id: {a.get('id', 'N/A')}){marker}")
            else:
                print("\n[WARNING] Agent was created but not yet visible in list. It may take a moment to propagate.")

        return {"STATUS": 0, "MESSAGE": "Agent created successfully.", "agent": result}

    #try
    except Exception as e:
        traceback.print_exc()
        logging.error("Error in registerAgent365 - {error}".format(error=traceback.format_exc()))
        return {"STATUS" : -1, "MESSAGE": traceback.format_exc()}
    #except
#def


if __name__ == "__main__":
    print("starting --------------------------------------------------")
    import json
    result = registerAgent365({
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

    # Format the result for human-readable output
    print("\n" + "=" * 60)
    if result.get("STATUS") == 0:
        print("  Status:  SUCCESS")
    else:
        print("  Status:  FAILED")
    print(f"  Message: {result.get('MESSAGE', 'N/A')}")
    agent = result.get("agent")
    if agent:
        print("-" * 60)
        print(f"  Agent ID:           {agent.get('id', 'N/A')}")
        print(f"  Display Name:       {agent.get('displayName', 'N/A')}")
        print(f"  Source Agent ID:    {agent.get('sourceAgentId', 'N/A')}")
        print(f"  Originating Store:  {agent.get('originatingStore', 'N/A')}")
        print(f"  URL:                {agent.get('url', 'N/A')}")
        print(f"  Transport:          {agent.get('preferredTransport', 'N/A')}")
        print(f"  Owner IDs:          {', '.join(agent.get('ownerIds', []))}")
        print(f"  Managed By:         {agent.get('managedBy') or 'N/A'}")
        print(f"  Created:            {agent.get('createdDateTime', 'N/A')}")
        print(f"  Last Modified:      {agent.get('lastModifiedDateTime', 'N/A')}")
        print(f"  Identity ID:        {agent.get('agentIdentityId') or 'N/A'}")
        print(f"  User ID:            {agent.get('agentUserId') or 'N/A'}")
        interfaces = agent.get("additionalInterfaces", [])
        if interfaces:
            print("  Interfaces:")
            for iface in interfaces:
                print(f"    - {iface.get('transport', 'N/A')} @ {iface.get('url', 'N/A')}")
        signatures = agent.get("signatures", [])
        if signatures:
            print(f"  Signatures:         {signatures}")
    print("=" * 60)
    print("\nCompleted ------------------------------------")