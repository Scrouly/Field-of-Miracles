/**
 * host.js — Логика пульта ведущего /host/.
 *
 * Отображает загаданное слово, подсказку, статус хода, кнопки действий и журнал.
 * Поддерживает горячие клавиши и ввод букв с физической клавиатуры при сбое тача.
 */

(function () {
  'use strict';

  class HostController {
    constructor() {
      this.version = -1;
      this.pollIntervalMs = 400;
      this.pollTimer = null;
      this.state = null;
      this.isSubmitting = false;

      // DOM Elements
      this.versionElem = document.getElementById('state-version');
      this.questionElem = document.getElementById('host-question');
      this.hintElem = document.getElementById('host-hint');
      this.wordDisplay = document.getElementById('host-word-display');
      this.playersContainer = document.getElementById('host-players');
      this.logList = document.getElementById('host-log-list');
      this.letterInput = document.getElementById('host-letter-input');
      this.sectorValueElem = document.getElementById('host-sector-value');
      this.roundSelect = document.getElementById('host-round-select');
      this.btnLoadRound = document.getElementById('btn-load-round');
      this.btnResetRound = document.getElementById('btn-reset-round');
      this.btnSpinHost = document.getElementById('btn-spin-host');

      this.initEvents();
      this.startPolling();
      this.fetchRounds();
    }

    getCsrfToken() {
      const match = document.cookie.match(/csrftoken=([^;]+)/);
      if (match) return match[1];
      const meta = document.querySelector('meta[name="csrf-token"]');
      return meta ? meta.getAttribute('content') : '';
    }

    initEvents() {
      // Кнопки панели
      document.getElementById('btn-skip-turn')?.addEventListener('click', () => {
        this.sendAction({ type: 'SKIP_TURN' });
      });

      document.getElementById('btn-word-correct')?.addEventListener('click', () => {
        this.sendAction({ type: 'GUESS_WORD', correct: true });
      });

      document.getElementById('btn-word-incorrect')?.addEventListener('click', () => {
        this.sendAction({ type: 'GUESS_WORD', correct: false });
      });

      document.getElementById('btn-undo')?.addEventListener('click', () => {
        this.sendAction({ type: 'UNDO' });
      });

      document.getElementById('btn-send-letter')?.addEventListener('click', () => {
        this.submitLetterInput();
      });

      // Переключение и сброс раундов
      this.btnLoadRound?.addEventListener('click', () => {
        if (!this.roundSelect || !this.roundSelect.value) return;
        this.sendAction({
          type: 'LOAD_ROUND',
          round_id: parseInt(this.roundSelect.value, 10),
        });
      });

      this.btnResetRound?.addEventListener('click', () => {
        if (confirm('Сбросить текущий раунд сначала?')) {
          this.sendAction({ type: 'RESET_ROUND' });
        }
      });

      this.btnSpinHost?.addEventListener('click', () => {
        this.triggerSpin();
      });

      // Ввод буквы по Enter
      this.letterInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.submitLetterInput();
        }
      });

      // Глобальные горячие клавиши для ведущего
      window.addEventListener('keydown', (e) => {
        // Если фокус в инпуте, горячие клавиши не перехватываем (кроме Escape)
        if (document.activeElement === this.letterInput) {
          return;
        }

        // Ctrl + Z -> Undo
        if (e.ctrlKey && (e.key === 'z' || e.key === 'я')) {
          e.preventDefault();
          this.sendAction({ type: 'UNDO' });
          return;
        }

        // Пробел -> Пропуск хода
        if (e.code === 'Space') {
          e.preventDefault();
          this.sendAction({ type: 'SKIP_TURN' });
          return;
        }

        // R / К -> Вращение барабана
        if (e.code === 'KeyR') {
          e.preventDefault();
          this.triggerSpin();
          return;
        }

        // Прямой ввод русской буквы с клавиатуры
        const char = e.key.toLowerCase();
        if (/^[а-яё]$/i.test(char)) {
          e.preventDefault();
          this.sendAction({ type: 'GUESS_LETTER', letter: char });
        }
      });
    }

    submitLetterInput() {
      if (!this.letterInput) return;
      const val = this.letterInput.value.trim().toLowerCase();
      if (!val) return;
      this.letterInput.value = '';
      this.sendAction({ type: 'GUESS_LETTER', letter: val[0] });
    }

    async sendAction(actionPayload) {
      if (this.isSubmitting) return;
      this.isSubmitting = true;

      try {
        const resp = await fetch('/api/action/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCsrfToken(),
          },
          body: JSON.stringify({
            expected_version: this.version,
            action: actionPayload,
          }),
        });

        if (resp.status === 409) {
          console.warn('Конфликт версии на пульте, обновление...');
          await this.fetchState(true);
          return;
        }

        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          console.error('Ошибка действия:', err);
          return;
        }

        const data = await resp.json();
        this.applyState(data);
        this.fetchLogs();
      } catch (err) {
        console.error('Сетевая ошибка при отправке действия:', err);
      } finally {
        this.isSubmitting = false;
      }
    }

    startPolling() {
      this.fetchState(true);
      this.fetchLogs();

      this.pollTimer = setInterval(() => {
        this.fetchState(false);
      }, this.pollIntervalMs);
    }

    async fetchState(force = false) {
      try {
        const url = force || this.version < 0
          ? '/api/state/'
          : `/api/state/?since=${this.version}`;

        const resp = await fetch(url, { headers: { 'Accept': 'application/json' } });
        if (!resp.ok) return;

        const data = await resp.json();
        if (data.status === 'no_news' || data.changed === false) return;

        this.applyState(data);
        this.fetchLogs();
      } catch (err) {
        console.warn('Ошибка опроса состояния:', err);
      }
    }

    async fetchLogs() {
      try {
        const resp = await fetch('/api/logs/');
        if (!resp.ok) return;
        const data = await resp.json();
        if (data && data.logs) {
          this.renderLogs(data.logs);
        }
      } catch (err) {
        console.warn('Ошибка получения журнала:', err);
      }
    }

    async fetchRounds() {
      try {
        const resp = await fetch('/api/rounds/');
        if (!resp.ok) return;
        const data = await resp.json();
        if (!this.roundSelect || !data.rounds) return;

        this.roundSelect.innerHTML = '';
        data.rounds.forEach((r) => {
          const opt = document.createElement('option');
          opt.value = r.id;
          const playersStr = r.players && r.players.length ? ` [${r.players.join(', ')}]` : '';
          opt.textContent = `Тур ${r.order} (${r.type === 'supergame' ? 'СУПЕРИГРА' : r.type}): ${r.word} — «${r.question}»${playersStr}`;
          if (this.state && this.state.word === r.word) {
            opt.selected = true;
          }
          this.roundSelect.appendChild(opt);
        });
      } catch (err) {
        console.error('Ошибка загрузки туров:', err);
      }
    }

    async triggerSpin() {
      const numSectors = 16;
      const targetIndex = Math.floor(Math.random() * numSectors);
      const defaultValues = [100, 200, 300, 0, 400, 0, 500, 0, 150, 250, 0, 350, 450, 600, 750, 1000];
      const secVal = defaultValues[targetIndex] || 100;

      await this.sendAction({ type: 'START_SPIN' });
      setTimeout(async () => {
        await this.sendAction({
          type: 'SPIN_RESULT',
          sector_index: targetIndex,
          sector_value: secVal,
        });
      }, 1000);
    }

    applyState(state) {
      if (!state) return;
      this.state = state;
      this.version = state.version;

      if (this.roundSelect && state.word) {
        for (let i = 0; i < this.roundSelect.options.length; i++) {
          if (this.roundSelect.options[i].textContent.includes(state.word)) {
            this.roundSelect.selectedIndex = i;
            break;
          }
        }
      }

      if (this.versionElem) {
        this.versionElem.textContent = `v${this.version}`;
      }

      if (this.questionElem) {
        this.questionElem.textContent = state.question || 'Вопрос раунда';
      }

      if (this.hintElem) {
        this.hintElem.textContent = state.hint
          ? `Подсказка ведущему: ${state.hint}`
          : 'Подсказка отсутствует';
      }

      if (this.sectorValueElem) {
        this.sectorValueElem.textContent = `${state.sector_value || 0} очков`;
      }

      this.renderWord(state.word, state.mask || []);
      this.renderPlayers(state.players || [], state.scores || [], state.current_player);
    }

    renderWord(word, mask) {
      if (!this.wordDisplay || !word) return;
      this.wordDisplay.innerHTML = '';

      const chars = word.split('');
      chars.forEach((char, idx) => {
        const isRevealed = Boolean(mask[idx]);
        const isLetter = /^[а-яёa-z]$/i.test(char);

        const cell = document.createElement('div');
        cell.className = `word-letter-cell ${isRevealed ? 'is-revealed' : 'is-hidden'}`;
        cell.title = isRevealed ? 'Буква уже открыта' : 'Нажмите, чтобы открыть эту букву';

        cell.innerHTML = `
          <div>${char.toUpperCase()}</div>
          <div class="word-letter-status">${isRevealed ? '✓' : 'закрыта'}</div>
        `;

        if (!isRevealed && isLetter) {
          cell.addEventListener('click', () => {
            this.sendAction({ type: 'GUESS_LETTER', letter: char.toLowerCase() });
          });
        }

        this.wordDisplay.appendChild(cell);
      });
    }

    renderPlayers(players, scores, currentPlayerIndex) {
      if (!this.playersContainer) return;
      this.playersContainer.innerHTML = '';

      players.forEach((name, idx) => {
        const isCurrent = idx === currentPlayerIndex;
        const score = (scores && scores[idx]) || 0;

        const card = document.createElement('div');
        card.className = `host-player-card ${isCurrent ? 'active-turn' : ''}`;
        card.innerHTML = `
          <div class="badge-turn">${isCurrent ? '● ХОДИТ СЕЙЧАС' : ''}</div>
          <div style="font-weight: bold; font-size: 16px; margin: 4px 0;">${name}</div>
          <div style="font-size: 20px; font-weight: 900; color: #f4c430; margin-bottom: 8px;">${score}</div>
          <div>
            <button class="score-control-btn" data-player="${idx}" data-delta="50">+50</button>
            <button class="score-control-btn" data-player="${idx}" data-delta="100">+100</button>
            <button class="score-control-btn" data-player="${idx}" data-delta="-50">-50</button>
          </div>
        `;

        card.querySelectorAll('.score-control-btn').forEach((btn) => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const player = parseInt(btn.getAttribute('data-player'), 10);
            const delta = parseInt(btn.getAttribute('data-delta'), 10);
            this.sendAction({ type: 'MANUAL_SCORE', player, delta });
          });
        });

        this.playersContainer.appendChild(card);
      });
    }

    renderLogs(logs) {
      if (!this.logList) return;
      this.logList.innerHTML = '';

      if (!logs || logs.length === 0) {
        this.logList.innerHTML = '<div style="color: #94a3b8; font-size: 13px;">Журнал пуст</div>';
        return;
      }

      logs.forEach((log) => {
        const item = document.createElement('div');
        let modifier = '';
        let detail = '';

        if (log.action === 'GUESS_LETTER') {
          detail = `буква «${(log.data.letter || '').toUpperCase()}»`;
        } else if (log.action === 'MANUAL_SCORE') {
          detail = `игрок ${log.data.player}: ${log.data.delta > 0 ? '+' : ''}${log.data.delta}`;
        } else if (log.action === 'GUESS_WORD') {
          detail = log.data.correct ? 'слово названо верно!' : 'неверно';
        }

        item.className = `log-item ${modifier}`;
        item.innerHTML = `
          <div><strong>#${log.number}</strong> ${log.action} <span style="color: #94a3b8;">${detail}</span></div>
          <div style="color: #64748b; font-size: 11px;">${log.created_at || ''}</div>
        `;
        this.logList.appendChild(item);
      });
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    window.hostController = new HostController();
  });
})();
