/* Progressive enhancement only. Authorization, pricing and stock live on the server. */
/* A looping background video is decoration, not content: hold it still for anyone
   who has asked the system for reduced motion. */
if(matchMedia('(prefers-reduced-motion: reduce)').matches){document.querySelectorAll('video.v-media').forEach(video=>{video.removeAttribute('autoplay');video.pause();});}
/* Preloader: leave as soon as the page is ready, but hold a beat so a fast load
   does not read as a flicker. The CSS clears the overlay on its own if this never runs. */
(()=>{const overlay=document.querySelector('[data-loader-overlay]');if(!overlay)return;const start=performance.now();const dismiss=()=>{overlay.classList.add('is-done');try{sessionStorage.setItem('verda-seen','1');}catch(e){}};const HOLD=5000;const settle=()=>setTimeout(dismiss,Math.max(0,HOLD-(performance.now()-start)));document.readyState==='complete'?settle():addEventListener('load',settle,{once:true});})();
document.querySelectorAll('[data-theme-toggle]').forEach(button=>button.addEventListener('click',()=>{const root=document.documentElement;const system=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';const current=root.getAttribute('data-theme')||system;const next=current==='dark'?'light':'dark';if(next===system){root.removeAttribute('data-theme');}else{root.setAttribute('data-theme',next);}try{next===system?localStorage.removeItem('verda-theme'):localStorage.setItem('verda-theme',next);}catch(e){}}));
document.querySelectorAll('[data-language-switch]').forEach(select=>select.addEventListener('change',()=>location.assign(select.value)));
/* Menus. The staff sidebar only toggles. The public menu is a full-screen overlay
   on phones, so it also locks scroll, makes everything behind it inert (so focus
   cannot wander underneath), and closes on Escape or when widened to desktop. */
const behindOverlay=()=>document.querySelectorAll('main,footer,.site-header>.brand,.site-header>.header-actions,.site-header>.menu-toggle');
function setMenu(button,menu,open){
  menu.classList.toggle('open',open);
  button.setAttribute('aria-expanded',String(open));
  if(menu.id!=='public-nav')return;
  document.documentElement.classList.toggle('menu-open',open);
  behindOverlay().forEach(el=>open?el.setAttribute('inert',''):el.removeAttribute('inert'));
  if(open){menu.querySelector('[data-menu-close]')?.focus({preventScroll:true});}
  else{button.focus({preventScroll:true});}
}
document.querySelectorAll('.menu-toggle').forEach(button=>button.addEventListener('click',()=>{const menu=document.getElementById(button.getAttribute('aria-controls'));if(menu)setMenu(button,menu,!menu.classList.contains('open'));}));
const publicMenu=document.getElementById('public-nav'),publicToggle=document.querySelector('.menu-toggle[aria-controls="public-nav"]');
if(publicMenu&&publicToggle){
  publicMenu.querySelectorAll('[data-menu-close]').forEach(close=>close.addEventListener('click',()=>setMenu(publicToggle,publicMenu,false)));
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&publicMenu.classList.contains('open'))setMenu(publicToggle,publicMenu,false);});
  matchMedia('(min-width: 901px)').addEventListener('change',wide=>{if(wide.matches&&publicMenu.classList.contains('open'))setMenu(publicToggle,publicMenu,false);});
}
document.querySelectorAll('[data-back]').forEach(button=>button.addEventListener('click',()=>history.length>1?history.back():location.assign('/')));
document.querySelectorAll('[data-auto-filter] select,[data-auto-filter] input').forEach(control=>control.addEventListener('change',()=>control.form.submit()));
const slotGrid=document.querySelector('.slot-grid');
function paintSpan(){if(!slotGrid)return;const hours=Number(slotGrid.dataset.duration||1);const start=slotGrid.querySelector('input[name="hour"]:checked');slotGrid.querySelectorAll('.time-slot').forEach(slot=>slot.classList.remove('within-booking'));if(!start)return;const order=Array.from(slotGrid.querySelectorAll('.time-slot'));const index=order.findIndex(slot=>slot.dataset.hour===start.value);for(let step=1;step<hours&&index+step<order.length;step++)order[index+step].classList.add('within-booking');}
document.querySelectorAll('input[name="hour"][data-price]').forEach(radio=>radio.addEventListener('change',()=>{for(const key of ['price','original','discount','date','end']){const output=document.querySelector(`[data-summary="${key}"]`);if(output){const value=radio.dataset[key];output.textContent=['price','original','discount'].includes(key)?`${Number(value).toLocaleString('en-US')} IQD`:value;output.dir='ltr';}}paintSpan();}));
paintSpan();
const deliveryChoices=document.querySelectorAll('[data-delivery-choice]');
function updateDelivery(){const delivery=document.querySelector('[data-delivery-choice]:checked')?.value==='delivery';const fields=document.querySelector('[data-delivery-fields]');if(fields){fields.hidden=!delivery;fields.querySelectorAll('input,textarea').forEach(el=>{el.disabled=!delivery;el.required=delivery;});}const fee=document.querySelector('[data-delivery-fee]');const total=document.querySelector('[data-checkout-total]');if(fee&&total){const amount=delivery?Number(fee.dataset.deliveryFee):0;fee.textContent=`${amount.toLocaleString('en-US')} IQD`;total.textContent=`${(Number(total.dataset.checkoutTotal)+amount).toLocaleString('en-US')} IQD`;}}
deliveryChoices.forEach(input=>input.addEventListener('change',updateDelivery));if(deliveryChoices.length)updateDelivery();
document.querySelectorAll('[data-remove-item]').forEach(button=>button.addEventListener('click',()=>{button.form.querySelector('input[name="quantity"]').value=0;button.removeAttribute('name');}));
/* Guard one-click destructive row actions. Without JS the form still submits,
   so this adds a check rather than being the thing that makes it work. */
