document.addEventListener("DOMContentLoaded", () => {
  const menuButton = document.querySelector(".menu-button");
  const sidebar = document.querySelector("#sidebar");
  const closeButtons = document.querySelectorAll("[data-menu-close]");
  let returnFocus = null;

  const focusableInSidebar = () => sidebar
    ? [...sidebar.querySelectorAll("a[href], button:not([disabled]), summary, input, select, textarea")]
    : [];

  const openMenu = () => {
    if (!menuButton || !sidebar) return;
    returnFocus = document.activeElement;
    sidebar.classList.add("open");
    document.body.classList.add("menu-open");
    menuButton.setAttribute("aria-expanded", "true");
    const first = focusableInSidebar()[0];
    (first || sidebar).focus();
  };

  const closeMenu = ({ restoreFocus = true } = {}) => {
    if (!menuButton || !sidebar) return;
    sidebar.classList.remove("open");
    document.body.classList.remove("menu-open");
    menuButton.setAttribute("aria-expanded", "false");
    if (restoreFocus && returnFocus instanceof HTMLElement) returnFocus.focus();
  };

  if (menuButton && sidebar) {
    menuButton.addEventListener("click", () => {
      if (sidebar.classList.contains("open")) closeMenu();
      else openMenu();
    });
    closeButtons.forEach((button) => button.addEventListener("click", () => closeMenu()));
    sidebar.querySelectorAll("a[href]").forEach((link) => link.addEventListener("click", () => {
      if (window.matchMedia("(max-width: 900px)").matches) closeMenu({ restoreFocus: false });
    }));
    document.addEventListener("keydown", (event) => {
      if (!sidebar.classList.contains("open")) return;
      if (event.key === "Escape") {
        event.preventDefault();
        closeMenu();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = focusableInSidebar();
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
    window.matchMedia("(min-width: 901px)").addEventListener("change", (event) => {
      if (event.matches) closeMenu({ restoreFocus: false });
    });
  }

  document.querySelectorAll("[data-copy]").forEach((button) => button.addEventListener("click", async () => {
    const target = document.getElementById(button.dataset.copy);
    try {
      await navigator.clipboard.writeText(target.innerText);
      button.textContent = "Copiado";
    } catch (_) {
      button.textContent = "Selecione e copie";
    }
  }));

  document.querySelectorAll("[data-select-mandatory]").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll("input[data-mandatory='true']").forEach((input) => {
      input.checked = true;
    });
  }));
});
