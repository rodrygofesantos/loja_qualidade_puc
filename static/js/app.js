document.addEventListener("DOMContentLoaded",()=>{
  const menu=document.querySelector(".menu-button"),nav=document.querySelector("#nav");
  if(menu&&nav)menu.addEventListener("click",()=>{const open=nav.classList.toggle("open");menu.setAttribute("aria-expanded",String(open));});
  document.querySelectorAll("[data-copy]").forEach(button=>button.addEventListener("click",async()=>{const target=document.getElementById(button.dataset.copy);try{await navigator.clipboard.writeText(target.innerText);button.textContent="Copiado";}catch(_){button.textContent="Selecione e copie";}}));
  document.querySelectorAll("[data-select-mandatory]").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll("input[data-mandatory='true']").forEach(input=>{input.checked=true;});}));
});

