/* Progressive enhancement only. Authorization, pricing and stock live on the server. */
/* A looping background video is decoration, not content: hold it still for anyone
   who has asked the system for reduced motion. */
if(matchMedia('(prefers-reduced-motion: reduce)').matches){document.querySelectorAll('video.v-media').forEach(video=>{video.removeAttribute('autoplay');video.pause();});}
/* Preloader: leave as soon as the page is ready, but hold a beat so a fast load
   does not read as a flicker. The CSS clears the overlay on its own if this never runs. */
(()=>{const overlay=document.querySelector('[data-loader-overlay]');if(!overlay)return;const start=performance.now();
/* Reveal the loader video only once the browser proves it can decode it (HEVC is
   not universally supported). Anything else leaves the logo fallback in place. */
const clip=overlay.querySelector('[data-loader-video]');
if(clip&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
  const reveal=()=>{overlay.classList.add('video-ready');clip.play().catch(()=>overlay.classList.remove('video-ready'));};
  clip.readyState>=3?reveal():clip.addEventListener('canplay',reveal,{once:true});
  clip.addEventListener('error',()=>overlay.classList.remove('video-ready'),{once:true});
}const dismiss=()=>{overlay.classList.add('is-done');try{sessionStorage.setItem('verda-seen','1');}catch(e){}};const HOLD=5000;const settle=()=>setTimeout(dismiss,Math.max(0,HOLD-(performance.now()-start)));document.readyState==='complete'?settle():addEventListener('load',settle,{once:true});})();
document.querySelectorAll('[data-theme-toggle]').forEach(button=>button.addEventListener('click',()=>{const root=document.documentElement;const system=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';const current=root.getAttribute('data-theme')||system;const next=current==='dark'?'light':'dark';if(next===system){root.removeAttribute('data-theme');}else{root.setAttribute('data-theme',next);}try{next===system?localStorage.removeItem('verda-theme'):localStorage.setItem('verda-theme',next);}catch(e){}}));
document.querySelectorAll('[data-language-switch]').forEach(select=>select.addEventListener('change',()=>location.assign(select.value)));
document.querySelectorAll('.menu-toggle').forEach(button=>button.addEventListener('click',()=>{const menu=document.getElementById(button.getAttribute('aria-controls'));if(menu){const open=menu.classList.toggle('open');button.setAttribute('aria-expanded',String(open));}}));
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
document.querySelectorAll('[data-print]').forEach(button=>button.addEventListener('click',()=>window.print()));
document.querySelectorAll('[data-select-all]').forEach(input=>input.addEventListener('change',()=>document.querySelectorAll('input[name="ids"]').forEach(item=>item.checked=input.checked)));
document.querySelectorAll('[data-catalog-search],[data-catalog-category]').forEach(input=>input.addEventListener('input',()=>{const query=(document.querySelector('[data-catalog-search]')?.value||'').toLocaleLowerCase();const category=document.querySelector('[data-catalog-category]')?.value||'';document.querySelectorAll('[data-product-name]').forEach(card=>{card.hidden=!card.dataset.productName.toLocaleLowerCase().includes(query)||(category&&card.dataset.category!==category);});}));
const quick=document.querySelector('[data-quick-sale]');
if(quick){const update=()=>{let total=0;quick.querySelectorAll('[data-unit-price]').forEach(input=>total+=Number(input.value||0)*Number(input.dataset.unitPrice));const subtotal=quick.querySelector('[data-subtotal]');if(subtotal)subtotal.textContent=`${total.toLocaleString('en-US')} IQD`;const discount=Number(quick.querySelector('[name="discount"]')?.value||0);const kind=quick.querySelector('[name="discount_kind"]')?.value;total=Math.max(0,total-(kind==='percentage'?Math.round(total*discount/100):discount));const output=quick.querySelector('[data-quick-total]');if(output)output.textContent=`${total.toLocaleString('en-US')} IQD`;};quick.addEventListener('input',update);quick.querySelector('[data-clear-basket]')?.addEventListener('click',()=>{quick.querySelectorAll('[data-unit-price]').forEach(input=>input.value=0);update();});const scanner=quick.querySelector('[data-quick-scan]');scanner?.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();const code=scanner.value.trim();const row=Array.from(quick.querySelectorAll('[data-barcode]')).find(el=>el.dataset.barcode===code);const status=quick.querySelector('[data-scan-status]');if(row){const input=row.querySelector('[data-unit-price]');input.value=Number(input.value||0)+1;row.hidden=false;row.scrollIntoView({block:'nearest'});status.textContent=row.dataset.productName;update();}else{status.textContent=status.dataset.notFound;}scanner.value='';}});update();}
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
  bar.innerHTML='<div class="v-book-bar-info"><small id="vbb-time"></small><strong id="vbb-price">—</strong></div><button class="btn btn-primary" id="vbb-btn">Book now →</button>';
  document.body.appendChild(bar);
  const timeEl=bar.querySelector('#vbb-time');
  const priceEl=bar.querySelector('#vbb-price');
  const bookBtn=bar.querySelector('#vbb-btn');
  bookBtn.addEventListener('click',()=>{
    const form=document.getElementById('booking-form');
    if(form){const submit=form.querySelector('button[type=submit]');if(submit)submit.click();}
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
