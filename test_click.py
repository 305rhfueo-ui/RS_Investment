import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Listen for console events
        page.on("console", lambda msg: print(f"Console {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Page Error: {err}"))
        
        print("Navigating to http://localhost:8080/index.html")
        await page.goto("http://localhost:8080/index.html")
        await page.wait_for_timeout(2000)
        
        print("Clicking Today's List")
        try:
            # The button has id 'todays-list-btn'
            await page.click("#todays-list-btn", timeout=5000)
            print("Successfully clicked Today's List")
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Error clicking: {e}")
            
        await browser.close()

asyncio.run(run())
