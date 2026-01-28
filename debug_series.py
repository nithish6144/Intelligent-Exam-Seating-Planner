
import re

def parse_series(start_s, end_s):
    print(f"Testing: {start_s} -> {end_s}")
    match_start = re.match(r"^(.*?)(\d+)$", start_s)
    match_end = re.match(r"^(.*?)(\d+)$", end_s)
    
    if not match_start or not match_end:
        print("Regex failed to match one or both.")
        return []

    prefix_start = match_start.group(1)
    prefix_end = match_end.group(1)
    
    print(f"Prefix Start: '{prefix_start}'")
    print(f"Prefix End:   '{prefix_end}'")
    
    if prefix_start == prefix_end:
        print("Prefixes match. Standard generation.")
        return [1] # Dummy
    else:
        print("FAIL: Prefixes do not match.")
        return []

# Test Case from User
parse_series("22881A6601", "22881A66F9")
