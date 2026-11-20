/**
 * display.js — Главный контроллер экрана мультиборда /display/.
 *
 * Опрашивает сервер каждые 400 мс через GET /api/state/?since=<version>.
 * Отправляет действия через POST /api/action/ с защитой по expected_version.
 */

(function () {
  'use strict';

  class DisplayController {
    constructor() {
      this.version = -1;
      this.pollIntervalMs = 400;
      this.pollTimer = null;
      this.isSubmitting = false;

      this.stageManager = new window.StageManager('#stage');
      this.boardManager = new window.BoardManager(document.getElementById('board'));
      this.keyboardManager = new window.KeyboardManager(
        document.getElementById('keyboard'),
        (letter) => this.onLetterGuess(letter)
      );

      this.questionTextElem = document.getElementById('question-text');
      this.sectorValueElem = document.getElementById('sector-value');
      this.playersContainer = document.getElementById('players-container');
      this.statusMessageElem = document.getElementById('status-message');
      this.roundWonBanner = document.getElementById('round-won-banner');

      this.csrfToken = this.getCsrfToken();

      this.startPolling();
    }

    getCsrfToken() {
      const match = document.cookie.match(/csrftoken=([^;]+)/);
      if (match) return match[1];
      const meta = document.querySelector('meta[name="csrf-token"]');
      return meta ? meta.getAttribute('content') : '';
    }

    async onLetterGuess(letter) {
      if (this.isSubmitting) return;
      this.isSubmitting = true;

      try {
        const response = await fetch('/api/action/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCsrfToken(),
          },
          body: JSON.stringify({
            expected_version: this.version,
            action: {
              type: 'GUESS_LETTER',
              letter: letter,
            },
          }),
        });

        if (response.status === 409) {
          console.warn('Конфликт версий, синхронизация с сервером...');
          await this.fetchState(true);
          return;
        }

        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          console.error('Ошибка применения действия:', err);
          return;
        }

        const data = await response.json();
        this.applyState(data);
      } catch (err) {
        console.error('Сетевая ошибка при отправке буквы:', err);
      } finally {
        this.isSubmitting = false;
      }
    }

    startPolling() {
      // Первичный запрос состояния без since
      this.fetchState(true);

      this.pollTimer = setInterval(() => {
        this.fetchState(false);
      }, this.pollIntervalMs);
    }

    async fetchState(force = false) {
      try {
        const url = force || this.version < 0
          ? '/api/state/'
          : `/api/state/?since=${this.version}`;

        const response = await fetch(url, {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
          },
        });

        if (!response.ok) {
          console.warn('Ошибка получения состояния:', response.status);
          return;
        }

        const data = await response.json();

        // Если «без новостей» — ничего не обновляем
        if (data.status === 'no_news' || data.changed === false) {
          return;
        }

        this.applyState(data);
      } catch (err) {
        console.warn('Ошибка опроса состояния:', err);
      }
    }

    applyState(state) {
      if (!state) return;

      this.version = state.version;

      // Обновление вопроса
      if (this.questionTextElem) {
        this.questionTextElem.textContent = state.question || 'Вопрос раунда';
      }

      // Обновление значения сектора
      if (this.sectorValueElem) {
        this.sectorValueElem.textContent = `${state.sector_value || 0} очков`;
      }

      // Обновление табло (маска и буквы)
      this.boardManager.render(state.word, state.mask || []);

      // Обновление клавиатуры
      this.keyboardManager.update(state.guessed_letters || [], state.word, state.phase);

      // Обновление списка игроков и счёта
      this.renderPlayers(state.players || [], state.scores || [], state.current_player);

      // Проверка победы в раунде
      if (state.phase === 'round_won') {
        if (this.roundWonBanner) {
          const winnerName = (state.players && state.players[state.current_player]) || 'Игрок';
          this.roundWonBanner.textContent = `Слово отгадано! Победитель тура: ${winnerName}!`;
          this.roundWonBanner.classList.add('visible');
        }
      } else if (this.roundWonBanner) {
        this.roundWonBanner.classList.remove('visible');
      }
    }

    renderPlayers(players, scores, currentPlayerIndex) {
      if (!this.playersContainer) return;
      this.playersContainer.innerHTML = '';

      players.forEach((name, index) => {
        const isCurrent = index === currentPlayerIndex;
        const score = (scores && scores[index]) || 0;

        const card = document.createElement('div');
        card.className = `player-card ${isCurrent ? 'is-current' : ''}`;
        card.innerHTML = `
          <div class="player-turn-indicator">${isCurrent ? 'ХОД' : ''}</div>
          <div class="player-name">${name}</div>
          <div class="player-score">${score}</div>
        `;
        this.playersContainer.appendChild(card);
      });
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    window.displayController = new DisplayController();
  });
})();
