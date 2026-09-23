// Ponto de entrada único do frontend ARKHER AI.
import { boot } from "./app/app";
import "./styles/main.css";

const container = document.getElementById("app");
if (container) {
  boot(container).catch((e) => {
    container.innerHTML = "";
    const div = document.createElement("div");
    div.className = "boot-error";
    div.textContent = `Falha ao iniciar a interface do ARKHER: ${(e as Error)?.message ?? e}`;
    container.append(div);
  });
}
