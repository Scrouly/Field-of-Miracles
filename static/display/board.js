/**
 * board.js — Табло слов «Поле чудес».
 *
 * Требования:
 *  - Слова от 5 до 14 букв (и более с пробелом/дефисом) отображаются без обрезки;
 *  - Раскладка в 1 или 2 строки с центрированием;
 *  - Анимация 3D-переворота клетки при открытии буквы;
 *  - Предоткрытые разделители (дефис, пробел).
 */

(function () {
  'use strict';

  class BoardManager {
    constructor(boardElement) {
      this.board = boardElement;
      this.currentWord = '';
      this.currentMask = [];
      this.cells = []; // Массив DOM-элементов клеток для синхронизации флипа
    }

    /**
     * Разбиение слова на строки (1 или 2) для центрирования на табло.
     * Возвращает массив строк с индексами символов исходного слова.
     */
    layoutWord(word) {
      const len = word.length;

      // Если слово короткое (до 10 букв) и без пробелов/дефисов — ровно 1 строка
      if (len <= 10 && !word.includes(' ') && !word.includes('-')) {
        return [word.split('').map((char, index) => ({ char, index }))];
      }

      // Если в слове есть пробел, делим по пробелу
      if (word.includes(' ')) {
        const parts = word.split(' ');
        const rows = [];
        let globalIndex = 0;

        // Если 2 части или больше, компонуем в 2 строки
        if (parts.length === 2) {
          const row1 = parts[0].split('').map((char) => ({ char, index: globalIndex++ }));
          globalIndex++; // пропускаем пробел в индексе
          const row2 = parts[1].split('').map((char) => ({ char, index: globalIndex++ }));
          return [row1, row2];
        }

        // Общий случай для нескольких пробелов
        let currentRow = [];
        for (let i = 0; i < parts.length; i++) {
          const partChars = parts[i].split('').map((char) => ({ char, index: globalIndex++ }));
          if (currentRow.length === 0) {
            currentRow.push(...partChars);
          } else if (currentRow.length + 1 + partChars.length <= 14) {
            // Добавляем пробел как клетку-разделитель
            currentRow.push({ char: ' ', index: globalIndex - partChars.length - 1, isSpace: true });
            currentRow.push(...partChars);
          } else {
            rows.push(currentRow);
            currentRow = [...partChars];
          }
          globalIndex++; // за пробел
        }
        if (currentRow.length > 0) rows.push(currentRow);
        return rows;
      }

      // Если слово длиннее 10 букв (до 14+):
      // Если есть дефис, делим по дефису
      if (word.includes('-')) {
        const hyphenIdx = word.indexOf('-');
        const row1 = word.slice(0, hyphenIdx + 1).split('').map((char, idx) => ({ char, index: idx }));
        const row2 = word.slice(hyphenIdx + 1).split('').map((char, idx) => ({ char, index: hyphenIdx + 1 + idx }));
        return [row1, row2];
      }

      // Если просто длинное слитное слово (11–14+ букв), делим примерно пополам
      const mid = Math.ceil(len / 2);
      const row1 = word.slice(0, mid).split('').map((char, idx) => ({ char, index: idx }));
      const row2 = word.slice(mid).split('').map((char, idx) => ({ char, index: mid + idx }));
      return [row1, row2];
    }

    /**
     * Отрисовка табло по состоянию.
     */
    render(word, mask) {
      if (!word) {
        this.board.innerHTML = '';
        this.cells = [];
        this.currentWord = '';
        this.currentMask = [];
        return;
      }

      const wordChanged = word !== this.currentWord || mask.length !== this.currentMask.length;

      if (wordChanged) {
        this.currentWord = word;
        this.currentMask = [...mask];
        this.buildBoardDOM(word, mask);
        return;
      }

      // Если слово то же, обновляем маску и анимируем новые перевороты
      this.updateRevealedCells(word, mask);
      this.currentMask = [...mask];
    }

    buildBoardDOM(word, mask) {
      this.board.innerHTML = '';
      this.cells = new Array(word.length);

      const rows = this.layoutWord(word);

      rows.forEach((rowItems, rowIndex) => {
        const rowElem = document.createElement('div');
        rowElem.className = 'board-row';
        rowElem.setAttribute('data-row', rowIndex);

        rowItems.forEach((item) => {
          const char = item.char;
          const index = item.index;
          const isRevealed = Boolean(mask[index]);
          const isSpecial = char === '-' || char === ' ' || item.isSpace;

          const cell = document.createElement('div');
          cell.className = 'board-cell';
          cell.setAttribute('data-index', index);

          if (isSpecial) {
            if (char === ' ' || item.isSpace) {
              cell.classList.add('cell-space');
            } else if (char === '-') {
              cell.classList.add('cell-separator');
              cell.innerHTML = `
                <div class="cell-inner is-flipped">
                  <div class="cell-front"></div>
                  <div class="cell-back">-</div>
                </div>
              `;
            }
          } else {
            cell.innerHTML = `
              <div class="cell-inner ${isRevealed ? 'is-flipped' : ''}">
                <div class="cell-front">
                  <span class="cell-pattern"></span>
                </div>
                <div class="cell-back">${char.toUpperCase()}</div>
              </div>
            `;
          }

          rowElem.appendChild(cell);
          if (index < this.cells.length) {
            this.cells[index] = cell;
          }
        });

        this.board.appendChild(rowElem);
      });
    }

    updateRevealedCells(word, mask) {
      mask.forEach((revealed, idx) => {
        const prevRevealed = Boolean(this.currentMask[idx]);
        if (revealed && !prevRevealed) {
          const cell = this.cells[idx];
          if (cell) {
            const inner = cell.querySelector('.cell-inner');
            if (inner && !inner.classList.contains('is-flipped')) {
              // Небольшая задержка для каскадного эффекта открытия нескольких букв
              setTimeout(() => {
                inner.classList.add('is-flipped');
              }, 50 * idx);
            }
          }
        }
      });
    }
  }

  window.BoardManager = BoardManager;
})();
