from pathlib import Path
from services.agentic_foundation import add_event

def run(mission_id:str,strategy:dict)->dict:
    out=Path(__file__).resolve().parents[1]/"generated_strategies"; out.mkdir(exist_ok=True)
    fn=f"{strategy['id']}.mq5"; fp=out/fn; code=f"// {strategy['name']}\ninput int FastEMA=20;"
    fp.write_text(code,encoding='utf-8')
    payload={"filename":fn,"file_path":str(fp),"code_preview":code}
    add_event(mission_id,"MQL5 Code Agent","completed","mql5_export","MQL5 exported","success",payload)
    return payload
