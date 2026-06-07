import requests

# We cache the devices here so the execution function knows exactly what ALICE is targeting
DYNAMIC_DEVICE_MAP = {}

def get_smart_home_context(config):
    """
    Fetches all devices from Home Assistant, maps them, and returns a formatted string
    for ALICE to read so she knows the live status of the house.
    """
    global DYNAMIC_DEVICE_MAP
    
    ha_config = config.get('home_assistant', {})
    ha_url = ha_config.get('url', '').rstrip('/')
    ha_token = ha_config.get('token', '')
    
    if not ha_token or ha_token == 'YOUR_LONG_LIVED_ACCESS_TOKEN_HERE':
        return "" # Fail silently if not configured yet
        
    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    
    try:
        # Pull the live state of the entire house
        response = requests.get(f"{ha_url}/api/states", headers=headers, timeout=2)
        if response.status_code != 200: return ""
        
        states = response.json()
        context_lines = []
        DYNAMIC_DEVICE_MAP.clear()
        
        # Only pull actionable devices so we don't overwhelm ALICE's memory with hidden sensors
        allowed_domains = ['light', 'switch', 'fan']
        
        for entity in states:
            domain = entity['entity_id'].split('.')[0]
            if domain in allowed_domains:
                friendly_name = entity['attributes'].get('friendly_name', entity['entity_id'])
                state = entity['state'].upper()
                
                # Convert the friendly name into a machine-readable command (e.g., "Bedroom Light" -> "BEDROOM_LIGHT")
                cmd_name = friendly_name.upper().replace(' ', '_').replace('-', '_')
                
                # Save to memory map for the execution phase
                DYNAMIC_DEVICE_MAP[cmd_name] = entity['entity_id']
                
                # Add to the text block ALICE will read
                context_lines.append(f"- {friendly_name} (Command Tag: {cmd_name}): Currently {state}")
                
        if not context_lines: return ""
        return "LIVE SMART HOME STATUS:\n" + "\n".join(context_lines)
        
    except requests.exceptions.RequestException:
        return "[System Note: Cannot connect to Home Assistant]"

def execute_ha_command(command, config):
    """
    Executes commands using the dynamically generated device map.
    """
    ha_config = config.get('home_assistant', {})
    ha_url = ha_config.get('url', '').rstrip('/')
    ha_token = ha_config.get('token', '')
    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}

    try:
        # Example command: "BEDROOM_LIGHT_ON"
        parts = command.split('_')
        action = parts[-1] # Grabs the "ON" or "OFF"
        target_cmd = "_".join(parts[:-1]) # Rebuilds the "BEDROOM_LIGHT" part
        
        # Look up the actual entity ID (e.g., light.bedroom) from our live map
        entity_id = DYNAMIC_DEVICE_MAP.get(target_cmd)
        
        if not entity_id:
            print(f"[⚠️ HA Error] Unknown dynamic target: {target_cmd}")
            return False
            
        domain = entity_id.split('.')[0]
        service = "turn_on" if action == "ON" else "turn_off"
        endpoint = f"{ha_url}/api/services/{domain}/{service}"
        
        print(f"[🏠 Smart Home] Executing: {service} on {entity_id}...")
        requests.post(endpoint, headers=headers, json={"entity_id": entity_id}, timeout=3)
        return True
        
    except Exception as e:
        print(f"[❌ Smart Home] Error: {e}")
        return False