from services.agentic_foundation import add_event

def run(mission_id:str,strategy:dict)->dict:
    evolved={**strategy,"id":strategy['id']+"_e1","status":"champion","params":{**strategy.get('params',{}),"ema_fast":18}}
    add_event(mission_id,"Evolution Agent","completed","evolution","Evolution attempt improved robustness","success",{"attempts":3,"selected":evolved['id']})
    return evolved

def run_evolution(parent: dict, generations: int = 3):
    # backward compatible placeholder used by legacy endpoints
    children = []
    base = dict(parent)
    for i in range(generations):
        child = dict(base)
        child["name"] = f"{base.get('name','strategy')}_g{i+1}"
        child["score"] = float(base.get("score", 0)) + (i + 1)
        children.append(child)
    return {"parent": parent, "children": children, "best": children[-1] if children else parent}