document.querySelectorAll('[data-confirm]').forEach(control=>control.addEventListener('click',event=>{if(!confirm(control.dataset.confirm))event.preventDefault();}));
/* Declining needs a reason. The field carries a usable default so the form works
   with scripting off; this just lets staff replace it without leaving the list. */
document.querySelectorAll('[data-reason-prompt]').forEach(button=>button.addEventListener('click',event=>{const field=button.form&&button.form.querySelector('input[name="reason"]');const given=prompt(button.dataset.reasonPrompt,field?field.value:'');if(given===null){event.preventDefault();return;}const text=given.trim();if(field&&text)field.value=text.slice(0,255);}));
document.querySelectorAll('[data-print]').forEach(button=>button.addEventListener('click',()=>window.print()));
document.querySelectorAll('[data-select-all]').forEach(input=>input.addEventListener('change',()=>document.querySelectorAll('input[name="ids"]').forEach(item=>item.checked=input.checked)));
document.querySelectorAll('[data-catalog-search],[data-catalog-category]').forEach(input=>input.addEventListener('input',()=>{const query=(document.querySelector('[data-catalog-search]')?.value||'').toLocaleLowerCase();const category=document.querySelector('[data-catalog-category]')?.value||'';document.querySelectorAll('[data-product-name]').forEach(card=>{card.hidden=!card.dataset.productName.toLocaleLowerCase().includes(query)||(category&&card.dataset.category!==category);});}));
const quick=document.querySelector('[data-quick-sale]');
if(quick){const fmt=(n,code)=>code==='USD'?`${n<0?'−':''}$${(Math.abs(n)/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`:`${n.toLocaleString('en-US')} IQD`;const toMinor=(text,code)=>{const v=Number(String(text||'0').replace(/,/g,''));return Number.isFinite(v)?Math.round(v*(code==='USD'?100:1)):0;};const rows=[...quick.querySelectorAll('[data-quick-item]')];const basket=quick.querySelector('[data-basket]');const template=quick.querySelector('[data-line-template]');const input=row=>row.querySelector('[data-unit-price]');const priceOf=row=>Number(input(row).dataset.unitPrice);const codeOf=row=>input(row).dataset.currency||'IQD';const qtyOf=row=>Number(input(row).value||0);const maxOf=row=>Number(input(row).dataset.max||999);
const update=()=>{const totals={IQD:0,USD:0};basket.replaceChildren();rows.forEach((row,index)=>{const q=qtyOf(row),price=priceOf(row),code=codeOf(row);const count=row.querySelector('[data-count]');count.textContent=q;count.hidden=!q;row.classList.toggle('is-picked',q>0);row.querySelector('[data-add]').disabled=q>=maxOf(row);if(!q)return;totals[code]+=q*price;const line=template.content.firstElementChild.cloneNode(true);line.dataset.index=index;line.querySelector('[data-name]').textContent=row.dataset.productName;line.querySelector('[data-each]').textContent=`${fmt(price,code)} × ${q}`;line.querySelector('[data-qty]').textContent=q;line.querySelector('[data-inc]').disabled=q>=maxOf(row);line.querySelector('[data-line-total]').textContent=fmt(q*price,code);basket.append(line);});quick.querySelector('[data-basket-empty]').hidden=basket.children.length>0;const complete=quick.querySelector('[data-complete]');if(complete)complete.disabled=!basket.children.length;const kind=quick.querySelector('[name="discount_kind"]')?.value;const discountCode=quick.querySelector('[name="discount_currency"]')?.value||'IQD';const picker=quick.querySelector('[data-discount-currency]');if(picker)picker.hidden=kind==='percentage';const raw=quick.querySelector('[name="discount"]')?.value;for(const code of ['IQD','USD']){const used=totals[code]>0||(code==='IQD'&&!totals.USD);quick.querySelectorAll(`[data-currency-row="${code}"]`).forEach(el=>el.hidden=!used);const sub=quick.querySelector(`[data-subtotal="${code}"]`);if(sub)sub.textContent=fmt(totals[code],code);let off=0;if(kind==='percentage')off=Math.round(totals[code]*Number(raw||0)/100);else if(code===discountCode)off=toMinor(raw,code);const out=quick.querySelector(`[data-quick-total="${code}"]`);if(out)out.textContent=fmt(Math.max(0,totals[code]-off),code);}};
const setQty=(row,q)=>{input(row).value=Math.max(0,Math.min(maxOf(row),q));update();};
quick.querySelector('[data-quick-grid]')?.addEventListener('click',event=>{const button=event.target.closest('[data-add]');if(!button||button.disabled)return;const row=button.closest('[data-quick-item]');setQty(row,qtyOf(row)+1);button.classList.remove('is-bumped');void button.offsetWidth;button.classList.add('is-bumped');});
basket.addEventListener('click',event=>{const line=event.target.closest('[data-index]');if(!line)return;const row=rows[Number(line.dataset.index)];if(event.target.closest('[data-inc]'))setQty(row,qtyOf(row)+1);else if(event.target.closest('[data-dec]'))setQty(row,qtyOf(row)-1);});
quick.addEventListener('input',event=>{if(event.target.matches('[name="discount"]'))update();});quick.addEventListener('change',event=>{if(event.target.matches('[name="discount_kind"],[name="discount_currency"]'))update();});
quick.querySelector('[data-clear-basket]')?.addEventListener('click',()=>{rows.forEach(row=>input(row).value=0);update();});
const scanner=quick.querySelector('[data-quick-scan]');scanner?.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();const code=scanner.value.trim();const row=rows.find(el=>el.dataset.barcode===code);const status=quick.querySelector('[data-scan-status]');if(row){setQty(row,qtyOf(row)+1);row.hidden=false;row.scrollIntoView({block:'nearest'});status.textContent=row.dataset.productName;}else{status.textContent=status.dataset.notFound;}scanner.value='';}});update();}
document.querySelectorAll('[data-tab-search]').forEach(input=>input.addEventListener('input',()=>{const query=input.value.trim().toLocaleLowerCase();document.querySelectorAll('[data-tab-name]').forEach(card=>{card.hidden=!!query&&!card.dataset.tabName.toLocaleLowerCase().includes(query);});}));
document.querySelectorAll('[data-elapsed]').forEach(node=>{const start=Date.parse(node.dataset.start+'Z');const end=node.dataset.end?Date.parse(node.dataset.end+'Z'):null;const paint=()=>{const seconds=Math.max(0,Math.floor(((end||Date.now())-start)/1000));node.textContent=[Math.floor(seconds/3600),Math.floor(seconds/60)%60,seconds%60].map(n=>String(n).padStart(2,'0')).join(':');};paint();if(!end)setInterval(paint,1000);});
if(document.querySelector('[data-auto-print="true"]')){const key='verda-printed-'+document.querySelector('[data-auto-print]').dataset.reference;if(!sessionStorage.getItem(key)){sessionStorage.setItem(key,'1');window.addEventListener('load',()=>window.print());}}

