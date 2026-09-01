import os, asyncio, httpx, random
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY","sk-kateto")
os.environ["OPENAI_API_BASE"] = os.getenv("OPENAI_API_BASE","http://127.0.0.1:11434/v1")
BRIDGE = os.getenv("BRIDGE_URL","http://127.0.0.1:8099")
MC_PORT = int(os.getenv("MC_PORT","45123"))
async def post(text, voice="jane", rms=0.2):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(f"{BRIDGE}/api/game/event", json={"game":"minecraft","event_type":"game_event","voice_id":voice,"text":text,"rms":rms,"state":{}})
    except Exception as e:
        print(f"[bridge fail] {e}")

async def main():
    await post("Voyager: conectando a MC 45123", voice="conquest")
    try:
        from voyager import Voyager
        print(f"Voyager import ok, MC port {MC_PORT}")
        voyager = Voyager(
            mc_port=MC_PORT,
            server_port=3000,
            openai_api_key=os.getenv("OPENAI_API_KEY","sk-kateto"),
            action_agent_model_name=os.getenv("VOYAGER_MODEL","Kateto"),
            curriculum_agent_model_name=os.getenv("VOYAGER_MODEL","Kateto"),
            critic_agent_model_name=os.getenv("VOYAGER_MODEL","Kateto"),
            skill_manager_model_name=os.getenv("VOYAGER_MODEL","Kateto"),
        )
        await post(f"Voyager iniciado MC:{MC_PORT} -> Kateto", voice="jane")
        # patch openai base if needed
        try:
            import openai
            openai.api_base = os.getenv("OPENAI_API_BASE","http://127.0.0.1:11434/v1")
        except: pass
        print("Voyager.learn() starting...")
        # run with bridge callbacks
        # Voyager.learn is blocking, run in thread and post heartbeat
        import threading
        def learn():
            try: voyager.learn()
            except Exception as e: print(f"Voyager learn fail {e}")
        t = threading.Thread(target=learn, daemon=True)
        t.start()
        # heartbeat to Kateto while learning
        voices=["jane","doktor","conquest"]
        tasks=["explora cueva","tala árbol","craftea mesa","busca diamante"]
        import time
        for i in range(60):
            await asyncio.sleep(10)
            await post(f"{random.choice(voices)} {random.choice(tasks)} paso {i}", rms=0.2)
            print(f"[heartbeat {i}] posted")
        t.join()
    except Exception as e:
        print(f"Voyager failed {e}, fallback mock")
        import traceback; traceback.print_exc()
        for i in range(6):
            await post(f"mock {random.choice(['explora','tala'])} {i}", rms=0.2)
            await asyncio.sleep(2)

if __name__=="__main__":
    asyncio.run(main())
