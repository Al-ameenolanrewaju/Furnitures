(() => {
  const menu = document.querySelector(".menu-toggle"), nav = document.querySelector(".main-nav");
  if (menu && nav) menu.addEventListener("click", () => { const open = menu.getAttribute("aria-expanded") !== "true"; menu.setAttribute("aria-expanded", String(open)); nav.classList.toggle("is-open", open); });
  document.addEventListener("click", event => { const thumb = event.target.closest("[data-gallery-src]"); if (thumb) { const main = document.getElementById("main-product-image"); if (main) main.src = thumb.dataset.gallerySrc; document.querySelectorAll("[data-gallery-src]").forEach(item => item.classList.toggle("active", item === thumb)); } });
})();
