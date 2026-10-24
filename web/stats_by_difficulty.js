/* 头部统计按难度独立；浏览筛选不改统计范围，B50仍为混合榜。 */
function renderStats(){
  const m=DATA.meta,songs=DATA.songs,box=document.getElementById('stats');
  const personal=!(PUBLIC && !hasUserData());
  const groups=['master','expert'].map(difficulty=>{
    const charts=songs.filter(s=>(s.difficulty||'master')===difficulty);
    const live=charts.filter(s=>!s.unrel);
    const fc=live.filter(s=>statusOf(s)==='fc').length;
    const quick=live.filter(s=>s.quick && statusOf(s)!=='fc');
    const fields=personal ? [
      ['g',fc,'已 FC','fc'],
      ['c',live.length-fc,'未 FC','unfc'],
      ['d',live.filter(s=>statusOf(s)==='tried').length,'打过未 FC','tried'],
      ['p',live.filter(s=>statusOf(s)==='never').length,'没打过','never'],
      ['v',charts.length-live.length,'未实装','unreleased'],
      ['y',quick.length,'能进 B50','quick'],
      ['p',quick.filter(s=>s.qtier==='g').length,'🟢 不越级','green'],
    ] : [
      ['c',charts.length,'谱面','total'],
      ['g',live.length,'已实装','released'],
      ['v',charts.length-live.length,'未实装','unreleased'],
      ['y',live.filter(s=>s.tips || (s.elems||[]).length).length,'有攻略','tips'],
      ['d',live.filter(s=>s.basis==='alias').length,'中文译名','alias'],
      ['p',live.filter(s=>s.bpmVar).length,'变速谱','bpmVar'],
    ];
    const master=difficulty==='master',color=master?'var(--purple)':'var(--pink)';
    const title=master?'MASTER':'EXPERT',name=master?'紫谱':'红谱';
    return `<div class="stat-group" data-difficulty="${difficulty}" style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;border-left:3px solid ${color};padding:3px 0 3px 10px">
      <div style="min-width:65px;color:${color};font-size:11px;font-weight:800;line-height:1.4">${title}<br><span style="font-size:10px;font-weight:500">${name}</span></div>
      ${fields.map(([cls,value,label,key])=>`<div class="stat ${cls}" data-metric="${key}" style="min-width:45px"><b>${value}</b><span>${label}</span></div>`).join('')}
    </div>`;
  });
  box.style.display='flex';box.style.flexDirection='column';box.style.alignItems='stretch';box.style.gap='9px';box.style.maxWidth='100%';
  box.innerHTML=groups.join('');
  const live=songs.filter(s=>!s.unrel),fc=live.filter(s=>statusOf(s)==='fc').length;
  document.getElementById('pfill').style.width=personal&&live.length?(fc/live.length*100).toFixed(1)+'%':'0%';
  const snapshot=PUBLIC?(suiteLoaded?(suiteTime?fmtTime(suiteTime):'未知'):(personal?'手动标记':'未导入')):m.snapshot;
  document.getElementById('snap').textContent='全量 '+songs.length+' 张谱面 · '+(personal?'快照 '+snapshot:'未导入成绩');
  document.getElementById('snap2').textContent=snapshot;
  document.getElementById('gen').textContent=m.generated;
  renderRuler();
}
