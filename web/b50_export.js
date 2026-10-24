/*__B50_EXPORT_BEGIN__*/
// Self-contained PNG export. Draws the displayed ranking; never changes its scores.
let b50ExportBusy = false;
let b50ExportURL = null;
function b50ExportName(){
  try { return localStorage.getItem('pjsk_b50_export_name') || '我的 B50'; }
  catch (_) { return '我的 B50'; }
}
function b50ExportModel(name){
  const ranking = (A && A.b50) || {};
  const songs = DATA.songs || [];
  const entries = (ranking.list || []).slice(0, 50).map((entry, index) => {
    const key = entry.chartId == null ? entry.musicId : entry.chartId;
    const song = songs.find(s => String(s.id) === String(key)
      && (!entry.difficulty || !s.difficulty || s.difficulty === entry.difficulty)) || {};
    return { rank:index+1, chartId:key, musicId:song.musicId == null ? entry.musicId : song.musicId,
      difficulty:entry.difficulty || song.difficulty || 'master',
      title:song.disp || song.jp || String(entry.musicId), abn:song.abn || '',
      level:entry.lv == null ? song.lv : entry.lv,
      teishu:entry.teishu, score:entry.score, ap:!!entry.ap };
  });
  if (!entries.length) throw new Error('还没有可导出的 FC／AP 谱面，请先导入成绩或标记 FC。');
  if (entries.some(e => !Number.isFinite(e.teishu) || !Number.isFinite(e.score)))
    throw new Error('榜单中有缺失的定数，请刷新榜单后重试。');
  const snapshot = PUBLIC && typeof suiteTime !== 'undefined' && suiteTime
    ? fmtTime(suiteTime) : ((DATA.meta || {}).snapshot || '手动标记');
  return {name:(name || b50ExportName()).trim().slice(0,40) || '我的 B50', snapshot,
    rating:ranking.rating, count:entries.length, entries,
    scope:songs.some(s=>s.difficulty==='expert') || entries.some(e=>e.difficulty==='expert') ? 'EXPERT + MASTER' : 'MASTER',
    generated:new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date())};
}
function b50Cover(url){
  return new Promise(resolve => {
    const img = new Image();
    let settled = false;
    const finish = value => { if (!settled){ settled=true; clearTimeout(timer); img.onload=img.onerror=null; resolve(value); } };
    const timer = setTimeout(()=>{finish(null);img.src='';},7000);
    img.crossOrigin='anonymous'; img.referrerPolicy='no-referrer';
    img.onload=()=>finish(img.naturalWidth ? img : null);
    img.onerror=()=>finish(null); img.src=url;
  });
}
async function b50LoadCover(entry){
  if (!entry.abn || entry.abn==='noimg') return null;
  const asset = encodeURIComponent(entry.abn);
  const sources = PUBLIC
    ? [COVER_CN(asset),COVER_JP(asset)]
    : [new URL('covers/'+asset+'.webp',location.href).href];
  for (const source of sources){ const img=await b50Cover(source); if (img) return img; }
  return null;
}
function b50Round(ctx,x,y,w,h,r){
  ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();
}
function b50Text(ctx,text,x,y,maxWidth){
  const chars=Array.from(String(text));
  if(ctx.measureText(chars.join('')).width<=maxWidth){ctx.fillText(chars.join(''),x,y);return;}
  while(chars.length && ctx.measureText(chars.join('')+'…').width>maxWidth) chars.pop();
  ctx.fillText(chars.join('')+'…',x,y);
}
function b50Draw(model,covers){
  const W=1200,M=36,G=16,CW=(W-2*M-2*G)/3,CH=126,TOP=270;
  const rows=Math.ceil(model.entries.length/3),H=TOP+rows*(CH+G)+106;
  const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;
  const ctx=canvas.getContext('2d');if(!ctx)throw new Error('当前浏览器无法生成图片。');
  const font=(size,weight=600)=>{ctx.font=`${weight} ${size}px "Segoe UI","Microsoft YaHei",sans-serif`;};
  const background=ctx.createLinearGradient(0,0,W,H);
  background.addColorStop(0,'#e9fbff');background.addColorStop(.45,'#fff5fd');background.addColorStop(1,'#e6fcf8');
  ctx.fillStyle=background;ctx.fillRect(0,0,W,H);
  // Soft crystal ribbons, generated locally rather than fetched as decoration.
  const colors=['#b4eeff','#f0c3ff','#fff2b5','#b9fff1'];
  for(let i=0;i<24;i++){
    const x=(i*367)%W,y=(i*541)%H;
    ctx.globalAlpha=.24;ctx.fillStyle=colors[i%colors.length];ctx.beginPath();
    ctx.moveTo(x-160,y);ctx.lineTo(x+175,y-110);ctx.lineTo(x+45,y+300);ctx.closePath();ctx.fill();
  }
  ctx.globalAlpha=1;
  ctx.fillStyle='#66778c';font(17,700);ctx.fillText('PJSK  /  BEST 50',M,43);
  ctx.fillStyle='#1c2540';font(39,800);b50Text(ctx,model.name,M,101,750);
  ctx.fillStyle='#596980';font(17,500);ctx.fillText('成绩快照  '+model.snapshot,M,137);
  ctx.fillText('导出时间  '+model.generated+'  UTC+8',M,165);
  ctx.fillStyle='#7950c6';font(16,800);ctx.fillText(model.scope+'  ·  '+model.count+' / 50 张谱面',M,204);
  ctx.fillStyle='#77829a';font(14,500);ctx.fillText('曲目顺序与当前 B50 榜单一致  ·  社区定数 → 排名计分',M,234);
  const badge=ctx.createLinearGradient(925,35,1140,207);badge.addColorStop(0,'#a9e8ff');badge.addColorStop(.5,'#dcbbff');badge.addColorStop(1,'#ffcee9');
  ctx.save();ctx.shadowColor='#a17bb955';ctx.shadowBlur=24;ctx.shadowOffsetY=8;
  ctx.fillStyle=badge;b50Round(ctx,900,38,264,185,30);ctx.fill();ctx.restore();
  ctx.fillStyle='#ffffffdc';b50Round(ctx,908,46,248,169,25);ctx.fill();
  ctx.textAlign='center';ctx.fillStyle='#68738e';font(17,800);ctx.fillText('B50 RATING',1032,86);
  ctx.fillStyle='#7250bd';font(70,800);ctx.fillText(model.rating==null?'—':Number(model.rating).toFixed(2),1032,164);
  ctx.fillStyle='#8690a3';font(13,500);ctx.fillText(model.count<50?'未满 50 张谱面':'FC / ALL PERFECT',1032,193);ctx.textAlign='left';
  model.entries.forEach((entry,index)=>{
    const x=M+(index%3)*(CW+G),y=TOP+Math.floor(index/3)*(CH+G);
    ctx.save();ctx.shadowColor='#8b82a52d';ctx.shadowBlur=13;ctx.shadowOffsetY=4;
    ctx.fillStyle='#ffffffed';b50Round(ctx,x,y,CW,CH,13);ctx.fill();ctx.restore();
    const purple=entry.difficulty==='expert'?'#ed4771':'#ad45df';
    ctx.fillStyle=purple;b50Round(ctx,x,y,5,CH,2);ctx.fill();
    const ix=x+13,iy=y+13,sz=100;
    ctx.save();b50Round(ctx,ix,iy,sz,sz,9);ctx.clip();
    if(covers[index])ctx.drawImage(covers[index],ix,iy,sz,sz);
    else{
      ctx.fillStyle='#eef0f8';ctx.fillRect(ix,iy,sz,sz);ctx.fillStyle='#a0a9c2';font(28,800);ctx.textAlign='center';ctx.fillText('♪',ix+sz/2,iy+48);font(11,500);ctx.fillText('暂无封面',ix+sz/2,iy+72);ctx.textAlign='left';
    }
    ctx.restore();
    ctx.fillStyle=purple;b50Round(ctx,ix-4,iy-4,42,24,10);ctx.fill();ctx.fillStyle='#fff';font(12,800);ctx.fillText('Lv'+entry.level,ix+1,iy+13);
    const tx=x+125,tw=CW-137;
    ctx.fillStyle='#8c97aa';font(12,700);ctx.fillText('#'+String(entry.rank).padStart(2,'0'),tx,y+23);
    ctx.fillStyle=purple;font(10,800);ctx.textAlign='right';ctx.fillText(entry.difficulty.toUpperCase(),x+CW-12,y+23);ctx.textAlign='left';
    ctx.fillStyle='#4c4364';font(20,800);ctx.fillText(Number(entry.teishu).toFixed(2)+' → '+Number(entry.score).toFixed(2),tx,y+51);
    ctx.fillStyle='#202b40';font(18,700);b50Text(ctx,entry.title,tx,y+79,tw);
    ctx.fillStyle=entry.ap?'#08a9ae':'#df5eac';font(16,800);ctx.fillText(entry.ap?'ALL PERFECT!':'FULL COMBO!',tx,y+106);
  });
  const fy=TOP+rows*(CH+G)+14;
  ctx.fillStyle='#68758b';font(14,600);ctx.fillText('FC = 社区定数     AP = 社区定数 + 1.5     B50 = 前 50 张谱面计分之和 ÷ 50',M,fy);
  const missing=covers.filter(img=>!img).length;
  font(12,500);ctx.fillStyle='#8c97a8';ctx.fillText('个人差与游玩次数修正不参与 B50'+(missing?'  ·  '+missing+' 张封面暂缺，已使用占位图':''),M,fy+25);
  ctx.fillStyle='#8791a5';font(12,700);ctx.fillText('PJSK 定数表  ·  va1z.xyz',M,fy+52);
  return {canvas,missing};
}
function b50ClosePreview(){
  document.removeEventListener('keydown',b50PreviewEscape);
  const previous=document.getElementById('b50ExportPreview');if(previous)previous.remove();
  if(b50ExportURL){URL.revokeObjectURL(b50ExportURL);b50ExportURL=null;}
}
function b50PreviewEscape(event){if(event.key==='Escape')b50ClosePreview();}
function b50Preview(url,filename,missing){
  const mask=document.createElement('div');mask.id='b50ExportPreview';
  mask.setAttribute('role','dialog');mask.setAttribute('aria-modal','true');mask.setAttribute('aria-label','B50 图片预览');
  mask.style.cssText='position:fixed;inset:0;z-index:10000;background:#080e20c9;display:flex;align-items:center;justify-content:center;padding:18px';
  mask.innerHTML=`<div style="background:var(--bg,#fff);color:var(--fg,#233);border-radius:16px;padding:18px;width:600px;max-width:100%;max-height:94vh;overflow:auto">
    <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px"><b>B50 图片已生成</b><button id="b50PreviewClose" aria-label="关闭预览">关闭</button></div>
    <div style="font-size:13px;margin-bottom:12px">${missing?missing+' 张封面暂缺，可稍后重试。':'封面已全部加载。'}已开始下载；手机也可长按图片保存。</div>
    <a id="b50SaveAgain" style="display:inline-block;margin-bottom:12px;color:var(--cyan,#377da0)" href="${url}" download="${filename}">再次保存 PNG</a>
    <img src="${url}" alt="完整 B50 榜单图片" style="width:100%;height:auto;display:block;border-radius:8px"></div>`;
  document.body.appendChild(mask);mask.querySelector('#b50PreviewClose').onclick=b50ClosePreview;
  mask.onclick=event=>{if(event.target===mask)b50ClosePreview();};
  document.addEventListener('keydown',b50PreviewEscape);
}
async function exportB50PNG(options={}){
  if(b50ExportBusy)return null;
  b50ExportBusy=true;
  const button=document.getElementById('b50Export'),status=document.getElementById('b50ExportStatus');
  const announce=text=>{if(status)status.textContent=text;};
  if(button)button.disabled=true;
  try{
    const nameInput=document.getElementById('b50ExportName');
    const model=b50ExportModel(options.name || (nameInput && nameInput.value));
    announce('正在加载封面…');
    const covers=new Array(model.entries.length);let cursor=0,complete=0;
    await Promise.all(Array.from({length:Math.min(8,covers.length)},async()=>{
      while(cursor<covers.length){const index=cursor++;covers[index]=await b50LoadCover(model.entries[index]);complete++;announce(`封面 ${complete} / ${covers.length}`);}
    }));
    const {canvas,missing}=b50Draw(model,covers);
    const blob=await new Promise((resolve,reject)=>{
      try{canvas.toBlob(value=>value?resolve(value):reject(new Error('图片编码失败，请重试。')),'image/png');}
      catch(_){reject(new Error('封面无法用于导出，请重试或换个浏览器。'));}
    });
    b50ClosePreview();b50ExportURL=URL.createObjectURL(blob);
    const filename='PJSK-B50-'+model.generated.replace(/[^0-9]/g,'')+'.png';
    const report={count:model.count,rating:model.rating,width:canvas.width,height:canvas.height,missingCovers:missing,filename,entries:model.entries};
    window.PJSKB50Export.lastReport=report;
    if(options.download!==false){
      const a=document.createElement('a');a.href=b50ExportURL;a.download=filename;document.body.appendChild(a);a.click();a.remove();
      b50Preview(b50ExportURL,filename,missing);
    }
    announce(missing?`已导出，${missing} 张封面使用占位图`:'已导出 PNG');
    return {blob,canvas,report,url:b50ExportURL};
  }catch(error){announce(error.message || '导出失败，请重试。');if(options.download===false)throw error;return null;}
  finally{b50ExportBusy=false;const current=document.getElementById('b50Export');if(current)current.disabled=false;}
}
window.PJSKB50Export={export:exportB50PNG,readModel:b50ExportModel,lastReport:null};
/*__B50_EXPORT_END__*/
