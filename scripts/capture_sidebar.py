import asyncio
from playwright.async_api import async_playwright

async def capture_toc_json(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        toc_url = None
        
        def handle_request(request):
            nonlocal toc_url
            if "_toc.json" in request.url or "nav?path=" in request.url:
                toc_url = request.url
                print(f"FOUND TOC URL: {toc_url}")

        page.on("request", handle_request)
        
        print(f"Loading {url}...")
        await page.goto(url, wait_until="networkidle")
        
        # Give it a bit more time to load dynamic content
        await asyncio.sleep(5)
        
        if toc_url:
            print(f"\nFinal TOC URL: {toc_url}")
            # Try to fetch it
            response = await page.request.get(toc_url)
            if response.ok:
                data = await response.json()
                with open("sidebar.json", "w") as f:
                    json.dump(data, f, indent=2)
                print("Sidebar JSON saved to sidebar.json")
        else:
            print("\nCould not find TOC JSON URL automatically.")
            
        await browser.close()

import json
if __name__ == "__main__":
    url = "https://cloud.google.com/customer-engagement-ai/conversational-agents/ps/docs/quickstart"
    asyncio.run(capture_toc_json(url))
