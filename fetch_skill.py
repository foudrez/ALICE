import urllib.request
import re

url = 'https://mcpmarket.com/tools/skills/live2d-character-development'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
})

try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        
        # Look for github URLs
        github_urls = re.findall(r'https://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+', html)
        print("GitHub URLs found:")
        for g in set(github_urls):
            print(g)
            
except Exception as e:
    print(f"Error: {e}")
