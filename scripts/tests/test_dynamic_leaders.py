from pathlib import Path
import json, subprocess
ROOT=Path(__file__).resolve().parents[1]

def test_dynamic_leader_engine_changes_with_market_focus_and_diversifies():
    script=r"""
const engine=require('./assets/dynamic-leaders.js');
const sectors=['半導體業','電腦及週邊設備業','金融保險業','航運業','電機機械業','生技醫療業','鋼鐵工業'];
const market=[];const basics={};const chips={};
for(let i=0;i<28;i++){
 const symbol=String(1101+i);const sector=sectors[i%sectors.length];
 market.push({symbol,name:'公司'+i,asset_class:'stock',price:40+i,trade_value:1e8*(i+1),volume:1e5*(i+2),change_percent:(i%9)-4,quote_date:'2026-08-07'});
 basics[symbol]={symbol,industry_name:sector,issued_shares:1e8*(1+(i%5)),business_scope:sector};
 chips[symbol]={symbol,institutional:{foreign_net:(i-10)*1000}};
}
let a=engine.selectDynamicLeaders({marketItems:market,basicsItems:basics,chipItems:chips,newsItems:[],limit:10,minSectors:6,maxPerSector:2,now:Date.parse('2026-08-07T10:00:00+08:00')});
const focus=market[0].symbol;
let b=engine.selectDynamicLeaders({marketItems:market,basicsItems:basics,chipItems:chips,newsItems:[{symbols:[focus],published_at:'2026-08-07T09:55:00+08:00',impact:'high',is_major:true,importance_score:100,title:'重大財報焦點'}],limit:10,minSectors:6,maxPerSector:2,now:Date.parse('2026-08-07T10:00:00+08:00')});
const counts={};for(const row of b)counts[row.sector]=(counts[row.sector]||0)+1;
console.log(JSON.stringify({len:b.length,sectors:Object.keys(counts).length,max:Math.max(...Object.values(counts)),firstA:a.map(x=>x.symbol),firstB:b.map(x=>x.symbol),focusIncluded:b.some(x=>x.symbol===focus)}));
"""
    out=subprocess.check_output(['node','-e',script],cwd=ROOT,text=True)
    result=json.loads(out)
    assert result['len']==10
    assert result['sectors']>=6
    assert result['max']<=2
    assert result['focusIncluded']
    assert result['firstA']!=result['firstB']