/* ── Mobile enhancements ── */

/* Scroll reveal: animate tiles, cards, panels as they enter the viewport */
if('IntersectionObserver' in window&&!matchMedia('(prefers-reduced-motion:reduce)').matches){
  const srTargets=document.querySelectorAll('.site-public .v-tile,.site-public .product-card,.site-public .court-card,.site-public .panel,.site-public .v-hero-in,.site-public .section-heading,.v-shead,.site-public .page-heading,.site-public .confirmation,.site-public .v-bento');
  const io=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('v-in');io.unobserve(e.target);}});},{threshold:.08,rootMargin:'0px 0px -36px 0px'});
  srTargets.forEach((el,i)=>{
    el.classList.add('v-sr');
    const siblings=el.parentElement?Array.from(el.parentElement.children).filter(c=>c.classList.contains(el.classList[0])):[];
    const idx=siblings.indexOf(el);
    if(idx>0&&idx<5)el.classList.add('v-sr-d'+idx);
    io.observe(el);
  });
}

/* Submit loading state — show spinner, disable button to prevent double-tap */
document.querySelectorAll('.site-public form').forEach(form=>{
  form.addEventListener('submit',function(){
    const btn=this.querySelector('button[type=submit],button:not([type=button]):not([type=reset])');
    if(!btn||btn.disabled)return;
    const orig=btn.innerHTML;
    btn.disabled=true;
    btn.innerHTML='<span class="v-btn-spinner"></span>';
    setTimeout(()=>{btn.disabled=false;btn.innerHTML=orig;},10000);
  });
});

