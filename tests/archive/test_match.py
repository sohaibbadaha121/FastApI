import json

# Test the matches_name function directly
judge_field = '["ايمن زهران"]'
name_parts = ['ايمن', 'زهران']

print(f"Judge field: {judge_field}")
print(f"Name parts to find: {name_parts}\n")

try:
    names = json.loads(judge_field)
    print(f"Parsed names: {names}")
    print(f"Is list: {isinstance(names, list)}\n")
    
    for name in names:
        name_lower = str(name).lower()
        print(f"Checking name: '{name}'")
        print(f"Name (lower): '{name_lower}'")
        
        for part in name_parts:
            part_lower = part.lower()
            is_in = part_lower in name_lower
            print(f"  '{part_lower}' in '{name_lower}': {is_in}")
        
        all_match = all(part.lower() in name_lower for part in name_parts)
        print(f"  All parts match: {all_match}")
        
except Exception as e:
    print(f"Error: {e}")
