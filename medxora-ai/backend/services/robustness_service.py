from __future__ import annotations

def _clamp(v,a,b): return max(a,min(b,v))

def calculate_robustness_score(metrics, walk_forward_result=None, monte_carlo_result=None, sensitivity_result=None):
    sharpe=float(metrics.get('sharpe_ratio',metrics.get('sharpe',0)) or 0)
    dd=float(metrics.get('max_drawdown_pct',metrics.get('max_drawdown',100)) or 100)
    pf=float(metrics.get('profit_factor',0) or 0)
    trades=float(metrics.get('total_trades',0) or 0)
    oos=float((walk_forward_result or {}).get('stability_score',50) or 50)
    mc=float((monte_carlo_result or {}).get('monte_carlo_score',50) or 50)
    sens=float((sensitivity_result or {}).get('score',70) or 70)
    consistency=float(metrics.get('consistency_score',60) or 60)

    components={
      'sharpe_quality': round(_clamp(sharpe/2*20,0,20),2),
      'drawdown_control': round(_clamp((30-dd)/30*20,0,20),2),
      'oos_stability': round(_clamp(oos/100*20,0,20),2),
      'monte_carlo_survival': round(_clamp(mc/100*15,0,15),2),
      'parameter_sensitivity': round(_clamp(sens/100*10,0,10),2),
      'consistency': round(_clamp(consistency/100*10,0,10),2),
      'profit_factor': round(_clamp(((pf-1)/1.5)*5 + min(trades/100,1),0,5),2),
    }
    score=round(sum(components.values()),2)
    if score>=85: grade='Production Ready'
    elif score>=70: grade='Strong Candidate'
    elif score>=55: grade='Needs More Testing'
    elif score>=40: grade='Overfit Risk'
    else: grade='Reject'
    warnings=[]
    if dd>15: warnings.append('High Drawdown')
    if sharpe<1.0: warnings.append('Weak OOS')
    if trades<40: warnings.append('Low Trade Count')
    badges=[]
    if dd<=12: badges.append('Low Drawdown')
    if oos>=65: badges.append('OOS Verified')
    if mc>=65: badges.append('Monte Carlo Passed')
    badges.append(grade)
    return {'score':score,'grade':grade,'components':components,'warnings':warnings,'badges':badges}