/* Sticky bottom booking bar — appears on mobile when a slot is selected */
(()=>{
  const grid=document.querySelector('.site-public .slot-grid');
  if(!grid)return;
  const bar=document.createElement('div');
  bar.className='v-book-bar site-public';
  bar.innerHTML='<div class="v-book-bar-info"><small id="vbb-time"></small><strong id="vbb-price">—</strong></div><button type="button" class="btn btn-primary" id="vbb-btn"></button>';
  document.body.appendChild(bar);
  const timeEl=bar.querySelector('#vbb-time');
  const priceEl=bar.querySelector('#vbb-price');
  const bookBtn=bar.querySelector('#vbb-btn');
  bookBtn.textContent=document.documentElement.lang==='ar'?'احجز الآن ←':'Book now →';
  /* Submit the booking form itself. If the name or phone is still empty, take the
     guest to that field instead of failing silently. */
  bookBtn.addEventListener('click',()=>{
    const form=document.getElementById('booking-form');
    if(!form)return;
    if(!form.checkValidity()){
      const missing=form.querySelector(':invalid');
      if(missing){missing.scrollIntoView({behavior:'smooth',block:'center'});setTimeout(()=>{missing.focus({preventScroll:true});form.reportValidity();},400);}
      return;
    }
    const submitter=form.querySelector('button:not([type=button]):not([type=reset])');
    if(form.requestSubmit)form.requestSubmit(submitter||undefined);else form.submit();
  });
  grid.addEventListener('change',e=>{
    if(!e.target.matches('input[name="hour"]'))return;
    const r=e.target;
    timeEl.textContent=r.closest('.time-slot').querySelector('b').textContent;
    const price=Number(r.dataset.price||0);
    priceEl.textContent=price?price.toLocaleString('en-US')+' IQD':'—';
    bar.classList.add('is-open');
  });
})();

/* Toast helper (used by other scripts) */
window.vToast=function(msg){
  let t=document.getElementById('v-toast-el');
  if(!t){t=document.createElement('div');t.id='v-toast-el';t.className='v-toast site-public';document.body.appendChild(t);}
  t.textContent=msg;t.classList.add('v-toast-show');
  clearTimeout(t._t);t._t=setTimeout(()=>t.classList.remove('v-toast-show'),2600);
};

