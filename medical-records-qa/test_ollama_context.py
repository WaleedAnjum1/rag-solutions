import asyncio
import httpx
import time

async def main():
    base_url = "http://localhost:11434"
    model = "llama3" # or whatever is configured

    # 1. Initial document load
    start = time.time()
    system_prompt = "You are a medical assistant. Use the following document to answer questions.\n\n=== Document ===\nPatient Name: John Doe\nHB: 14.5 g/dL\nWBC: 7.2\nUric Acid: 5.5 mg/dL\n"
    print("Loading document into Ollama...")
    
    async with httpx.AsyncClient() as client:
        # Get the configured model
        resp = await client.get("http://localhost:8200/docs") # just a dummy to get the server running, let's just use the config
        
        # We'll hardcode llama3 or check what model is running
        tags = await client.get(f"{base_url}/api/tags")
        if tags.status_code == 200:
            models = tags.json().get("models", [])
            if models:
                model = models[0]["name"]
                
        print(f"Using model: {model}")
        
        resp = await client.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": system_prompt,
                "keep_alive": -1,
                "options": {"num_predict": 1}
            },
            timeout=None
        )
        data = resp.json()
        context_arr = data.get("context", [])
        print(f"Document loaded in {time.time() - start:.2f}s. Context size: {len(context_arr)}")
        
        # 2. Ask question 1 using context
        start = time.time()
        q1 = "=== Question ===\nWhat is HB?\n\n=== Answer ===\n"
        resp = await client.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": q1,
                "context": context_arr,
                "keep_alive": -1,
            },
            timeout=None
        )
        print(f"Q1 answered in {time.time() - start:.2f}s: {resp.json().get('response')}")
        
        # 3. Ask question 2 using context
        start = time.time()
        q2 = "=== Question ===\nWhat is Uric Acid?\n\n=== Answer ===\n"
        resp = await client.post(
            f"{base_url}/api/generate",
            json={
                "model": model,
                "prompt": q2,
                "context": context_arr,
                "keep_alive": -1,
            },
            timeout=None
        )
        print(f"Q2 answered in {time.time() - start:.2f}s: {resp.json().get('response')}")

asyncio.run(main())
