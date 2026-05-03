import asyncio
from playwright.async_api import async_playwright
import json

async def find_nav_json(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        print(f"Loading {url}...")
        await page.goto(url, wait_until="networkidle")
        
        # Wait for the sidebar to be present
        try:
            await page.wait_for_selector(".devsite-nav-list", timeout=10000)
        except:
            print("Sidebar not found using default selector.")

        # Extract all links from the sidebar
        links = await page.evaluate("""() => {
            // Try different common GCP doc sidebar selectors
            const selectors = [
                '.devsite-nav-list',
                '.devsite-book-nav',
                'nav[role="navigation"]',
                '.devsite-section-nav'
            ];
            
            let nav = null;
            for (const s of selectors) {
                nav = document.querySelector(s);
                if (nav && nav.querySelectorAll('a').length > 5) break;
            }

            if (!nav) return [];
            
            const anchors = Array.from(nav.querySelectorAll('a'));
            return anchors.map(a => ({
                text: a.innerText.trim(),
                href: a.href
            })).filter(l => l.href.startsWith('http'));
        }""")
        
        print(f"\nFound {len(links)} links in the sidebar:")
        unique_links = set()
        for l in links:
            if l['href'] not in unique_links:
                print(l['href'])
                unique_links.add(l['href'])
        
        with open("links.txt", "w") as f:
            for l in sorted(list(unique_links)):
                f.write(f"{l}\n")
        
        print(f"\nSaved {len(unique_links)} unique links to links.txt")
        await browser.close()

if __name__ == "__main__":
    url = "https://cloud.google.com/customer-engagement-ai/conversational-agents/ps"
    asyncio.run(find_nav_json(url))
