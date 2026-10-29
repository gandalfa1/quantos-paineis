/* REVISAO GERAL, PARTE 3 (07/10/2026) - tabelas e graficos que nao cabem na tela.
   No celular, varias tabelas (e o grafico mes a mes da Quao preciso e) sao mais
   largas que a tela e rolam para o lado, sem nenhum sinal disso; e o teclado nao
   alcancava essas areas (axe: scrollable-region-focusable). Este arquivo, usado
   pelas telas e pelas paginas, so mexe nas areas que de fato passam da largura:
   - escreve acima delas "Arraste para o lado para ver tudo";
   - deixa a area alcancavel pelo Tab (tabindex=0) e com nome para o leitor de tela.
   Confere de novo quando a janela muda de tamanho e quando uma secao abre. */
(function () {
    var SELETOR = '.tabela-wrap, .grafico-rolagem';
    // Nome para o leitor de tela: a legenda da tabela (caption) ou do grafico
    // (figcaption); senao, o titulo mais proximo acima. Cada nome tem de ser
    // unico na pagina (axe: landmark-unique), entao repete com numero.
    var usados = {};
    function titulo(area) {
        var c = area.querySelector('caption') || (area.closest('figure') && area.closest('figure').querySelector('figcaption'));
        if (c) { return c.textContent; }
        var el = area;
        while (el) {
            var irmao = el.previousElementSibling;
            while (irmao) {
                if (/^H[2-4]$/.test(irmao.tagName)) { return irmao.textContent; }
                var h = irmao.querySelectorAll ? irmao.querySelectorAll('h2, h3, h4') : [];
                if (h.length) { return h[h.length - 1].textContent; }
                irmao = irmao.previousElementSibling;
            }
            el = el.parentElement;
        }
        return '';
    }
    function nomeDaArea(area) {
        var tipo = (area.classList.contains('grafico-rolagem') ? 'Gráfico' : 'Tabela');
        var t = titulo(area).replace(/\s+/g, ' ').trim();
        if (t.length > 90) { t = t.slice(0, 87) + '...'; }
        var nome = tipo + (t ? ': ' + t : '') + ' (mais larga que a tela; use as setas para os lados)';
        usados[nome] = (usados[nome] || 0) + 1;
        return usados[nome] > 1 ? nome + ' ' + usados[nome] : nome;
    }
    function preparar() {
        document.querySelectorAll(SELETOR).forEach(function (area) {
            var dica = area.previousElementSibling;
            var temDica = dica && dica.classList.contains('dica-rolagem');
            var rola = area.clientWidth > 0 && area.scrollWidth > area.clientWidth + 1;
            if (rola) {
                if (!temDica) {
                    var p = document.createElement('p');
                    p.className = 'dica-rolagem no-print';
                    p.setAttribute('aria-hidden', 'true');
                    p.textContent = 'Arraste para o lado para ver tudo →';
                    area.parentNode.insertBefore(p, area);
                }
                area.setAttribute('tabindex', '0');
                area.setAttribute('role', 'region');
                if (!area.hasAttribute('aria-label')) {
                    area.setAttribute('aria-label', nomeDaArea(area));
                }
            } else {
                if (temDica) { dica.parentNode.removeChild(dica); }
                area.removeAttribute('tabindex');
                area.removeAttribute('role');
                area.removeAttribute('aria-label');
            }
        });
    }
    var espera = null;
    function depois() { clearTimeout(espera); espera = setTimeout(preparar, 150); }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', preparar);
    } else {
        preparar();
    }
    window.addEventListener('load', preparar);
    window.addEventListener('resize', depois);
    document.addEventListener('toggle', depois, true);   // <details> abrindo ou fechando
})();
