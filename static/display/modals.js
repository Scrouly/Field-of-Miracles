/**
 * modals.js — Модальные окна событий «Поле чудес» (Задача 13).
 *
 * Спецмеханики:
 *  - Сектор «+»: подсветка закрытых клеток табло, выбор одной клетки;
 *  - «Две шкатулки»: выбор одной из двух шкатулок после 3 угаданных букв подряд;
 *  - Всплывающие уведомления призов и побед.
 */

(function () {
  'use strict';

  class ModalManager {
    constructor(displayManager) {
      this.display = displayManager;
      this.activeModal = null;
      this.isSelectingCell = false;
      this.lastHandledSound = null;
      this.lastHandledModalKey = null;

      this.createDOM();
    }

    createDOM() {
      // 1. Banner for sector '+'
      this.banner = document.createElement('div');
      this.banner.id = 'special-event-banner';
      this.banner.className = 'special-event-banner hidden';
      document.body.appendChild(this.banner);

      // 2. Overlay modal dialog
      this.overlay = document.createElement('div');
      this.overlay.id = 'event-modal-overlay';
      this.overlay.className = 'event-modal-overlay hidden';
      document.body.appendChild(this.overlay);
    }

    update(state) {
      if (!state) return;

      // 1. Sector '+' (reveal any closed cell)
      const isSectorPlus = (state.special_event === 'reveal_any_letter' || state.pending_modal === 'reveal_cell');
      if (isSectorPlus) {
        this.enableCellSelection(state);
      } else {
        this.disableCellSelection();
      }

      // 3. Two Boxes minigame
      if (state.special_event === 'two_boxes' || state.pending_modal === 'two_boxes') {
        const modalKey = `${state.version}:two_boxes`;
        if (this.lastHandledModalKey !== modalKey) {
          this.lastHandledModalKey = modalKey;
          this.showTwoBoxesModal();
        }
      } else if (state.pending_modal && state.pending_modal.startsWith('box_win:')) {
        const modalKey = `${state.version}:${state.pending_modal}`;
        if (this.lastHandledModalKey !== modalKey) {
          this.lastHandledModalKey = modalKey;
          const pts = state.pending_modal.split(':')[1] || '500';
          this.showBoxResult(true, pts);
        }
      } else if (state.pending_modal === 'box_empty') {
        const modalKey = `${state.version}:box_empty`;
        if (this.lastHandledModalKey !== modalKey) {
          this.lastHandledModalKey = modalKey;
          this.showBoxResult(false, 0);
        }
      } else if (state.pending_modal && state.pending_modal.startsWith('prize:')) {
        const modalKey = `${state.version}:${state.pending_modal}`;
        if (this.lastHandledModalKey !== modalKey) {
          this.lastHandledModalKey = modalKey;
          const prizeName = state.pending_modal.split(':')[1] || 'Приз';
          this.showPrizeModal(prizeName);
        }
      } else if (!isSectorPlus && !state.pending_modal && this.activeModal) {
        this.closeModal();
      }
    }

    enableCellSelection(state) {
      if (this.isSelectingCell) return;
      this.isSelectingCell = true;

      this.banner.textContent = '★ СЕКТОР «+»! Нажмите на любую закрытую клетку табло ★';
      this.banner.classList.remove('hidden');

      const boardElem = document.getElementById('board');
      if (!boardElem) return;

      const cells = boardElem.querySelectorAll('.board-cell');
      cells.forEach((cell) => {
        const cellIndex = parseInt(cell.dataset.index, 10);
        // If cell is unrevealed and alphabetic
        if (!isNaN(cellIndex) && state.mask && !state.mask[cellIndex]) {
          cell.classList.add('cell-selectable');

          const onClickCell = (e) => {
            e.stopPropagation();
            this.disableCellSelection();
            this.display.sendAction({
              type: 'REVEAL_CELL',
              cell_index: cellIndex,
            });
          };

          cell._onSelectCell = onClickCell;
          cell.addEventListener('click', onClickCell, { once: true });
        }
      });
    }

    disableCellSelection() {
      this.isSelectingCell = false;
      this.banner.classList.add('hidden');

      const boardElem = document.getElementById('board');
      if (!boardElem) return;

      const cells = boardElem.querySelectorAll('.board-cell');
      cells.forEach((cell) => {
        cell.classList.remove('cell-selectable');
        if (cell._onSelectCell) {
          cell.removeEventListener('click', cell._onSelectCell);
          delete cell._onSelectCell;
        }
      });
    }

    showTwoBoxesModal() {
      if (this.activeModal === 'two_boxes') return;
      this.activeModal = 'two_boxes';

      this.overlay.innerHTML = `
        <div class="event-modal-card">
          <div class="modal-badge">СПЕЦИАЛЬНАЯ ИГРА</div>
          <h2 class="modal-title">ДВЕ ШКАТУЛКИ</h2>
          <p class="modal-desc">Три буквы угаданы подряд! В одной из шкатулок деньги, вторая — пустая.</p>
          <div class="boxes-container">
            <button class="box-btn" data-box="0">
              <div class="box-icon">🎁</div>
              <div class="box-label">Шкатулка № 1</div>
            </button>
            <button class="box-btn" data-box="1">
              <div class="box-icon">🎁</div>
              <div class="box-label">Шкатулка № 2</div>
            </button>
          </div>
        </div>
      `;

      this.overlay.querySelectorAll('.box-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          const boxIdx = parseInt(btn.dataset.box, 10);
          btn.classList.add('box-opening');
          this.display.sendAction({
            type: 'CHOOSE_BOX',
            box_index: boxIdx,
          });
        });
      });

      this.overlay.classList.remove('hidden');
    }

    showBoxResult(isWinner, points) {
      this.activeModal = 'box_result';

      const icon = isWinner ? '💰' : '💨';
      const title = isWinner ? 'ПОБЕДА!' : 'ПУСТО!';
      const msg = isWinner
        ? `Вы открыли шкатулку с деньгами: <strong>+${points} очков</strong> на счёт!`
        : 'Увы, эта шкатулка оказалась пустой. Игра продолжается!';
      const cardClass = isWinner ? 'result-win' : 'result-empty';

      this.overlay.innerHTML = `
        <div class="event-modal-card ${cardClass}">
          <div class="box-result-icon">${icon}</div>
          <h2 class="modal-title">${title}</h2>
          <p class="modal-desc">${msg}</p>
          <button class="btn-modal-close">Продолжить игру</button>
        </div>
      `;

      const closeBtn = this.overlay.querySelector('.btn-modal-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', () => this.closeModal());
      }

      this.overlay.classList.remove('hidden');

      // Auto close after 4 seconds if not clicked
      setTimeout(() => {
        if (this.activeModal === 'box_result') {
          this.closeModal();
        }
      }, 4000);
    }

    showPrizeModal(prizeName) {
      this.activeModal = 'prize';

      this.overlay.innerHTML = `
        <div class="event-modal-card result-win">
          <div class="box-result-icon">🏆</div>
          <h2 class="modal-title">СЕКТОР «ПРИЗ»!</h2>
          <p class="modal-desc">Игрок получает приз: <strong>${escapeHtml(prizeName)}</strong>!</p>
          <button class="btn-modal-close">Отлично!</button>
        </div>
      `;

      const closeBtn = this.overlay.querySelector('.btn-modal-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', () => this.closeModal());
      }

      this.overlay.classList.remove('hidden');
    }

    closeModal() {
      this.activeModal = null;
      this.overlay.classList.add('hidden');
      this.overlay.innerHTML = '';
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  window.ModalManager = ModalManager;
})();
