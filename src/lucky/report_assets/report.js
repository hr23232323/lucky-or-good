(function(){
const tip=document.getElementById('tip');
function place(e){const pad=14;let x=e.clientX+pad,y=e.clientY+pad;
 const r=tip.getBoundingClientRect();if(x+r.width>innerWidth-8)x=e.clientX-r.width-pad;
 if(y+r.height>innerHeight-8)y=e.clientY-r.height-pad;tip.style.left=x+'px';tip.style.top=y+'px';}
function show(lines,e){tip.replaceChildren();lines.forEach((t,i)=>{const d=document.createElement('div');
 d.className=i===0?'v':(i===1?'n':'r');d.textContent=t;tip.appendChild(d);});tip.style.display='block';
 if(e&&e.clientX!==undefined)place(e);}
function hide(){tip.style.display='none';}
document.querySelectorAll('.mark').forEach(g=>{const lines=JSON.parse(g.dataset.tip);
 g.addEventListener('pointermove',e=>show(lines,e));g.addEventListener('pointerleave',hide);
 g.addEventListener('focus',()=>{show(lines);const b=g.getBoundingClientRect();
  tip.style.left=(b.left+20)+'px';tip.style.top=(b.bottom+4)+'px';});g.addEventListener('blur',hide);});
const raw=document.getElementById('equity-data');if(!raw)return;
const data=JSON.parse(raw.textContent);const svg=document.getElementById('equity');
const hit=document.getElementById('eq-hit');const cross=document.getElementById('crosshair');
const lines=[...svg.querySelectorAll('.line')];const n=data.dates.length;
const color=g=>getComputedStyle(svg).getPropertyValue(g==='bench'?'--muted':'--'+g).trim();
hit.addEventListener('pointermove',e=>{const pt=svg.createSVGPoint();pt.x=e.clientX;pt.y=e.clientY;
 const p=pt.matrixTransform(svg.getScreenCTM().inverse());
 const k=Math.max(0,Math.min(n-1,Math.round((p.x-data.x0)/(data.x1-data.x0)*(n-1))));
 const x=data.x0+k/(n-1)*(data.x1-data.x0);cross.setAttribute('x1',x);cross.setAttribute('x2',x);
 cross.style.visibility='visible';
 const rows=data.series.map((s,i)=>({i,name:s.name,group:s.group,v:s.v[k]})).sort((a,b)=>b.v-a.v);
 const best=rows[0];lines.forEach(l=>l.classList.toggle('hot',+l.dataset.i===best.i));
 tip.replaceChildren();const h=document.createElement('div');h.className='r';h.textContent=data.dates[k];
 tip.appendChild(h);
 const shown=rows.slice(0,6);const b=rows.find(r=>r.group==='bench');if(b&&!shown.includes(b))shown.push(b);
 shown.forEach(r=>{const row=document.createElement('div');row.className='row';
  const key=document.createElement('span');key.className='k';key.style.background=color(r.group);
  const v=document.createElement('strong');v.textContent='$'+r.v.toFixed(2);
  const nm=document.createElement('span');nm.className='n';nm.textContent=r.name;
  row.append(key,v,nm);tip.appendChild(row);});
 if(rows.length>shown.length){const m=document.createElement('div');m.className='r';
  m.textContent='+'+(rows.length-shown.length)+' more';tip.appendChild(m);}
 tip.style.display='block';place(e);});
hit.addEventListener('pointerleave',()=>{hide();cross.style.visibility='hidden';
 lines.forEach(l=>l.classList.remove('hot'));});
})();