/* ── Booking start reminders: "it's their time" cards on staff screens ── */
(()=>{const stack=document.getElementById('due-bookings');if(!stack)return;
let labels={accept:'Accept & start',decline:'Decline',open:'Open bill',error:'Could not start. Check the cashier page.'};
const SEEN='verda-due-seen';const seen=new Set((()=>{try{return JSON.parse(sessionStorage.getItem(SEEN)||'[]')}catch(e){return []}})());
const remember=()=>{try{sessionStorage.setItem(SEEN,JSON.stringify([...seen]))}catch(e){}};
const chime=()=>{try{const ctx=new (window.AudioContext||window.webkitAudioContext)();[[0,784],[.18,1046]].forEach(([d,f])=>{const o=ctx.createOscillator(),g=ctx.createGain();o.type='sine';o.frequency.value=f;g.gain.setValueAtTime(.0001,ctx.currentTime+d);g.gain.exponentialRampToValueAtTime(.22,ctx.currentTime+d+.02);g.gain.exponentialRampToValueAtTime(.0001,ctx.currentTime+d+.45);o.connect(g).connect(ctx.destination);o.start(ctx.currentTime+d);o.stop(ctx.currentTime+d+.5);});}catch(e){}};
const key=()=>(window.crypto&&crypto.randomUUID)?crypto.randomUUID():`${Date.now()}-${Math.random().toString(36).slice(2)}`;
const send=(url)=>fetch(url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','Accept':'application/json','X-CSRFToken':stack.dataset.csrf,'Idempotency-Key':key()},body:'{}'});
const reason=async r=>{try{return (await r.json()).error||labels.error}catch(e){return labels.error}};
function card(b){const el=document.createElement('article');el.className='due-card';el.dataset.id=b.id;el.setAttribute('role','alertdialog');el.setAttribute('aria-label',b.title);
el.innerHTML='<span class="due-pulse" aria-hidden="true"></span><div class="due-body"><strong class="due-title"></strong><span class="due-when"></span><a class="due-phone" dir="ltr"></a></div><div class="due-actions"><button type="button" class="btn btn-primary" data-accept></button><button type="button" class="btn btn-outline" data-decline></button></div><p class="due-error" hidden></p>';
el.querySelector('.due-title').textContent=b.title;el.querySelector('.due-when').textContent=b.when;const phone=el.querySelector('.due-phone');phone.textContent=b.phone;phone.href='tel:'+b.phone;
const accept=el.querySelector('[data-accept]'),decline=el.querySelector('[data-decline]'),error=el.querySelector('.due-error');accept.textContent=labels.accept;decline.textContent=labels.decline;
const busy=on=>{accept.disabled=decline.disabled=on;el.classList.toggle('is-busy',on);};const fail=msg=>{error.textContent=msg;error.hidden=false;busy(false);};
accept.addEventListener('click',async()=>{busy(true);try{const r=await send(`/pos/bookings/${b.id}/start`);if(r.ok){location.href=(await r.json()).url;}else fail(await reason(r));}catch(e){fail(labels.error)}});
decline.addEventListener('click',async()=>{busy(true);try{const r=await send(`/pos/bookings/${b.id}/decline`);if(r.ok){el.classList.add('is-leaving');setTimeout(()=>el.remove(),250);}else fail(await reason(r));}catch(e){fail(labels.error)}});
return el;}
function toast(s){const el=document.createElement('div');el.className='due-toast';el.setAttribute('role','status');const p=document.createElement('p');p.textContent=s.text;const a=document.createElement('a');a.href=s.url;a.textContent=labels.open+' ↗';el.append(p,a);stack.append(el);setTimeout(()=>el.remove(),12000);}
async function poll(){try{const r=await fetch(stack.dataset.dueUrl,{credentials:'same-origin',headers:{'Accept':'application/json'}});
if(!r.ok||!(r.headers.get('content-type')||'').includes('json'))return;const data=await r.json();labels=Object.assign(labels,data.labels||{});
const ids=new Set(data.due.map(b=>String(b.id)));stack.querySelectorAll('.due-card').forEach(c=>{if(!ids.has(c.dataset.id))c.remove();});
let fresh=false;data.due.forEach(b=>{if(!stack.querySelector(`.due-card[data-id="${b.id}"]`))stack.prepend(card(b));if(!seen.has(b.id)){seen.add(b.id);fresh=true;}});
if(fresh){remember();chime();}
data.stopped.forEach(toast);if(data.stopped.length&&location.pathname.startsWith('/pos'))setTimeout(()=>location.reload(),2500);}catch(e){}}
poll();setInterval(poll,20000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
window.verdaCheckBookings=poll;})();

/* Booked session countdown: when it reaches zero, ask the server to stop it and refresh. */
document.querySelectorAll('[data-remaining]').forEach(node=>{const end=Date.parse(node.dataset.end+'Z');let done=false;
const paint=()=>{const s=Math.max(0,Math.floor((end-Date.now())/1000));node.textContent=[Math.floor(s/3600),Math.floor(s%3600/60),s%60].map(v=>String(v).padStart(2,'0')).join(':');
if(!s&&!done){done=true;fetch('/pos/api/due',{credentials:'same-origin',headers:{'Accept':'application/json'}}).finally(()=>setTimeout(()=>location.reload(),800));}};paint();setInterval(paint,1000);});

/* Staff form: choosing a role presets the permission ticks (still editable). */
document.querySelectorAll('[data-role-presets]').forEach(grid=>{const form=grid.closest('form');const role=form&&form.querySelector('select[name="role"]');if(!role)return;
const boxes=[...grid.querySelectorAll('input[name="permissions"]')];const cashier=(grid.dataset.cashier||'').split(' ');
role.addEventListener('change',()=>{if(role.value==='cashier')boxes.forEach(b=>b.checked=cashier.includes(b.value));else if(role.value==='super_admin')boxes.forEach(b=>b.checked=true);});
if(role.value==='cashier'&&!boxes.some(b=>b.checked))boxes.forEach(b=>b.checked=cashier.includes(b.value));});

/* Home page media: fade in the theme veil as the hero scrolls away. */
(()=>{if(!document.body.classList.contains('home-media'))return;const hero=document.querySelector('.v-hero');if(!hero)return;const root=document.documentElement;
const paint=()=>{const h=hero.offsetHeight||1;const p=Math.min(1,Math.max(0,(window.scrollY-h*.3)/(h*.7)));root.style.setProperty('--veil-progress',(p*.86).toFixed(3));};
window.addEventListener('scroll',paint,{passive:true});window.addEventListener('resize',paint);paint();})();

/* Nav underline: one line that slides to the link of the section in view (home page),
   or sits under the current page's link everywhere else. */
(()=>{const nav=document.getElementById('public-nav');if(!nav)return;const links=[...nav.querySelectorAll(':scope>a')];if(!links.length)return;
const ink=document.createElement('span');ink.className='nav-ink';ink.setAttribute('aria-hidden','true');nav.append(ink);
const linkFor=path=>links.find(a=>a.getAttribute('href')===path);
let current=links.find(a=>a.classList.contains('active'))||null;
const place=()=>{if(!current||nav.classList.contains('open')||!current.offsetWidth){nav.classList.remove('has-ink');return;}
  const n=nav.getBoundingClientRect(),r=current.getBoundingClientRect();ink.style.width=r.width+'px';ink.style.transform=`translateX(${r.left-n.left}px)`;nav.classList.add('has-ink');};
const setActive=link=>{if(!link||link===current){place();return;}links.forEach(a=>{a.classList.toggle('active',a===link);a.toggleAttribute('aria-current',a===link);});current=link;place();};
const sections=[...document.querySelectorAll('[data-nav]')];
if(sections.length){const spy=()=>{const line=window.innerHeight*.35;let pick=sections[0];
  for(const s of sections){if(s.getBoundingClientRect().top<=line)pick=s;}
  if(window.innerHeight+window.scrollY>=document.documentElement.scrollHeight-4)pick=sections[sections.length-1];
  setActive(linkFor(pick.dataset.nav));};
  window.addEventListener('scroll',spy,{passive:true});spy();}
window.addEventListener('resize',place);if(document.fonts&&document.fonts.ready)document.fonts.ready.then(place);place();})();

/* Measure the sticky header so the home first screen (hero + cards) fits exactly. */
(()=>{const header=document.querySelector('.site-public .site-header');if(!header)return;
const set=()=>document.documentElement.style.setProperty('--header-h',header.offsetHeight+'px');
set();window.addEventListener('resize',set);if(document.fonts&&document.fonts.ready)document.fonts.ready.then(set);})();
